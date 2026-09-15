"""Offline weather replay and fresh one-day provider comparisons; no evidence writes."""
from backend import core, acquisition as service, acquisition_weather as weather
from backend.acquisition_contracts import AcquisitionError, parse_request
from backend.acquisition_sources import BoundedClient


def verify_weather(org, summary, *, live=True, client=None):
    if summary['state'] != 'succeeded' or summary['request']['adapter_version'] != weather.ADAPTER:
        raise AcquisitionError('successful_weather_capture_required')
    request=parse_request(summary['request'])
    # Shared integrity read replays both retained original responses.
    checked=service.read_acquisition(org,summary['acquisition_id'],attempt_id=summary['attempt_id'])
    if checked != summary:
        raise AcquisitionError('integrity_failure')
    series=service.read_acquisition_artifact(org,summary['acquisition_id'],'series',attempt_id=summary['attempt_id'])
    metadata=service.read_acquisition_artifact(org,summary['acquisition_id'],'source_metadata',attempt_id=summary['attempt_id'])
    first=weather.calendar_date(request.start_date);last=weather.calendar_date(request.end_date)
    dates=sorted({first,first+(last-first)//2,last})
    reader=BoundedClient(client,max_response=1_000_000,max_total=3_000_000,seconds=150,request_timeout=45) if live else None
    samples=[]
    try:
        if live:
            for day in dates:
                sample_request=weather.WeatherRequest.model_validate({**request.model_dump(),'start_date':day.isoformat(),'end_date':day.isoformat()})
                raw=reader.get_bytes(weather.ENDPOINT,weather.parameters(sample_request))
                normalized=weather.normalize(weather.decode(raw),sample_request)
                expected_metadata={**metadata,'header':{**metadata['header'],'start':day.strftime('%Y%m%d'),'end':day.strftime('%Y%m%d')}}
                if normalized['source_metadata'] != expected_metadata:
                    raise AcquisitionError('weather_provider_changed_since_capture')
                for column in normalized['series']['variables']:
                    saved=next(v for v in series['variables'] if v['variable']==column['variable'])
                    expected=next(v for v in saved['daily'] if v['date']==day.isoformat())
                    if column['daily'] != [expected]:
                        raise AcquisitionError('independent_weather_sample_mismatch')
                    samples.append({'variable':column['variable'],'unit':column['unit'],**expected,'independent_match':True})
        return {'verification_version':'weather_daily_verification_v1','verified_at':core.now(),
                'acquisition_id':summary['acquisition_id'],'manifest_sha256':summary['manifest_sha256'],
                'offline_response_replay_match':True,'live_sample_match':True if live else None,'samples':samples,
                'independent_responses':reader.responses if live else [],
                'method':'Replays original responses and compares new one-day requests at first/middle/last dates across every variable.',
                'limits':'Same-provider consistency check; not independent station or scientific validation.'}
    finally:
        if reader: reader.close()
