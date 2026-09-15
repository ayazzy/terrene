"""Bounded daily reanalysis point queries; never station or parcel observations."""
from datetime import date, datetime, timedelta, timezone
import json
import math
import re
from typing import Literal

from pydantic import Field, model_validator

from backend.acquisition_contracts import Contract, AcquisitionError, BinaryArtifact, digest, encode

SOURCE = 'nasa.power_merra2_daily'
ADAPTER = 'nasa_power_daily_point_v1'
PROCESSING = 'power_daily_missingness_v1'
ENDPOINT = 'https://power.larc.nasa.gov/api/temporal/daily/point'
# Native AG community units; never silently convert daily rates to totals.
VARIABLES = {
    'T2M': ('C', 'daily_mean_air_temperature_2m', -120, 70),
    'T2M_MIN': ('C', 'daily_minimum_air_temperature_2m', -120, 70),
    'T2M_MAX': ('C', 'daily_maximum_air_temperature_2m', -120, 70),
    'PRECTOTCORR': ('mm/day', 'daily_bias_corrected_precipitation_rate', 0, 3000),
    'WS10M': ('m/s', 'daily_mean_wind_speed_10m', 0, 150),
    'RH2M': ('%', 'daily_mean_relative_humidity_2m', 0, 100),
}
LIMITS = {'max_days':366,'max_response_bytes':1_000_000,'max_total_bytes':2_000_000,
          'network_deadline_seconds':120,'request_timeout_seconds':45,'minimum_age_days':120}


def calendar_date(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):
        raise ValueError('calendar_date_required')
    return date.fromisoformat(value)


class WeatherRequest(Contract):
    contract_version: Literal['geographic_weather_request_v1']
    source_id: Literal['nasa.power_merra2_daily']
    adapter_version: Literal['nasa_power_daily_point_v1']
    point: dict
    start_date: str
    end_date: str
    time_standard: Literal['UTC']
    idempotency_key: str = Field(min_length=1,max_length=128,pattern=r'^[A-Za-z0-9_.:-]+$')

    @model_validator(mode='after')
    def validate_request(self):
        start,end = calendar_date(self.start_date),calendar_date(self.end_date)
        if start < date(1981,1,1) or not 0 <= (end-start).days < LIMITS['max_days']:
            raise ValueError('weather_interval_limit')
        p = self.point
        coords = p.get('coordinates')
        if (set(p) != {'type','coordinates'} or p['type'] != 'Point'
                or not isinstance(coords,list) or len(coords) != 2
                or any(type(v) not in (int,float) or not math.isfinite(v) for v in coords)
                or not -180 <= coords[0] <= 180 or not -90 <= coords[1] <= 90):
            raise ValueError('weather_requires_wgs84_point')
        return self

    @property
    def geometry_fingerprint(self):
        return digest(encode(self.point))


def descriptor():
    return {'source_id':SOURCE,'adapter_version':ADAPTER,'normalization_version':PROCESSING,
        'data_family':'weather_timeseries','publisher':'NASA POWER / NASA GMAO',
        'endpoint':ENDPOINT,'access':'public; no credentials','community':'AG',
        'evidence_kind':'modelled_reanalysis','source_model':'MERRA-2',
        'nominal_source_grid_degrees':{'latitude':0.5,'longitude':0.625},
        'temporal_resolution':'daily','time_standard':'UTC','limits':LIMITS,
        'variables':{k:{'unit':v[0],'meaning':v[1]} for k,v in VARIABLES.items()},
        'coverage_method':'Global model point-query service, including UK; actual temporal availability measured per variable.',
        'licence':'NASA POWER data are freely available; acknowledge NASA POWER and source models.',
        'terms_url':'https://forum.earthdata.nasa.gov/viewtopic.php?t=82',
        'documentation':'https://power.larc.nasa.gov/docs/services/api/temporal/daily/',
        'limitations':['Reanalysis is modelled from assimilated observations, not a station measurement.',
            'Coarse grid values are not parcel averages, site measurements or a forecast.',
            'Returned point/elevation does not establish an exact native cell identity or a measured site altitude.',
            'Recent periods and non-MERRA2 or mixed-model responses are refused by this adapter.',
            'API version is not an immutable source dataset release; each refresh needs a new capture.',
            'Missing days and provider fill values remain explicit; evidence availability is not predictive confidence.']}


def days(request):
    start,end = calendar_date(request.start_date),calendar_date(request.end_date)
    return [(start+timedelta(days=i)).strftime('%Y%m%d') for i in range((end-start).days+1)]


def parameters(request, *, day=None):
    return {'parameters':','.join(VARIABLES),'community':'AG',
            'longitude':request.point['coordinates'][0],'latitude':request.point['coordinates'][1],
            'start':day or request.start_date.replace('-',''),'end':day or request.end_date.replace('-',''),
            'format':'JSON','time-standard':'UTC'}


def decode(content):
    def reject_constant(_):
        raise ValueError('nonfinite_json')

    def unique(pairs):
        result = {}
        for key,value in pairs:
            if key in result:
                raise ValueError('duplicate_json_key')
            result[key] = value
        return result
    try:
        value = json.loads(content,object_pairs_hook=unique,parse_constant=reject_constant)
        if not isinstance(value,dict): raise ValueError('object_required')
        return value
    except (ValueError,UnicodeError) as exc:
        raise AcquisitionError('invalid_weather_json') from exc


def normalize(value, request):
    """Preserve daily native units, separate missing keys, nulls, fill and genuine zero."""
    try:
        if (set(value) != {'type','geometry','properties','header','messages','parameters','times'}
                or set(value['properties']) != {'parameter'} or not isinstance(value['times'],dict)):
            raise AcquisitionError('weather_response_schema_changed')
        header = value['header'];coords = value['geometry']['coordinates']
        if (value['type'] != 'Feature' or value['geometry']['type'] != 'Point'
                or len(coords) != 3 or any(type(v) not in (int,float) or not math.isfinite(v) for v in coords)
                or any(abs(coords[i]-request.point['coordinates'][i]) > 0.00051 for i in (0,1))):
            raise AcquisitionError('weather_location_mismatch')
        if (header['title'] != 'NASA/POWER Source Native Resolution Daily Data'
                or header['api']['name'] != 'POWER Daily API'
                or not re.fullmatch(r'v2\.\d+\.\d+',header['api']['version'])
                or header['sources'] != ['MERRA2','POWER']):
            raise AcquisitionError('weather_source_identity_changed')
        if (header['time_standard'] != 'UTC' or header['start'] != request.start_date.replace('-','')
                or header['end'] != request.end_date.replace('-','')):
            raise AcquisitionError('weather_time_mismatch')
        if type(header['fill_value']) not in (int,float) or header['fill_value'] != -999:
            raise AcquisitionError('weather_fill_schema_changed')
        if value.get('messages') != []:
            raise AcquisitionError('weather_provider_warning')
        data = value['properties']['parameter'];metadata = value['parameters']
        if set(data) != set(VARIABLES) or set(metadata) != set(VARIABLES):
            raise AcquisitionError('weather_variable_schema_changed')
        expected = days(request);rows,coverage = [],{}
        for key,(unit,meaning,lower,upper) in VARIABLES.items():
            if (metadata[key]['units'] != unit or not isinstance(metadata[key]['longname'],str)
                    or not metadata[key]['longname'] or not isinstance(data[key],dict)):
                raise AcquisitionError('weather_unit_or_schema_changed')
            if set(data[key])-set(expected):
                raise AcquisitionError('weather_unexpected_date')
            counts = {'present':0,'provider_fill':0,'provider_null':0,'absent_date':0}
            series = []
            for day in expected:
                native = data[key].get(day)
                state = 'absent_date' if day not in data[key] else 'provider_null' if native is None else 'provider_fill' if native == -999 else 'present'
                if state == 'present' and (type(native) not in (float,int) or not math.isfinite(native) or not lower <= native <= upper):
                    raise AcquisitionError('weather_value_out_of_range')
                counts[state] += 1
                series.append({'date':date.fromisoformat(day).isoformat(),'value':native if state == 'present' else None,'state':state})
            rows.append({'variable':key,'unit':unit,'meaning':meaning,'daily':series})
            valid=counts['present']
            coverage[key] = {'unit':unit,'meaning':meaning,'expected_days':len(expected),'present_days':valid,
                            'missing_days':len(expected)-valid,'missingness_counts':counts,
                            'availability':'complete' if valid == len(expected) else 'partial' if valid else 'no_valid_days'}
        # Compare available temperature pairs; missing input never becomes zero.
        temperatures = {row['variable']:row['daily'] for row in rows if row['variable'].startswith('T2M')}
        for i in range(len(expected)):
            lo,mean,hi = (temperatures[k][i]['value'] for k in ('T2M_MIN','T2M','T2M_MAX'))
            if ((lo is not None and hi is not None and lo > hi)
                    or (mean is not None and ((lo is not None and mean < lo) or (hi is not None and mean > hi)))):
                raise AcquisitionError('weather_temperature_inconsistent')
        source = {'header':header,'geometry':value['geometry'],'parameters':metadata,'messages':value['messages']}
        return {'source_metadata':source,'series':{'contract_version':'weather_daily_series_v1','time_standard':'UTC',
                'date_semantics':'Each date labels the UTC daily aggregation period; end date inclusive.', 'variables':rows},
            'result':{'data_family':'weather_timeseries','processing_version':PROCESSING,'evidence_kind':'modelled_reanalysis',
                'source_model':'MERRA-2','source_api_version':header['api']['version'],'publisher_release_id':None,
                'requested_point':request.point,'provider_point':value['geometry'],
                'native_grid_cell_id':None,'nominal_source_grid_degrees':{'latitude':0.5,'longitude':0.625},
                'spatial_semantics':'Coarse source-grid meteorology returned for an explicit query point; not a measured point or polygon average.',
                'start_date':request.start_date,'end_date':request.end_date,'time_standard':'UTC','variables':coverage,
                'completeness':'bounded_response_with_explicit_daily_missingness',
                'time_semantics':'Historical UTC daily model aggregates; capture time and source API version are separate from weather dates.'}}
    except AcquisitionError:
        raise
    except (KeyError,TypeError,ValueError,IndexError) as exc:
        raise AcquisitionError('weather_response_schema_changed') from exc


def fetch_weather(request, *, client=None, artifacts=None, diagnostics=None):
    from backend.acquisition_sources import BoundedClient
    artifacts = artifacts if artifacts is not None else {}
    diagnostics = diagnostics if diagnostics is not None else {}
    if calendar_date(request.end_date) > datetime.now(timezone.utc).date()-timedelta(days=LIMITS['minimum_age_days']):
        raise AcquisitionError('weather_period_not_mature')
    reader=BoundedClient(client,max_response=LIMITS['max_response_bytes'],max_total=LIMITS['max_total_bytes'],
                         seconds=LIMITS['network_deadline_seconds'],request_timeout=LIMITS['request_timeout_seconds'])
    try:
        before=reader.get_bytes(ENDPOINT,parameters(request))
        artifacts['provider_response_before']=BinaryArtifact(before,'application/octet-stream')
        normalized=normalize(decode(before),request)
        after=reader.get_bytes(ENDPOINT,parameters(request))
        artifacts['provider_response_after']=BinaryArtifact(after,'application/octet-stream')
        # Runtime timing fields may differ; all evidence and source metadata must agree.
        if normalized != normalize(decode(after),request):
            raise AcquisitionError('source_changed_during_capture')
        artifacts.update(normalized)
        return normalized['result']
    finally:
        diagnostics['responses']=reader.responses
        diagnostics['decoded_bytes_received']=reader.bytes_received
        reader.close()


def validate_retained(request, manifest, references, load):
    required={'provider_response_before','provider_response_after','source_metadata','series','result'}
    if set(references) != required:
        raise AcquisitionError('integrity_failure')
    for name in ('provider_response_before','provider_response_after'):
        if references[name].get('media_type') != 'application/octet-stream':
            raise AcquisitionError('integrity_failure')
        replay=normalize(decode(load(manifest['artifacts'][name])),request)
        if replay['result'] != manifest['result']:
            raise AcquisitionError('integrity_failure')
        for key in ('source_metadata','series','result'):
            if replay[key] != load(manifest['artifacts'][key]):
                raise AcquisitionError('integrity_failure')
    return required
