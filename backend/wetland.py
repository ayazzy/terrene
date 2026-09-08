"""Deterministic, uncalibrated lowland wetland restoration screening, v0.1."""
from copy import deepcopy
import math
import os

from backend.earth import EarthState, fingerprint
from backend.derived import quality, FEATURE_VERSION
from backend.adapters import ADAPTER_VERSION

MODEL_VERSION = 'wetland_restoration_v0_1'
DEFAULT_CONFIG = {
    'physical_weights': {'terrain.slope_deg': .35, 'soil.retention_index': .30,
                         'hydrology.water_context_index': .35},
    'potential_weights': {'physical_potential': .7, 'hydrological_relevance': .2,
                          'ecological_opportunity': .1},
    'slope_zero_score_deg': 10,
    'high_threshold': 65,
    'moderate_threshold': 35,
}
LIMITATIONS = (
    'Unvalidated first-pass suitability heuristic for lowland wetland restoration in England. '
    'Scores are relative indices, not probabilities, predicted outcomes or investment advice. '
    'Site hydrology, reliable water supply, water quality, drainage, groundwater, seasonal variation '
    'and habitat condition require field assessment. This model does not establish flood reduction, '
    'BNG units, legal clearance or an intervention design. It is not suitable for every wetland type.'
)


def model_spec(config=None, environment_version='configured', refresh_sources=False):
    config = deepcopy(DEFAULT_CONFIG if config is None else config)
    if set(config) != set(DEFAULT_CONFIG):
        raise ValueError('Model configuration keys must match v0.1')
    for group in ('physical_weights', 'potential_weights'):
        if set(config[group]) != set(DEFAULT_CONFIG[group]):
            raise ValueError('Model weight variables must match v0.1')
        if any(not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 for v in config[group].values()):
            raise ValueError('All weights must be finite and positive')
    for key in ('slope_zero_score_deg', 'high_threshold', 'moderate_threshold'):
        if not isinstance(config[key], (int, float)) or not math.isfinite(config[key]):
            raise ValueError('Thresholds must be finite numbers')
    if not 0 < config['slope_zero_score_deg'] <= 90 or not 0 <= config['moderate_threshold'] < config['high_threshold'] <= 100:
        raise ValueError('Invalid model thresholds')
    if environment_version == 'configured':
        environment_version = None if os.getenv('CRC_ENVIRONMENT_ACQUISITION') == 'disabled' else 'crc_england_real_inputs_v1'
    if environment_version not in (None, 'crc_england_real_inputs_v1'):
        raise ValueError('Unsupported environmental acquisition version')
    if not isinstance(refresh_sources, bool):
        raise ValueError('refresh_sources must be boolean')
    spec = {'model_version': MODEL_VERSION, 'adapter_version': ADAPTER_VERSION,
            'feature_version': FEATURE_VERSION,
            'environment_version': environment_version,
            'refresh_sources': refresh_sources,
            'config': config}
    return spec | {'signature': fingerprint(spec)}


def component(state, key, label, weights, transformations, rule):
    inputs, available, missing = [], [], []
    covered_weight = 0
    all_complete = True
    total = sum(weights.values())
    for variable, weight in weights.items():
        observation = state.get(variable)
        known = observation is not None and observation.value is not None
        if not known or observation.input_coverage < 1:
            all_complete = False
        term = transformations[variable](observation.value) if known else None
        if known:
            available.append((weight, term, quality(observation, state.as_of)))
            covered_weight += weight * observation.input_coverage
            missing.extend(observation.missing_input_variables)
        else:
            missing.append(variable)
        inputs.append({'variable': variable, 'observation_id': observation.id if observation else None,
                       'value': observation.value if observation else None,
                       'unit': observation.unit if observation else None,
                       'source': observation.source if observation else None,
                       'source_dataset': observation.source_dataset if observation else None,
                       'source_version': observation.source_version if observation else None,
                       'source_url': observation.source_url if observation else None,
                       'weight': weight, 'transformed_score': round(term*100, 2) if term is not None else None,
                       'confidence': round(quality(observation, state.as_of), 4) if known else 0,
                       'missing_reason': (observation.missing_reason if observation else 'No registered source observation.') if not known else None})
    used = sum(w for w, _, _ in available)
    return {'key': key, 'label': label,
            'score': round(100*sum(w*v for w, v, _ in available)/used, 1) if used else None,
            'coverage': 1.0 if all_complete else min(math.nextafter(1.0, 0.0), covered_weight/total),
            'confidence': round(sum(w*q for w, _, q in available)/total, 4),
            'status': 'unknown' if not available else 'partial' if missing or not all_complete else 'modelled',
            'rule': rule, 'inputs': inputs, 'missing_inputs': missing}


def run_wetland(state: EarthState, spec=None):
    spec = deepcopy(spec or model_spec())
    expected = model_spec(spec.get('config'), environment_version=spec.get('environment_version'), refresh_sources=spec.get('refresh_sources', False))
    if spec != expected:
        raise ValueError('Pinned model, feature or adapter version is unsupported; use its matching worker')
    cfg = spec['config']
    physical = component(state, 'physical_potential', 'Wetland physical potential', cfg['physical_weights'],
                         {'terrain.slope_deg': lambda v: max(0, 1-v/cfg['slope_zero_score_deg']),
                          'soil.retention_index': lambda v: v,
                          'hydrology.water_context_index': lambda v: v},
                         f'Weighted mean of max(0, 1 - slope / {cfg["slope_zero_score_deg"]}°), explicit soil-retention heuristic, and water-context index. Available weights renormalized; missing inputs lower confidence.')
    single = [
        ('restoration_need', 'Current restoration need', 'ecology.restoration_need_index'),
        ('hydrological_relevance', 'Hydrological relevance', 'hydrology.water_context_index'),
        ('ecological_opportunity', 'Ecological opportunity', 'ecology.habitat_proximity_index'),
        ('implementation_feasibility', 'Implementation feasibility', 'human.unblocked_area_index'),
    ]
    components = [physical]
    for key, label, variable in single:
        feature = state.get(variable)
        components.append(component(state, key, label, {variable: 1}, {variable: lambda v: v},
                                    '100 × ' + variable + '. ' + (feature.method if feature else 'Feature unavailable.')))
    by_key = {c['key']: c for c in components}
    gaps = []
    # Report original missing measurements, not only the missing derived index.
    soil = state.get('soil.permeability')
    soil_variable = 'soil.permeability' if soil is not None and soil.value is not None else 'soil.drainage_class'
    required = ['terrain.slope_deg', soil_variable, 'hydrology.distance_to_water_m',
                'hydrology.mapped_flood_extent_fraction', 'land_use.current_cover',
                'ecology.wetland_fraction', 'ecology.habitat_condition',
                'land_use.developed_fraction', 'human.infrastructure_fraction',
                'ecology.irreplaceable_habitat_fraction', 'ecology.distance_to_habitat_m']
    wetland = state.get('ecology.wetland_fraction')
    if wetland is not None and wetland.value == 0:
        required.remove('ecology.habitat_condition')
    for variable in required + ['hydrology.groundwater_depth_m', 'climate.annual_precipitation_mm',
                                 'hydrology.flow_accumulation', 'regulatory.protected_area_fraction',
                                 'terrain.elevation_m']:
        o = state.get(variable)
        if o is None or o.value is None:
            gaps.append({'variable': variable, 'reason': o.missing_reason if o else 'No source connected for this parcel.',
                         'role': 'scored input' if variable in required else 'unassessed context'})
    reviews = ['Confirm reliable water supply, hydroperiod, drainage and water quality.',
               'Check tenure, utilities, heritage, access, consents and off-site effects.']
    development = state.get('land_use.developed_fraction')
    if development and development.value is not None and development.value > .5:
        reviews.append('More than half the parcel is classified as built-up by the mapped source. Major development is an intervention constraint; inspect the dated classification and actual infrastructure footprint.')
    protected = state.get('regulatory.protected_area_fraction')
    if protected and protected.value is not None and protected.value > 0:
        reviews.append('Mapped protected-area overlap: ecological objectives and consents require review. Designation is not a benefit score or an automatic exclusion.')
    woodland = state.get('ecology.irreplaceable_habitat_fraction')
    if woodland and woodland.value is not None and woodland.value > 0:
        reviews.append('Known irreplaceable habitat overlaps this parcel. Avoid conversion; review the proposed intervention footprint with an ecologist.')
    required_components = ['physical_potential', 'restoration_need', 'implementation_feasibility']
    blocked = [by_key[k]['label'] for k in required_components if by_key[k]['score'] is None or by_key[k]['coverage'] < 1]
    if state.geography != 'England':
        blocked.append('Geography outside the model implementation (England)')
    score = None
    if not blocked:
        terms = [(w, by_key[k]['score']) for k, w in cfg['potential_weights'].items() if by_key[k]['score'] is not None]
        potential = sum(w*s for w, s in terms)/sum(w for w, _ in terms)
        score = round(potential * by_key['restoration_need']['score']/100 * by_key['implementation_feasibility']['score']/100, 1)
    band = ('INSUFFICIENT_DATA' if score is None else 'HIGH' if score >= cfg['high_threshold'] else
            'MODERATE' if score >= cfg['moderate_threshold'] else 'LOW')
    # Confidence is evidence completeness/quality, never predicted model accuracy.
    confidence = round(sum(quality(state.get(v), state.as_of) if state.get(v) else 0 for v in required)/len(required), 4)
    used_known = sum(state.get(v) is not None and state.get(v).value is not None for v in required)
    confidence_component = {
        'key': 'data_confidence', 'label': 'Data support (legacy combined index)', 'score': round(confidence*100, 1),
        'confidence': confidence, 'coverage': round(used_known/len(required), 4),
        'status': 'partial' if used_known < len(required) else 'inferred',
        'rule': f'Mean of quality-adjusted source confidence across {len(required)} applicable scored measurements; missing = 0. Wetland condition is not required when wetland fraction is zero. Resolution: ≤10m ×1, ≤30m ×0.85, coarser ×0.6, unknown ×0.75. Unknown observation date ×0.75; known age ≤2 years ×1, ≤5 years ×0.8, older ×0.6, relative to saved state time. This measures data support, not scientific validation.',
        'inputs': [{'variable': v, 'observation_id': state.get(v).id if state.get(v) else None,
                    'value': state.get(v).value if state.get(v) else None,
                    'source': state.get(v).source if state.get(v) else None,
                    'confidence': round(quality(state.get(v), state.as_of), 4) if state.get(v) else 0} for v in required],
        'missing_inputs': [g['variable'] for g in gaps if g['role'] == 'scored input'],
    }
    available_quality = [quality(state.get(v), state.as_of) for v in required if state.get(v) is not None and state.get(v).value is not None]
    data_quality = sum(available_quality)/len(available_quality) if available_quality else None
    gating = [v for v in required if v != 'ecology.distance_to_habitat_m']
    gating_known = sum(state.get(v) is not None and state.get(v).value is not None for v in gating)
    # This heuristic has no empirical predictive calibration, even with complete coverage.
    evidence = {'data_coverage': {'available': used_known, 'required': len(required),
                                'fraction': round(used_known/len(required), 4), 'variables': required},
                'gating_coverage': {'available': gating_known, 'required': len(gating),
                                    'fraction': gating_known/len(gating), 'variables': gating,
                                    'meaning': 'Inputs required for an overall ranking. Availability alone does not establish interpretable categories or complete spatial coverage.'},
                'data_quality': {'index': round(data_quality, 4) if data_quality is not None else None,
                                 'label': 'UNKNOWN' if data_quality is None else 'HIGH' if data_quality >= .8 else 'MODERATE' if data_quality >= .5 else 'LOW',
                                 'meaning': 'Heuristic source quality among available inputs; resolution, observation date and source judgement. Not measured accuracy.'},
                'model_confidence': {'label': 'UNVALIDATED',
                                     'meaning': 'No calibrated predictive confidence or statistical interval. Categories are screening hypotheses.'}}
    for c in components:
        c['band'] = category(c['score'], cfg)
        c['supporting_evidence'] = [f"{i['variable']}: {i['value']} {i.get('unit') or ''}" for i in c['inputs'] if i['value'] is not None]
    physical['supporting_evidence'] = []
    for variable, label, unit in [('terrain.slope_deg', 'Mean terrain slope', '°'),
                                  ('hydrology.distance_to_water_m', 'Nearest mapped watercourse', ' m'),
                                  ('hydrology.mapped_flood_extent_fraction', 'Mapped flood-zone overlap', ' of parcel'),
                                  (soil_variable, 'Soil evidence', '')]:
        o = state.get(variable)
        if o is not None and o.value is not None:
            value = f'{o.value:.2f}' if isinstance(o.value, (float, int)) else o.value.replace('_', ' ')
            physical['supporting_evidence'].append(f'{label}: {value}{unit}')
    return spec | {
        'evidence_summary': evidence,
        'current_state': {v: {'value': state.get(v).value if state.get(v) else None,
                              'observation_id': state.get(v).id if state.get(v) else None,
                              'timestamp': state.get(v).timestamp.isoformat() if state.get(v) and state.get(v).timestamp else None}
                          for v in ('land_use.current_cover', 'ecology.mapped_wetland_fraction',
                                    'ecology.wetland_fraction', 'ecology.habitat_condition')},
        'schema_version': state.schema_version, 'state_as_of': state.as_of.isoformat(),
        'boundary_version': state.boundary_version,
        'state_fingerprint': fingerprint(state.model_dump(mode='json')),
        'epistemic_status': 'unknown' if score is None else 'modelled',
        'components': components + [confidence_component],
        'overall': {'score': score, 'band': band, 'confidence': confidence,
                    'confidence_label': 'HIGH' if confidence >= .8 else 'MODERATE' if confidence >= .5 else 'LOW',
                    'rule': 'Weighted mean of physical potential, hydrological relevance and ecological opportunity (available terms only) × restoration need / 100 × feasibility / 100. Requires complete physical, need and feasibility components. High ≥65, moderate ≥35 by default; configuration retained.',
                    'blocking_gaps': blocked, 'input_components': [c['key'] for c in components]},
        'missing_inputs': gaps, 'review_flags': reviews, 'limitations': LIMITATIONS,
        'synthetic': any(o.synthetic for o in state.observations()),
        'predicted_future_state': None,
    }


def category(value, config=None):
    """Uncalibrated descriptive bands; component coverage is always reported separately."""
    config = config or DEFAULT_CONFIG
    return ('INSUFFICIENT_DATA' if value is None else 'VERY_HIGH' if value >= 85 else
            'HIGH' if value >= config['high_threshold'] else 'MODERATE' if value >= config['moderate_threshold'] else
            'LOW' if value >= 15 else 'VERY_LOW')
