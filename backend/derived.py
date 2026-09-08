"""Small, explicit parcel-scale CRC features with full input lineage."""
from backend.earth import EarthState, Observation, SpatialReference, VARIABLES, fingerprint

FEATURE_VERSION = 'crc_wetland_features_v0_1_1'

# Explicit ordinal screening priors, never a measured permeability coefficient.
DRAINAGE_RETENTION = {'very_poorly_drained': 1, 'poorly_drained': .85,
                     'imperfectly_drained': .65, 'moderately_well_drained': .4,
                     'well_drained': .2, 'excessively_drained': 0}


def quality(o: Observation, as_of=None) -> float:
    if o.value is None:
        return 0
    # Already computed quality for derived CRC features; do not discount twice.
    if o.source == 'CRC':
        return o.confidence
    resolution_factor = (.75 if o.spatial.spatial_resolution_m is None else
                         1 if o.spatial.spatial_resolution_m <= 10 else
                         .85 if o.spatial.spatial_resolution_m <= 30 else .6)
    date_factor = .75 if o.timestamp is None else 1
    if o.timestamp is not None and as_of is not None:
        years = max(0, (as_of-o.timestamp).total_seconds()/(365.25*86400))
        date_factor = 1 if years <= 2 else .8 if years <= 5 else .6
    return o.confidence * resolution_factor * date_factor


def derive(state: EarthState, variable: str, inputs: list[str], calculate, method: str,
           uncertainty: str, allow_partial=False, inference_quality=1):
    records = [state.get(v) for v in inputs]
    available = [o for o in records if o is not None and o.value is not None]
    values = {o.variable: o.value for o in available}
    complete = len(available) == len(inputs)
    value = calculate(values) if available and (complete or allow_partial) else None
    missing = [v for v, o in zip(inputs, records) if o is None or o.value is None]
    reason = ('Missing inputs: ' + ', '.join(missing)) if missing else 'Existing cover or habitat state is not interpretable by this model.'
    times = {o.timestamp for o in available}
    resolutions = [o.spatial.spatial_resolution_m for o in available]
    known_records = [o for o in records if o is not None]
    observation = Observation(
        id=fingerprint([FEATURE_VERSION, state.location_id, state.boundary_version, variable,
                        [o.id for o in known_records], value]),
        variable=variable, value=value, unit=VARIABLES[variable][0], source='CRC',
        source_dataset='CRC derived environmental features', source_version=FEATURE_VERSION,
        timestamp=next(iter(times)) if len(times) == 1 else None, retrieved_at=state.as_of,
        spatial=SpatialReference(
            geometry_or_cell_reference=f'{state.location_id}/boundary/{state.boundary_version}',
            spatial_resolution_m=max(resolutions) if resolutions and all(r is not None for r in resolutions) else None,
            aggregation='Parcel summary; native sources are not resampled'),
        method=method, observed_or_derived='derived', epistemic_status='inferred' if value is not None else 'unknown',
        confidence=(sum(quality(o, state.as_of) for o in available) / len(inputs) * inference_quality) if value is not None else 0,
        uncertainty=uncertainty + (' Missing: ' + ', '.join(missing) + '.' if missing else ''),
        input_ids=[o.id for o in known_records],
        input_coverage=sum(o.input_coverage for o in available)/len(inputs) if value is not None else 0,
        missing_input_variables=missing,
        raw_source_ids=sorted({sid for o in known_records for sid in o.raw_source_ids}),
        missing_reason=reason if value is None else None, synthetic=any(o.synthetic for o in known_records),
    )
    state.derived[variable] = observation


def compute_features(state: EarthState) -> EarthState:
    permeability = state.get('soil.permeability')
    numeric = permeability is not None and permeability.value is not None
    soil_input = 'soil.permeability' if numeric else 'soil.drainage_class'
    derive(state, 'soil.retention_index', [soil_input],
           lambda v: 1-v[soil_input] if numeric else DRAINAGE_RETENTION.get(v[soil_input]),
           '1 - explicitly normalized permeability, when available; otherwise ordinal drainage-class screening prior: ' + str(DRAINAGE_RETENTION),
           'An uncalibrated retention heuristic. Categorical drainage is not hydraulic conductivity, a measured permeability coefficient, groundwater depth or a water-supply assessment.',
           inference_quality=1 if numeric else .6)
    water = ['hydrology.mapped_flood_extent_fraction', 'hydrology.distance_to_water_m']
    derive(state, 'hydrology.water_context_index', water,
           lambda v: sum(v[k] if k == water[0] else max(0, 1-v[k]/1000) for k in v)/len(v),
           'Mean of mapped flood extent fraction and max(0, 1 - distance_to_water_m / 1000); available terms only',
           'A water-context proxy, not hydrological connectivity, annual flood probability, hydroperiod or flood reduction. Distance alone does not establish a water supply.',
           allow_partial=True, inference_quality=.6)

    def need(v):
        cover, wet = v['land_use.current_cover'], v['ecology.wetland_fraction']
        base = {'arable': .7, 'improved_grassland': .6, 'wetland': 0}.get(cover)
        if base is None or (cover == 'wetland' and wet < .95):
            return None
        return (1-wet)*base + wet*(1-v.get('ecology.habitat_condition', 0))
    need_inputs = ['land_use.current_cover', 'ecology.wetland_fraction']
    wetland = state.get('ecology.wetland_fraction')
    if wetland is None or wetland.value != 0:
        need_inputs.append('ecology.habitat_condition')
    derive(state, 'ecology.restoration_need_index',
           need_inputs, need,
           '(1 - wetland_fraction) × managed-cover prior + wetland_fraction × (1 - habitat_condition); priors: arable 0.70, improved_grassland 0.60, wetland 0',
           'Habitat condition refers to the existing wetland portion. Managed-cover priors are uncalibrated opportunity assumptions, not observations of degradation. Other cover types require ecological review.',
           inference_quality=.6)

    derive(state, 'ecology.habitat_proximity_index', ['ecology.distance_to_habitat_m'],
           lambda v: max(0, 1-v['ecology.distance_to_habitat_m']/1000),
           'max(0, 1 - distance_to_habitat_m / 1000)',
           'Euclidean proximity to relevant wetland habitat is not functional habitat connectivity or a biodiversity gain estimate.', inference_quality=.6)

    derive(state, 'human.unblocked_area_index',
           ['land_use.developed_fraction', 'human.infrastructure_fraction', 'ecology.irreplaceable_habitat_fraction'],
           lambda v: max(0, 1-sum(v.values())),
           'max(0, 1 - developed_fraction - infrastructure_fraction - irreplaceable_habitat_fraction)',
           'Conservative lower bound on area free of these mapped constraints; overlapping constraint categories may be counted twice and depress the score. This is not a measured feasible area. No tenure, consent, utility, heritage, water-quality or cost feasibility is established.',
           inference_quality=.7)
    return state
