"""Synthetic-only model/adapter fixtures; no live provider or real site scores."""
from copy import deepcopy
import math

import pytest
from pydantic import ValidationError
from backend.earth import EarthState, Observation, SpatialReference, Asset, VARIABLES, normalize_unit
from backend.adapters import normalize_findings, select_observations
from backend.derived import compute_features
from backend.wetland import run_wetland, model_spec

DATE = '2026-09-01T00:00:00+00:00'
JOB = {'site_id': 'synthetic-parcel', 'version': 1, 'created': DATE,
       'geometry': {'type': 'Polygon', 'coordinates': [[[-1.3,51.75],[-1.29,51.75],[-1.29,51.76],[-1.3,51.75]]]}}
FAVOURABLE = {
    'terrain.slope_deg': 0, 'soil.permeability': 0,
    'hydrology.mapped_flood_extent_fraction': 1, 'hydrology.distance_to_water_m': 0,
    'land_use.current_cover': 'arable', 'ecology.wetland_fraction': 0,
    'ecology.habitat_condition': 1, 'land_use.developed_fraction': 0,
    'human.infrastructure_fraction': 0, 'ecology.irreplaceable_habitat_fraction': 0,
    'ecology.distance_to_habitat_m': 0,
}


def obs(variable, value, **overrides):
    return Observation(**({
        'id': 'synthetic:'+variable, 'variable': variable, 'value': value, 'unit': VARIABLES[variable][0],
        'source': 'SYNTHETIC TEST SURVEY', 'source_dataset': 'Synthetic fixture', 'source_version': 'fixture-1',
        'timestamp': DATE, 'retrieved_at': DATE,
        'spatial': SpatialReference(geometry_or_cell_reference='synthetic-parcel/boundary/1', spatial_resolution_m=1),
        'method': 'Synthetic fixture only', 'observed_or_derived': 'observed',
        'epistemic_status': 'observed' if value is not None else 'unknown',
        'confidence': .9 if value is not None else 0, 'uncertainty': 'Synthetic; no actual measurement.',
        'missing_reason': 'Synthetic missing input' if value is None else None,
        'raw_source_ids': ['synthetic-source'], 'synthetic': True,
    } | overrides))


def state(values=None):
    result = EarthState(location_id=JOB['site_id'], boundary_version=1, geography='England', as_of=DATE, geometry=JOB['geometry'])
    select_observations(result, [(100, obs(k,v)) for k,v in (FAVOURABLE if values is None else values).items()])
    return compute_features(result)


def score(values=None, key='physical_potential'):
    return next(c for c in run_wetland(state(values))['components'] if c['key'] == key)


def finding(key='flood', percent=70, **overrides):
    return {'key': key, 'dataset': 'Synthetic '+key, 'dataset_version': key+'-1',
            'source_url': 'https://example.invalid/synthetic', 'retrieved': DATE,
            'coverage': 'covered', 'percent': percent, 'method': 'synthetic-overlay',
            'limitations': 'Synthetic source', 'synthetic': True} | overrides


def test_adapter_canonical_mapping_and_provenance():
    raw = finding()
    saved = deepcopy(raw)
    s = normalize_findings(JOB, [raw, finding('sssi', 20)])
    flood = s.get('hydrology.mapped_flood_extent_fraction')
    assert flood.value == pytest.approx(.7)
    assert flood.unit == 'fraction'
    assert flood.raw_source_ids == ['flood-1']
    assert flood.source_version == 'flood-1' and flood.timestamp is None
    assert flood.spatial.geometry_or_cell_reference == 'synthetic-parcel/boundary/1'
    assert s.get('hydrology.floodplain_probability') is None
    assert s.get('regulatory.protected_area_fraction').value == pytest.approx(.2)
    assert raw == saved
    roundtrip = EarthState.model_validate_json(s.model_dump_json())
    assert roundtrip.get(flood.variable) == flood


@pytest.mark.parametrize('variable,value,unit,expected', [
    ('soil.clay_fraction', 25, '%', .25),
    ('hydrology.distance_to_water_m', .4, 'km', 400),
    ('terrain.slope_deg', math.pi/6, 'radian', 30),
    ('hydrology.flow_accumulation', 2, 'ha', 20000),
    ('climate.annual_precipitation_mm', .8, 'm/year', 800),
])
def test_unit_normalization(variable,value,unit,expected):
    converted = normalize_unit(value,unit,variable)
    assert obs(variable,converted).value == pytest.approx(expected)


def test_dimensionally_invalid_conversion_rejected():
    with pytest.raises(ValueError): normalize_unit(3, 'flood_zone', 'hydrology.floodplain_probability')
    with pytest.raises(ValueError): normalize_unit(20, '%', 'terrain.slope_deg')
    with pytest.raises(ValidationError): obs('terrain.slope_deg', 10, unit='radian')


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -1, 1.01])
def test_invalid_fractions_rejected(value):
    with pytest.raises(ValidationError): obs('ecology.wetland_fraction', value)


def test_unknown_requires_reason_and_zero_confidence():
    with pytest.raises(ValidationError): obs('soil.permeability',None,confidence=.9)
    with pytest.raises(ValidationError): obs('soil.permeability',None,missing_reason=None)


def test_missing_and_out_of_coverage_are_not_zero():
    for coverage in ('unknown','unavailable'):
        s=normalize_findings(JOB,[finding(coverage=coverage)])
        o=s.get('hydrology.mapped_flood_extent_fraction')
        assert o.value is None and o.confidence == 0 and o.missing_reason
        assert run_wetland(compute_features(s))['overall']['score'] is None
    assert normalize_findings(JOB,[finding(percent=0)]).get('hydrology.mapped_flood_extent_fraction').value == 0


def test_provider_fallback_and_all_candidates_retained():
    s=state({})
    preferred=obs('soil.permeability',None,id='national')
    fallback=obs('soil.permeability',.3,id='global',source_version='global-v1')
    select_observations(s,[(100,preferred),(10,fallback)])
    assert s.get('soil.permeability').id == 'global'
    assert len(s.normalized['soil']['permeability']) == 2
    assert preferred.missing_reason


def test_woodland_incomplete_absence_never_erases_known_habitat():
    s=normalize_findings(JOB,[finding('woodland',70),finding('woodland_revised',0)])
    assert s.get('ecology.irreplaceable_habitat_fraction').value == pytest.approx(.7)
    s=normalize_findings(JOB,[finding('woodland',70),finding('woodland_revised',40)])
    assert s.get('ecology.irreplaceable_habitat_fraction').value == pytest.approx(.7)
    s=normalize_findings(JOB,[finding('woodland',0),finding('woodland_revised',0)])
    assert s.get('ecology.irreplaceable_habitat_fraction').value is None


def test_derived_lineage_and_quality_survive_serialization():
    s=state()
    derived=s.get('hydrology.water_context_index')
    assert derived.source == 'CRC' and derived.observed_or_derived == 'derived'
    assert derived.input_ids == ['synthetic:hydrology.mapped_flood_extent_fraction','synthetic:hydrology.distance_to_water_m']
    assert derived.raw_source_ids == ['synthetic-source']
    assert derived.synthetic and derived.confidence < .9
    assert EarthState.model_validate_json(s.model_dump_json()).derived == s.derived


def test_empty_model_deterministic_and_unknown():
    s=state({})
    a=run_wetland(s)
    assert a == run_wetland(s)
    assert a['overall']['band'] == 'INSUFFICIENT_DATA'
    assert a['overall']['score'] is None and a['overall']['confidence'] == 0
    assert all(c['score'] is None for c in a['components'] if c['key'] != 'data_confidence')


def test_favourable_conditions_score_well():
    result=run_wetland(state())
    assert result == run_wetland(state())
    assert result['overall']['band'] == 'HIGH'
    assert result['overall']['score'] == 70
    assert result['synthetic'] and result['predicted_future_state'] is None


def test_steep_permeable_distant_conditions_score_poorly():
    bad=FAVOURABLE | {'terrain.slope_deg': 30,'soil.permeability':1,
                       'hydrology.distance_to_water_m':2000,'hydrology.mapped_flood_extent_fraction':0,
                       'ecology.distance_to_habitat_m':2000}
    result=run_wetland(state(bad))
    assert score(bad)['score'] == 0
    assert result['overall']['score'] == 0 and result['overall']['band'] == 'LOW'


def test_slope_and_permeability_sensitivity():
    baseline=score()['score']
    assert score(FAVOURABLE | {'terrain.slope_deg':8})['score'] < baseline
    assert score(FAVOURABLE | {'soil.permeability':.9})['score'] < baseline
    assert score(FAVOURABLE | {'terrain.elevation_m':1000})['score'] == baseline


def test_pristine_existing_wetland_has_no_restoration_need():
    pristine=FAVOURABLE | {'land_use.current_cover':'wetland','ecology.wetland_fraction':1,'ecology.habitat_condition':1}
    assert score(pristine)['score'] == 100
    assert score(pristine,'restoration_need')['score'] == 0
    assert run_wetland(state(pristine))['overall']['band'] == 'LOW'
    degraded=pristine | {'ecology.habitat_condition':.1}
    assert run_wetland(state(degraded))['overall']['score'] > run_wetland(state(pristine))['overall']['score']


def test_condition_only_required_for_existing_wetland():
    no_condition={k:v for k,v in FAVOURABLE.items() if k!='ecology.habitat_condition'}
    r=run_wetland(state(no_condition))
    assert r['overall']['band'] == 'HIGH'
    assert not any(g['variable']=='ecology.habitat_condition' for g in r['missing_inputs'])
    wet=no_condition | {'land_use.current_cover':'wetland','ecology.wetland_fraction':1}
    assert run_wetland(state(wet))['overall']['band'] == 'INSUFFICIENT_DATA'


def test_derived_partial_coverage_blocks_overall_and_is_visible():
    partial={k:v for k,v in FAVOURABLE.items() if k!='hydrology.distance_to_water_m'}
    r=run_wetland(state(partial))
    hydro=next(c for c in r['components'] if c['key']=='hydrological_relevance')
    assert hydro['score'] == 100 and hydro['coverage'] == .5 and hydro['status']=='partial'
    assert 'hydrology.distance_to_water_m' in hydro['missing_inputs']
    assert r['overall']['band'] == 'INSUFFICIENT_DATA'


def test_development_and_disjoint_constraints_are_not_optimistic():
    developed=FAVOURABLE | {'land_use.developed_fraction':1}
    assert run_wetland(state(developed))['overall']['score'] == 0
    disjoint=FAVOURABLE | {'land_use.developed_fraction':.34,'human.infrastructure_fraction':.33,'ecology.irreplaceable_habitat_fraction':.33}
    assert score(disjoint,'implementation_feasibility')['score'] == 0


def test_semi_natural_habitats_are_not_treated_as_conversion_opportunity():
    natural=FAVOURABLE | {'land_use.current_cover':'semi_natural_grassland'}
    assert run_wetland(state(natural))['overall']['score'] is None


def test_sssi_is_review_flag_not_benefit_or_automatic_exclusion():
    original=run_wetland(state())
    protected=run_wetland(state(FAVOURABLE | {'regulatory.protected_area_fraction':1}))
    assert original['overall']['score'] == protected['overall']['score']
    assert any('protected-area' in flag for flag in protected['review_flags'])


def test_quality_degrades_for_coarse_or_undated_sources():
    a=state(); b=state()
    for o in b.observations():
        if o.source!='CRC':
            o.timestamp=None
            o.spatial.spatial_resolution_m=250
    compute_features(b)
    assert run_wetland(b)['overall']['confidence'] < run_wetland(a)['overall']['confidence']


def test_config_is_explicit_pinned_and_versioned():
    spec=model_spec(); modified=deepcopy(spec['config']); modified['slope_zero_score_deg']=5
    s=state(FAVOURABLE | {'terrain.slope_deg':5})
    alternate=model_spec(modified)
    assert run_wetland(s,alternate)['overall']['score'] < run_wetland(s,spec)['overall']['score']
    assert spec['signature'] != alternate['signature']
    with pytest.raises(ValueError): run_wetland(s,spec | {'model_version':'invented'})
    with pytest.raises(ValueError): model_spec(modified | {'high_threshold':101})
    with pytest.raises(ValueError): model_spec(modified | {'slope_zero_score_deg':float('nan')})


def test_geography_guard_and_temporal_snapshots():
    s=state(); s.geography='Brazil'
    assert run_wetland(s)['overall']['band']=='INSUFFICIENT_DATA'
    a=state(); b=state(); b.boundary_version=2
    assert run_wetland(a)['state_fingerprint'] != run_wetland(b)['state_fingerprint']
    assert run_wetland(a)['model_version']=='wetland_restoration_v0_1'


def test_native_assets_preserve_resolution_and_crs():
    asset=Asset(href='private://dem.tif',media_type='image/tiff; application=geotiff; profile=cloud-optimized',
                roles=['data'],crs='EPSG:27700',spatial_resolution_m=1,stac_item_href='https://example.invalid/item.json')
    assert Asset.model_validate_json(asset.model_dump_json()).spatial_resolution_m==1
