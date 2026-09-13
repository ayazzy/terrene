"""Native PHI semantics, lineage, snapshot and wetland-separation checks."""
from copy import deepcopy
import json
import os
from pathlib import Path

from pyproj import Transformer
import pytest
from shapely.geometry import box, mapping, shape
from shapely.ops import transform
from sqlalchemy import create_engine, delete, insert, text

from backend import core
from backend import land_evidence_store as store
from backend.earth import fingerprint
from backend.land_evidence import (
    PHI_REGISTRY_VERSION,
    PriorityHabitatObservation,
    project_land_evidence,
)
from backend.priority_habitats import (
    CLASSIFICATION,
    LIMITATIONS,
    SCHEMA_VERSION,
    SERVICE_URL,
    normalize_properties,
    summarize_intersections,
    validate_service_metadata,
)
from backend.wetland import run_wetland
from backend.wetland_binding import bind_wetland_input
from synthetic_assessment import synthetic_assessment


REAL_ROOT = Path(__file__).parents[1] / 'data' / 'verification' / 'england-real-v1-final'
PORT_MEADOW = REAL_ROOT / 'port-meadow-after.json'
FORWARD = Transformer.from_crs(4326, 27700, always_xy=True).transform
BACKWARD = Transformer.from_crs(27700, 4326, always_xy=True).transform


def source_polygon(west, south, east, north):
    return mapping(transform(BACKWARD, box(west, south, east, north)))


def feature(object_id, uid, geometry, main, *, additional='', feature_code='',
            feature_description='', other=''):
    codes = [item[0] for item in main]
    names = [item[1] for item in main]
    return {
        'id': 'db-' + uid,
        'geometry': geometry,
        'properties': {
            'OBJECTID': object_id,
            'GlobalID': f'global-{uid}',
            'UID': uid,
            'MainHabs': ','.join(names),
            'HabCodes': ', '.join(codes),
            'FeatDesc': feature_description,
            'FeatCodes': feature_code,
            'OtherClass': other,
            'AddHabs': additional,
            'PrimSource': f'Synthetic geometry for deterministic test ({codes[0]})',
            'AreaHa': transform(FORWARD, shape(geometry)).area / 10000,
            'Version': 'Sep_25',
        },
    }


def synthetic_summary():
    parcel = source_polygon(450000, 210000, 450100, 210100)
    rows = [
        feature(1, 'PHID-LMEAD', source_polygon(450000, 210000, 450070, 210100),
                [('LMEAD', 'Lowland meadows')], additional='PONDS',
                other='Annex1(H6510)'),
        feature(2, 'PHID-DWOOD', source_polygon(450030, 210000, 450100, 210100),
                [('DWOOD', 'Deciduous woodland')]),
        feature(3, 'PHID-MULTI', source_polygon(450000, 210000, 450070, 210020),
                [('CFPGM', 'Coastal and floodplain grazing marsh'),
                 ('LMEAD', 'Lowland meadows')]),
    ]
    summary = summarize_intersections(parcel, rows, FORWARD, BACKWARD)
    summary.pop('union_geometry')
    return parcel, summary


def retained_payload():
    return json.loads(PORT_MEADOW.read_text())


def legacy_observation(payload, variable):
    state = payload['environmental_state']
    observations = [
        item
        for domain in state['normalized'].values()
        for group in domain.values()
        for item in group
    ] + list(state['derived'].values())
    return next(item for item in observations if item['variable'] == variable)


def with_phi(payload, summary=None, *, coverage='covered', storage=True):
    result = deepcopy(payload)
    dataset_id = 'phi-import-sep-25'
    finding = {
        'key': 'priority_habitats',
        'dataset': 'Priority Habitats Inventory (England)',
        'publisher': 'Natural England',
        'source_url': SERVICE_URL,
        'retrieved': '2026-09-08T12:00:00Z',
        'dataset_version': dataset_id,
        'source_release': 'Sep_25',
        'source_metadata_revision_date': '2025-10-01',
        'source_capture_end_date': '2025-09-10',
        'source_service_data_last_edit': '2025-10-23T12:36:23.345000+00:00',
        'coverage': coverage,
        'coverage_fraction': 1 if coverage == 'covered' else .5 if coverage == 'partial' else None,
        'limitations': LIMITATIONS,
        'attribution': '© Natural England 2025.',
        'licence': 'Open Government Licence v3.0.',
        'raw_sha256': 'a' * 64 if storage else None,
        'raw_storage_reference': f'reference/{dataset_id}/source.json' if storage else None,
        'raw_semantics': 'Assembled exhaustive authoritative features before repair.',
    }
    if summary is not None:
        finding['priority_habitats'] = deepcopy(summary)
    result['findings'].append(finding)
    return result


def phi_observations(projection):
    return [item for item in projection.observations
            if isinstance(item, PriorityHabitatObservation)]


def test_multiple_main_habitats_overlap_and_union_exactly_once():
    _, summary = synthetic_summary()
    by_code = {item['habitat_code']: item for item in summary['habitats']}
    assert by_code['LMEAD']['overlap_fraction'] == pytest.approx(.7, abs=1e-10)
    assert by_code['DWOOD']['overlap_fraction'] == pytest.approx(.7, abs=1e-10)
    assert by_code['CFPGM']['overlap_fraction'] == pytest.approx(.14, abs=1e-10)
    assert sum(item['overlap_fraction'] for item in by_code.values()) > 1
    assert summary['any_main_priority_habitat']['overlap_fraction'] == pytest.approx(1, abs=1e-10)
    # Additional PONDS is a may-be-present qualifier, never a mapped-area row.
    assert 'PONDS' not in by_code
    qualifier = next(item for item in summary['source_features']
                     if item['uid'] == 'PHID-LMEAD')
    assert qualifier['additional_habitat_codes'] == ['PONDS']


def test_native_projection_retains_measurements_release_and_feature_lineage():
    _, summary = synthetic_summary()
    projection = project_land_evidence(with_phi(synthetic_assessment(), summary))
    assert projection.identity.registry_version == PHI_REGISTRY_VERSION
    observations = phi_observations(projection)
    assert {item.dimensions.get('habitat_code') for item in observations
            if item.definition_id.endswith('mapped_overlap_fraction')
            and 'any_mapped' not in item.definition_id} == {'LMEAD', 'DWOOD', 'CFPGM'}
    union = next(item for item in observations if item.definition_id.endswith('any_mapped_overlap_fraction'))
    assert union.value.value == union.measurement.overlap_fraction
    assert union.measurement.mapped_intersection_area_ha / union.measurement.parcel_area_ha == pytest.approx(union.value.value)
    assert union.provenance.source_release == 'Sep_25'
    assert union.provenance.source_schema_version == SCHEMA_VERSION
    assert union.provenance.source_metadata_revision_date == '2025-10-01'
    assert union.provenance.source_capture_end_date == '2025-09-10'
    assert union.provenance.source_service_data_last_edit.isoformat() == '2025-10-23T12:36:23.345000+00:00'
    feature_ids = {item.id for item in projection.source_feature_references}
    assert set(union.source_feature_reference_ids) <= feature_ids
    meadow_feature = next(item for item in projection.source_feature_references
                          if item.source_feature_id == 'PHID-LMEAD')
    assert meadow_feature.additional_habitat_codes == ['PONDS']
    assert meadow_feature.other_classification == 'Annex1(H6510)'


def test_known_mapped_zero_is_not_unknown_or_ecological_absence():
    parcel = source_polygon(450000, 210000, 450100, 210100)
    rows = [feature(10, 'PHID-GQSIG', parcel,
                    [('GQSIG', 'Good quality semi improved grassland')],
                    additional='LMEAD')]
    summary = summarize_intersections(parcel, rows, FORWARD, BACKWARD)
    summary.pop('union_geometry')
    projection = project_land_evidence(with_phi(synthetic_assessment(), summary))
    union = next(item for item in phi_observations(projection)
                 if item.definition_id.endswith('any_mapped_overlap_fraction'))
    assert union.value.value == 0 and union.known_zero
    assert union.support.coverage_status == 'full'
    assert union.source_feature_reference_ids == []
    assert not any(item.definition_id == 'ecology.priority_habitat.mapped_overlap_fraction'
                   for item in phi_observations(projection))
    assert 'does not establish ecological absence' in union.limitations
    assert projection.source_feature_references[0].main_habitats[0].status == 'supporting_non_priority'


@pytest.mark.parametrize(
    ('coverage', 'storage', 'state', 'reason_code'),
    [
        ('unknown', False, 'unavailable', 'source_unavailable'),
        ('unknown', True, 'unavailable', 'outside_acquired_coverage'),
        ('partial', True, 'partial_coverage', 'partial_acquired_coverage'),
    ],
)
def test_unavailable_outside_and_partial_coverage_are_not_mapped_zero(
        coverage, storage, state, reason_code):
    projection = project_land_evidence(with_phi(
        synthetic_assessment(), coverage=coverage, storage=storage,
    ))
    assert not phi_observations(projection)
    gap = next(item for item in projection.gaps
               if item.definition_id == 'ecology.priority_habitat.any_mapped_overlap_fraction')
    assert gap.state == state and gap.reason_code == reason_code
    assert gap.reason_code != 'known_zero'


def test_invalid_source_code_and_changed_service_schema_are_rejected():
    properties = feature(
        1, 'PHID-BAD', source_polygon(450000, 210000, 450010, 210010),
        [('LMEAD', 'Lowland meadows')],
    )['properties']
    properties['HabCodes'] = 'INVENTED'
    with pytest.raises(ValueError, match='Invalid PHI main habitat'):
        normalize_properties(properties)

    metadata = {
        'type': 'Feature Layer', 'geometryType': 'esriGeometryPolygon',
        'spatialReference': {'latestWkid': 27700},
        'objectIdField': 'OBJECTID', 'globalIdField': 'GlobalID',
        'fields': [{'name': name, 'type': field_type} for name, field_type in {
            'OBJECTID': 'esriFieldTypeOID', 'GlobalID': 'esriFieldTypeGlobalID',
            'UID': 'esriFieldTypeString', 'MainHabs': 'esriFieldTypeString',
            'HabCodes': 'esriFieldTypeString', 'FeatDesc': 'esriFieldTypeString',
            'FeatCodes': 'esriFieldTypeString', 'OtherClass': 'esriFieldTypeString',
            'AddHabs': 'esriFieldTypeString', 'PrimSource': 'esriFieldTypeString',
            'AreaHa': 'esriFieldTypeDouble', 'Version': 'esriFieldTypeString',
        }.items()],
    }
    assert validate_service_metadata(metadata)['native_crs'] == 'EPSG:27700'
    metadata['fields'] = [item for item in metadata['fields'] if item['name'] != 'HabCodes']
    with pytest.raises(ValueError, match='HabCodes'):
        validate_service_metadata(metadata)


def test_unrelated_phi_does_not_rename_a_legacy_unavailable_placeholder():
    payload = synthetic_assessment()
    slope = legacy_observation(payload, 'terrain.slope_deg')
    slope.update(
        value=None,
        confidence=0,
        epistemic_status='unknown',
        input_coverage=0,
        missing_reason='Real EA DTM unavailable: source failure',
    )
    _, summary = synthetic_summary()
    legacy = project_land_evidence(payload)
    enriched = project_land_evidence(with_phi(payload, summary))
    assert enriched.identity.projection_id == legacy.identity.projection_id
    legacy_state = bind_wetland_input(legacy, payload['geometry'])
    enriched_state = bind_wetland_input(enriched, payload['geometry'])
    assert enriched_state.model_dump(mode='json') == legacy_state.model_dump(mode='json')


@pytest.fixture
def snapshot_database(tmp_path, monkeypatch):
    database_url = os.getenv('CRC_TEST_DATABASE_URL')
    database = create_engine(
        database_url or 'sqlite:///' + str(tmp_path / 'phi-snapshots.db'),
        pool_pre_ping=True,
    )
    monkeypatch.setattr(core, 'engine', database)
    monkeypatch.setattr(core, 'ROOT', tmp_path)
    monkeypatch.setenv('CRC_ENV', 'development')
    monkeypatch.delenv('R2_BUCKET', raising=False)
    core.init()
    tables = (
        core.land_evidence_snapshot_origins, core.land_evidence_snapshot_links,
        core.land_evidence_snapshot_members, core.land_evidence_snapshots,
        core.features, core.datasets,
    )
    if database_url:
        with database.begin() as connection:
            for table in tables:
                connection.execute(delete(table))
    yield database
    if database_url:
        with database.begin() as connection:
            for table in tables:
                connection.execute(delete(table))
    database.dispose()


def test_phi_change_creates_new_immutable_snapshot_with_org_isolation_and_wetland_parity(
        snapshot_database):
    payload = retained_payload()
    _, summary = synthetic_summary()
    legacy = project_land_evidence(payload)
    enriched = project_land_evidence(with_phi(payload, summary))
    first = store.persist_land_evidence_snapshot(
        legacy, org='org-a', site_id=legacy.identity.legacy_location_id,
    )
    manifest_before = core.load_object(first.manifest_key)
    second = store.persist_land_evidence_snapshot(
        enriched, org='org-a', site_id=enriched.identity.legacy_location_id,
    )
    assert second.id != first.id and second.content_hash != first.content_hash
    assert core.load_object(first.manifest_key) == manifest_before
    assert store.load_land_evidence_snapshot(first.id, org='org-a') == legacy
    loaded = store.load_land_evidence_snapshot(second.id, org='org-a')
    assert loaded == enriched
    with pytest.raises(store.LandEvidenceSnapshotNotFound):
        store.load_land_evidence_snapshot(second.id, org='org-b')

    with snapshot_database.connect() as connection:
        member_kinds = set(connection.execute(
            core.land_evidence_snapshot_members.select().with_only_columns(
                core.land_evidence_snapshot_members.c.kind
            ).where(core.land_evidence_snapshot_members.c.snapshot_id == second.id)
        ).scalars())
        relationships = set(connection.execute(
            core.land_evidence_snapshot_links.select().with_only_columns(
                core.land_evidence_snapshot_links.c.relationship
            ).where(core.land_evidence_snapshot_links.c.snapshot_id == second.id)
        ).scalars())
    assert 'source_feature_reference' in member_kinds
    assert 'source_feature_reference' in relationships

    legacy_state = bind_wetland_input(legacy, payload['geometry'])
    phi_state = bind_wetland_input(enriched, payload['geometry'])
    assert phi_state.model_dump(mode='json') == legacy_state.model_dump(mode='json')
    spec = {key: deepcopy(payload['wetland_model'][key]) for key in (
        'model_version', 'adapter_version', 'feature_version',
        'environment_version', 'refresh_sources', 'config', 'signature',
    )}
    assert run_wetland(phi_state, spec) == payload['wetland_model']
    assert fingerprint(payload) == fingerprint(retained_payload())


def test_analyze_resolves_stored_phi_attributes_on_supported_database(snapshot_database):
    parcel = source_polygon(450000, 210000, 450100, 210100)
    source = feature(
        91, 'PHID-DATABASE', source_polygon(450000, 210000, 450050, 210100),
        [('LMEAD', 'Lowland meadows')], additional='PONDS',
    )
    dataset_id = 'phi-database-sep-25'
    with snapshot_database.begin() as connection:
        connection.execute(insert(core.datasets).values(
            id=dataset_id, key='priority_habitats', state='available',
            retrieved='2026-09-09T00:00:00+00:00',
            metadata={
                'name': 'Priority Habitats Inventory (England)',
                'publisher': 'Natural England', 'url': SERVICE_URL,
                'bbox': core.PILOT, 'limitations': LIMITATIONS,
                'attribution': '© Natural England 2025.',
                'licence_text': 'Open Government Licence v3.0.',
                'synthetic': False, 'source_release': 'Sep_25',
                'source_metadata_revision_date': '2025-10-01',
                'source_capture_end_date': '2025-09-10',
                'source_schema': {
                    'service_data_last_edit': '2025-10-23T12:36:23.345000+00:00',
                },
                'sha256': 'a' * 64,
                'raw_semantics': 'Assembled exhaustive authoritative features before repair.',
            },
        ))
        geometry = source['geometry']
        minx, miny, maxx, maxy = shape(geometry).bounds
        connection.execute(insert(core.features).values(
            id=source['id'], dataset_id=dataset_id, geometry=geometry,
            properties=source['properties'], minx=minx, miny=miny,
            maxx=maxx, maxy=maxy,
        ))
        if snapshot_database.dialect.name == 'postgresql':
            connection.execute(text(
                'UPDATE features SET geom=ST_SetSRID(ST_GeomFromGeoJSON(:geometry),4326) '
                'WHERE id=:id'
            ), {'geometry': json.dumps(geometry), 'id': source['id']})
    result = core.analyze({
        'id': 'phi-database-analysis', 'site_id': 'phi-database-site',
        'site_name': 'PHI database path', 'version': 1, 'geometry': parcel,
        'dataset_ids': [dataset_id], 'created': '2026-09-09T00:01:00+00:00',
    })
    finding = result['findings'][0]
    assert finding['coverage'] == 'covered'
    assert finding['priority_habitats']['habitats'][0]['habitat_code'] == 'LMEAD'
    assert finding['priority_habitats']['habitats'][0]['overlap_fraction'] == pytest.approx(.5)
    assert finding['priority_habitats']['any_main_priority_habitat']['overlap_fraction'] == pytest.approx(.5)
    assert finding['priority_habitats']['source_features'][0]['uid'] == 'PHID-DATABASE'
    assert finding['priority_habitats']['source_features'][0]['additional_habitat_codes'] == ['PONDS']
    # PHI is native evidence and never enters the legacy wetland EarthState.
    assert result['environmental_state']['raw'] == []
