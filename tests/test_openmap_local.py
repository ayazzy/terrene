"""OS OpenMap - Local object, relationship, evidence and parity checks."""
from copy import deepcopy
import json
import os
from pathlib import Path

from pyproj import Transformer
import pytest
from shapely.geometry import LineString, Point, box, mapping, shape
from shapely.ops import transform
from sqlalchemy import create_engine, delete, insert

from backend import core
from backend import building_heights
from backend import land_evidence_store as store
from backend.earth import fingerprint
from backend.land_evidence import (
    BUILDING_HEIGHT_REGISTRY_VERSION,
    BuildingHeightEvidenceGap,
    BuildingHeightObservation,
    BUILT_WORLD_REGISTRY_VERSION,
    BuiltWorldObservation,
    FunctionalSiteObject,
    RailwayTrackObject,
    project_land_evidence,
)
from backend.building_heights import (
    DTM_CATALOG as HEIGHT_DTM_CATALOG,
    DSM_CATALOG as HEIGHT_DSM_CATALOG,
    PROCESSING_VERSION as HEIGHT_PROCESSING_VERSION,
    SURVEY_METADATA as HEIGHT_SURVEY_METADATA,
)
from backend.openmap_local import (
    ATTRIBUTION,
    DOWNLOAD_FILE_NAME,
    DOWNLOAD_MD5,
    DOWNLOAD_SHA256,
    LIMITATIONS,
    PRODUCT_URL,
    SCHEMA_VERSION,
    SOURCE_RELEASE,
    summarize_relationships,
    validate_product_metadata,
    validate_properties,
)
from backend.wetland import run_wetland
from backend.wetland_binding import bind_wetland_input
from synthetic_assessment import synthetic_assessment


REAL_ROOT = Path(__file__).parents[1] / 'data' / 'verification' / 'england-real-phi-v1'
PORT_MEADOW = REAL_ROOT / 'port-meadow-after.json'
OXFORD_STATION = (
    Path(__file__).parents[1] / 'data' / 'verification' /
    'england-real-openmap-local-2026-04' / 'oxford-station-after.json'
)
OXFORD_STATION_V3_CONTENT_HASH = (
    '507d8ef7b2688ccb911aeeb483c94a1d15924a4b3a7bf6a1cf83e614ae2a6ab8'
)
OXFORD_HEIGHTS = (
    Path(__file__).parents[1] / 'docs' / 'sprints' /
    '005-oxford-station-building-heights.json'
)
FORWARD = Transformer.from_crs(4326, 27700, always_xy=True).transform
BACKWARD = Transformer.from_crs(27700, 4326, always_xy=True).transform


def source_polygon(west, south, east, north):
    return mapping(transform(BACKWARD, box(west, south, east, north)))


def source_row(object_type, source_id, geometry, **attributes):
    feature_code = {
        'building': 15014, 'functional_site': 15811,
        'railway_track': 15300, 'railway_station': 15422,
    }[object_type]
    return {
        'geometry': mapping(geometry),
        'properties': {
            'object_type': object_type, 'source_feature_id': source_id,
            'feature_code': feature_code, **attributes,
        },
    }


def synthetic_summary(*, empty=False):
    parcel = source_polygon(450000, 210000, 450100, 210100)
    rows = [] if empty else [
        source_row('building', '00000000-0000-0000-0000-000000000001',
                   box(450000, 210000, 450070, 210100)),
        source_row('building', '00000000-0000-0000-0000-000000000002',
                   box(450030, 210000, 450100, 210100)),
        source_row('building', '00000000-0000-0000-0000-000000000003',
                   box(450100, 210020, 450110, 210030)),
        source_row(
            'functional_site', '00000000-0000-0000-0000-000000000004',
            box(450010, 210010, 450020, 210020), distinctive_name='CRC Hospital',
            site_theme='Medical Care', classification='Hospital',
        ),
        source_row(
            'railway_track', '00000000-0000-0000-0000-000000000005',
            LineString([(449990, 210050), (450110, 210050)]),
            classification='Multi Track',
        ),
        source_row(
            'railway_track', '00000000-0000-0000-0000-000000000006',
            LineString([(450020, 210050), (450080, 210050)]),
            classification='Single Track',
        ),
        source_row(
            'railway_track', '00000000-0000-0000-0000-000000000007',
            LineString([(450000, 210100), (450100, 210100)]),
            classification='Single Track',
        ),
        source_row(
            'railway_station', '00000000-0000-0000-0000-000000000008',
            Point(450050, 210050), distinctive_name='Oxford',
            classification='Railway Station',
        ),
    ]
    return parcel, summarize_relationships(parcel, rows)


def retained_payload():
    return json.loads(PORT_MEADOW.read_text())


def with_built_world(payload, summary=None, *, coverage='covered', storage=True,
                     failure_type=None):
    result = deepcopy(payload)
    dataset_id = 'openmap-local-2026-04-test'
    finding = {
        'key': 'built_world', 'dataset': 'OS OpenMap - Local',
        'publisher': 'Ordnance Survey', 'source_url': PRODUCT_URL,
        'retrieved': '2026-09-10T00:00:00Z', 'dataset_version': dataset_id,
        'source_release': SOURCE_RELEASE, 'coverage': coverage,
        'coverage_fraction': 1 if coverage == 'covered' else .5 if coverage == 'partial' else None,
        'limitations': LIMITATIONS, 'attribution': ATTRIBUTION,
        'licence': 'Open Government Licence v3.0.',
        'raw_sha256': 'b' * 64 if storage else None,
        'raw_storage_reference': f'reference/{dataset_id}/source.zip' if storage else None,
        'raw_semantics': 'Original official pinned OS archive.',
        'source_failure_type': failure_type,
        'source_error': 'Deliberate test failure' if failure_type else None,
    }
    if summary is not None:
        finding['built_world'] = deepcopy(summary)
    result['findings'].append(finding)
    return result


def built_observations(projection):
    return [item for item in projection.observations
            if isinstance(item, BuiltWorldObservation)]


def with_building_heights(payload):
    result = deepcopy(payload)
    finding = next(item for item in result['findings'] if item['key'] == 'built_world')
    buildings = [item for item in finding['built_world']['objects']
                 if item['object_type'] == 'building']
    roles = (
        ('dtm_describe_coverage', 'a', HEIGHT_DTM_CATALOG, 'application/xml', 'metadata', None),
        ('dtm_raster', 'b', HEIGHT_DTM_CATALOG, 'image/tiff', 'terrain', 1),
        ('dsm_describe_coverage', 'c', HEIGHT_DSM_CATALOG, 'application/xml', 'metadata', None),
        ('dsm_raster', 'd', HEIGHT_DSM_CATALOG, 'image/tiff', 'surface', 1),
    )
    artifacts = []
    for role, character, source_url, media_type, asset_role, resolution in roles:
        checksum = character * 64
        artifacts.append({
            'role': role, 'sha256': checksum,
            'storage_reference': f'environmental/raw/{checksum}/{checksum}.{media_type.split("/")[-1]}',
            'provider': 'Environment Agency',
            'dataset': ('LIDAR Composite Digital Surface Model (DSM) - 1m'
                        if role.startswith('dsm') else
                        'LIDAR Composite Digital Terrain Model (DTM) - 1m'),
            'source_url': source_url, 'media_type': media_type,
            'asset_role': asset_role, 'crs': 'EPSG:27700' if resolution else None,
            'spatial_resolution_m': resolution,
            'raw_semantics': 'Exact retained fixture WCS response.',
            'request': {
                'url': f'https://environment.data.gov.uk/wcs?role={role}',
                'retrieved_at': '2026-09-14T10:00:00Z',
                'etag': None, 'last_modified': None,
            },
        })
    outcomes = []
    for index, item in enumerate(buildings):
        if index == len(buildings) - 1:
            outcomes.append({
                'source_object_key': item['source_object_key'], 'state': 'gap',
                'reason_code': 'footprint_too_small',
                'reason': 'Fixture footprint is too small after buffering.',
                'candidate_cell_count': 2,
            })
        else:
            outcomes.append({
                'source_object_key': item['source_object_key'], 'state': 'available',
                'p50_height_m': 8.25 + index, 'p90_height_m': 11.75 + index,
                'extrusion_height_m': 11.75 + index,
                'candidate_cell_count': 100, 'valid_cell_count': 90,
                'sample_count': 88, 'coverage_fraction': .9,
                'median_absolute_deviation_m': .5,
            })
    finding['building_heights'] = {
        'processing_version': HEIGHT_PROCESSING_VERSION, 'status': 'available',
        'retrieved_at': '2026-09-14T10:00:00Z',
        'building_source_fingerprint': 'fixture',
        'assessment_input_fingerprint': 'fixture',
        'requested_bounds_27700': [449998, 209998, 450112, 210102],
        'survey_metadata': deepcopy(HEIGHT_SURVEY_METADATA),
        'artifacts': artifacts, 'results': outcomes,
        'limitations': 'Historical fixture evidence.',
    }
    return result


def test_pinned_release_metadata_and_source_attributes_are_strict():
    product = {'id': 'OpenMapLocal', 'version': SOURCE_RELEASE}
    downloads = [{
        'area': 'SP', 'format': 'ESRI® Shapefile', 'md5': DOWNLOAD_MD5,
        'fileName': DOWNLOAD_FILE_NAME, 'size': 132851994,
    }]
    assert validate_product_metadata(product, downloads) == downloads[0]
    assert DOWNLOAD_SHA256 == '1e1654017820ef8cf63a93d16a148849cecb651c3e5cb8f153840df931f91bd6'
    changed = deepcopy(downloads)
    changed[0]['md5'] = '0' * 32
    with pytest.raises(ValueError, match='identity changed'):
        validate_product_metadata(product, changed)
    normalized = validate_properties('functional_site', {
        'ID': '00000000-0000-0000-0000-000000000004', 'FEATCODE': 15811,
        'DISTNAME': 'CRC Hospital', 'SITETHEME': 'Medical Care',
        'CLASSIFICA': 'Hospital',
    })
    assert normalized['site_theme'] == 'Medical Care'
    assert normalized['classification'] == 'Hospital'
    with pytest.raises(ValueError, match='code-list'):
        validate_properties('functional_site', {
            **normalized, 'classification': 'Invented Site Type',
        })


def test_polygon_union_objects_and_touch_are_not_conflated():
    _, summary = synthetic_summary()
    observations = {item['definition_id']: item for item in summary['observations']}
    building = observations['built.building.mapped_overlap_fraction']
    # Two 70% polygons overlap by 40%; their union is the whole parcel, not 140%.
    assert building['value'] == pytest.approx(1, abs=2e-4)
    assert building['numerator'] / building['denominator'] == building['value']
    assert len(building['supporting_source_object_keys']) == 2
    touch = next(item for item in summary['relationships']
                 if item['source_object_key'].endswith('000000000003'))
    assert touch['predicate'] == 'touches'
    assert touch['measurements'] == {}
    assert touch['source_object_key'] not in building['supporting_source_object_keys']


def test_line_crossing_containment_touch_and_union_length_remain_lines():
    _, summary = synthetic_summary()
    tracks = [item for item in summary['objects'] if item['object_type'] == 'railway_track']
    assert tracks and all(shape(item['source_geometry']).geom_type == 'LineString' for item in tracks)
    predicates = {
        item['source_object_key']: item['predicate']
        for item in summary['relationships'] if item['predicate'] != 'minimum_distance'
    }
    assert predicates['railway_track:00000000-0000-0000-0000-000000000005'] == 'crosses'
    assert predicates['railway_track:00000000-0000-0000-0000-000000000006'] == 'contained_within'
    assert predicates['railway_track:00000000-0000-0000-0000-000000000007'] == 'touches'
    length = next(item for item in summary['observations']
                  if item['definition_id'] == 'transport.railway_track.mapped_length_within')
    # The contained line overlaps the crossing line, so the union stays 100 m.
    assert length['value'] == pytest.approx(100, abs=.02)


def test_projection_retains_typed_objects_relationships_and_derived_measurements():
    _, summary = synthetic_summary()
    payload = with_built_world(synthetic_assessment(), summary)
    projection = project_land_evidence(payload)
    assert projection.identity.registry_version == BUILT_WORLD_REGISTRY_VERSION
    assert len(projection.objects) == 8
    assert any(isinstance(item, FunctionalSiteObject)
               and item.classification == 'Hospital' and item.site_theme == 'Medical Care'
               for item in projection.objects)
    assert any(isinstance(item, RailwayTrackObject) for item in projection.objects)
    object_ids = {item.id for item in projection.objects}
    assert all(item.object_id in object_ids for item in projection.relationships)
    building = next(item for item in built_observations(projection)
                    if item.definition_id == 'built.building.mapped_overlap_fraction')
    assert building.measurement.numerator / building.measurement.denominator == pytest.approx(
        building.value.value, abs=1e-12
    )
    assert set(building.supporting_object_ids) <= object_ids
    assert SCHEMA_VERSION == building.provenance.source_schema_version
    assert not any(item.definition_id == 'built.infrastructure.complete_footprint_fraction'
                   for item in projection.observations)


def test_v4_height_observations_link_existing_buildings_and_never_fill_gaps():
    _, summary = synthetic_summary()
    v3_payload = with_built_world(synthetic_assessment(), summary)
    v3_projection = project_land_evidence(v3_payload)
    projection = project_land_evidence(with_building_heights(v3_payload))
    assert projection.identity.registry_version == BUILDING_HEIGHT_REGISTRY_VERSION
    assert projection.identity.projection_id == v3_projection.identity.projection_id
    assert [item.model_dump(mode='json') for item in projection.objects] == [
        item.model_dump(mode='json') for item in v3_projection.objects
    ]
    building_ids = {item.id for item in projection.objects
                    if item.object_type == 'building'}
    observations = [item for item in projection.observations
                    if isinstance(item, BuildingHeightObservation)]
    gaps = [item for item in projection.gaps
            if isinstance(item, BuildingHeightEvidenceGap)]
    assert len(observations) == 2 and len(gaps) == 1
    assert {item.object_id for item in observations} | {item.object_id for item in gaps} == building_ids
    assert all(item.value.value == item.measurement.p90_height_m ==
               item.measurement.extrusion_height_m for item in observations)
    assert all(item.availability == 'partial' and item.measurement.coverage_fraction == .9
               for item in observations)
    assert gaps[0].reason_code == 'footprint_too_small'
    assert not any(item.object_id == gaps[0].object_id for item in observations)
    assert bind_wetland_input(projection, v3_payload['geometry']).model_dump(mode='json') == (
        bind_wetland_input(v3_projection, v3_payload['geometry']).model_dump(mode='json')
    )


def test_retained_oxford_v3_content_identity_is_byte_stable():
    projection = project_land_evidence(json.loads(OXFORD_STATION.read_text()))
    assert projection.identity.registry_version == BUILT_WORLD_REGISTRY_VERSION
    assert store.snapshot_content_hash(projection) == OXFORD_STATION_V3_CONTENT_HASH


def test_retained_oxford_height_results_link_all_five_real_buildings():
    payload = json.loads(OXFORD_STATION.read_text())
    verified = json.loads(OXFORD_HEIGHTS.read_text())
    finding = next(item for item in payload['findings'] if item['key'] == 'built_world')
    artifacts = []
    for item in verified['artifacts']:
        is_dsm = item['role'].startswith('dsm')
        is_raster = item['role'].endswith('raster')
        artifacts.append({
            'role': item['role'], 'sha256': item['sha256'],
            'request': {
                'url': item['request_url'],
                'retrieved_at': '2026-09-14T09:42:51.647962+00:00',
                'etag': None, 'last_modified': None,
            },
            'storage_reference': 'verification-only/' + item['sha256'],
            'provider': 'Environment Agency',
            'dataset': ('LIDAR Composite Digital Surface Model (DSM) - 1m'
                        if is_dsm else
                        'LIDAR Composite Digital Terrain Model (DTM) - 1m'),
            'source_url': HEIGHT_DSM_CATALOG if is_dsm else HEIGHT_DTM_CATALOG,
            'media_type': 'image/tiff' if is_raster else 'application/xml',
            'asset_role': ('surface' if is_dsm else 'terrain') if is_raster else 'metadata',
            'crs': 'EPSG:27700' if is_raster else None,
            'spatial_resolution_m': 1 if is_raster else None,
            'raw_semantics': 'Verification identity only; production retains the exact private bytes.',
        })
    finding['building_heights'] = {
        'processing_version': verified['processing_version'],
        'status': verified['status'],
        'retrieved_at': '2026-09-14T09:42:51.647962+00:00',
        'building_source_fingerprint': 'retained-verification',
        'assessment_input_fingerprint': 'retained-verification',
        'requested_bounds_27700': verified['requested_bounds_27700'],
        'survey_metadata': verified['survey_metadata'],
        'artifacts': artifacts, 'results': verified['results'],
        'limitations': verified['qualification'],
    }
    projection = project_land_evidence(payload)
    observations = [item for item in projection.observations
                    if isinstance(item, BuildingHeightObservation)]
    building_ids = {item.id for item in projection.objects if item.object_type == 'building'}
    assert projection.identity.registry_version == BUILDING_HEIGHT_REGISTRY_VERSION
    assert len(observations) == 5
    assert {item.object_id for item in observations} == building_ids
    assert sorted(item.value.value for item in observations) == sorted(
        item['p90_height_m'] for item in verified['results']
    )


def test_known_mapped_zero_is_not_unknown_or_real_world_absence():
    parcel, summary = synthetic_summary(empty=True)
    projection = project_land_evidence(with_built_world(synthetic_assessment(), summary))
    values = {item.definition_id: item for item in built_observations(projection)}
    for definition_id in (
        'built.building.mapped_overlap_fraction',
        'built.functional_site.mapped_overlap_fraction',
        'transport.railway_track.mapped_length_within',
    ):
        assert values[definition_id].known_zero
        assert values[definition_id].value.value == 0
        assert values[definition_id].support.coverage_status == 'full'
        assert 'not that no real-world object exists' in values[definition_id].limitations
    distance_gaps = [item for item in projection.gaps
                     if item.definition_id and item.definition_id.endswith('distance_min')]
    assert len(distance_gaps) == 2
    assert all(item.reason_code == 'no_mapped_object_within_search_radius'
               for item in distance_gaps)


def test_incomplete_tile_halo_withholds_minimum_distance_but_not_parcel_observations():
    parcel = source_polygon(450000, 202000, 450100, 202100)
    summary = summarize_relationships(parcel, [source_row(
        'railway_station', '00000000-0000-0000-0000-000000000099',
        Point(450200, 202050), distinctive_name='Outside sample',
        classification='Railway Station',
    )])
    assert summary['rail_distance_coverage'] == 'partial'
    definitions = {item['definition_id'] for item in summary['observations']}
    assert 'built.building.mapped_overlap_fraction' in definitions
    assert 'transport.railway_station.distance_min' not in definitions
    projection = project_land_evidence(with_built_world(synthetic_assessment(), summary))
    gap = next(item for item in projection.gaps
               if item.definition_id == 'transport.railway_station.distance_min')
    assert gap.state == 'partial_coverage'
    assert gap.reason_code == 'partial_search_coverage'


@pytest.mark.parametrize(
    ('coverage', 'storage', 'state', 'reason_code'),
    [
        ('unknown', False, 'unavailable', 'source_unavailable'),
        ('unknown', True, 'unavailable', 'outside_acquired_coverage'),
        ('partial', True, 'partial_coverage', 'partial_acquired_coverage'),
        ('acquisition_failure', False, 'unavailable', 'acquisition_failure'),
        ('processing_failure', False, 'unavailable', 'processing_failure'),
    ],
)
def test_unavailable_partial_and_outside_are_not_mapped_zero(
        coverage, storage, state, reason_code):
    failure_type = coverage if coverage.endswith('_failure') else None
    effective_coverage = 'unknown' if failure_type else coverage
    projection = project_land_evidence(with_built_world(
        synthetic_assessment(), coverage=effective_coverage, storage=storage,
        failure_type=failure_type,
    ))
    assert not projection.objects and not projection.relationships
    assert not built_observations(projection)
    gaps = [item for item in projection.gaps
            if item.definition_id in {definition.id for definition in projection.definitions
                                      if definition.id.startswith(('built.building', 'built.functional', 'transport.railway'))}]
    assert len(gaps) == 5
    assert all(item.state == state and item.reason_code == reason_code for item in gaps)


@pytest.fixture
def snapshot_database(tmp_path, monkeypatch):
    database_url = os.getenv('CRC_TEST_DATABASE_URL')
    database = create_engine(database_url or 'sqlite:///' + str(tmp_path / 'openmap.db'))
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


def test_snapshot_history_org_isolation_phi_worldcover_and_wetland_parity(snapshot_database):
    payload = retained_payload()
    _, summary = synthetic_summary()
    old_projection = project_land_evidence(payload)
    enriched = project_land_evidence(with_built_world(payload, summary))
    assert old_projection.identity.projection_id == enriched.identity.projection_id
    assert fingerprint(payload) == fingerprint(retained_payload())
    old_snapshot = store.persist_land_evidence_snapshot(
        old_projection, org='org-a', site_id=old_projection.identity.legacy_location_id,
    )
    old_manifest = core.load_object(old_snapshot.manifest_key)
    new_snapshot = store.persist_land_evidence_snapshot(
        enriched, org='org-a', site_id=enriched.identity.legacy_location_id,
    )
    assert new_snapshot.id != old_snapshot.id
    assert core.load_object(old_snapshot.manifest_key) == old_manifest
    assert store.load_land_evidence_snapshot(old_snapshot.id, org='org-a') == old_projection
    assert store.load_land_evidence_snapshot(new_snapshot.id, org='org-a') == enriched
    with pytest.raises(store.LandEvidenceSnapshotNotFound):
        store.load_land_evidence_snapshot(new_snapshot.id, org='org-b')

    # Existing independent source families remain alongside the new objects.
    definitions = {item.definition_id for item in enriched.observations}
    assert 'built.mapped_built_up_fraction' in definitions
    assert 'ecology.priority_habitat.any_mapped_overlap_fraction' in definitions
    assert 'built.building.mapped_overlap_fraction' in definitions
    assert [item.model_dump(mode='json') for item in old_projection.observations
            if item.definition_id.startswith('ecology.priority_habitat.')] == [
                item.model_dump(mode='json') for item in enriched.observations
                if item.definition_id.startswith('ecology.priority_habitat.')
            ]
    assert [item.model_dump(mode='json') for item in old_projection.observations
            if item.definition_id == 'built.mapped_built_up_fraction'] == [
                item.model_dump(mode='json') for item in enriched.observations
                if item.definition_id == 'built.mapped_built_up_fraction'
            ]
    prior_state = bind_wetland_input(old_projection, payload['geometry'])
    enriched_state = bind_wetland_input(enriched, payload['geometry'])
    assert enriched_state.model_dump(mode='json') == prior_state.model_dump(mode='json')
    spec = {key: deepcopy(payload['wetland_model'][key]) for key in (
        'model_version', 'adapter_version', 'feature_version', 'environment_version',
        'refresh_sources', 'config', 'signature',
    )}
    # The historical retained result is never rewritten; adding built-world
    # evidence also leaves the bound state and resulting wetland run unchanged.
    assert run_wetland(enriched_state, spec) == run_wetland(prior_state, spec)
    assert payload['wetland_model'] == retained_payload()['wetland_model']
    assert enriched_state.get('human.infrastructure_fraction').value is None


def test_v4_snapshot_persists_object_links_and_round_trips(snapshot_database):
    _, summary = synthetic_summary()
    payload = with_building_heights(with_built_world(synthetic_assessment(), summary))
    projection = project_land_evidence(payload)
    record = store.persist_land_evidence_snapshot(
        projection, org='org-a', site_id=projection.identity.legacy_location_id,
    )
    assert record.registry_version == BUILDING_HEIGHT_REGISTRY_VERSION
    assert store.load_land_evidence_snapshot(record.id, org='org-a') == projection
    height_members = [item for item in projection.observations
                      if isinstance(item, BuildingHeightObservation)]
    height_gaps = [item for item in projection.gaps
                   if isinstance(item, BuildingHeightEvidenceGap)]
    with snapshot_database.connect() as connection:
        links = [dict(row) for row in connection.execute(
            core.land_evidence_snapshot_links.select().where(
                core.land_evidence_snapshot_links.c.snapshot_id == record.id,
                core.land_evidence_snapshot_links.c.relationship == 'object',
            )
        ).mappings()]
    linked = {(item['owner_kind'], item['owner_id'], item['reference_id']) for item in links}
    assert all(('observation', item.id, item.object_id) in linked for item in height_members)
    assert all(('gap', item.id, item.object_id) in linked for item in height_gaps)


def test_database_analysis_path_resolves_multiple_geometry_types(snapshot_database, monkeypatch):
    def unavailable_height_fixture(job, finding):
        buildings = [item for item in finding['built_world']['objects']
                     if item['object_type'] == 'building']
        return {
            'processing_version': HEIGHT_PROCESSING_VERSION,
            'status': 'unavailable', 'retrieved_at': '2026-09-14T10:00:00Z',
            'building_source_fingerprint': 'fixture',
            'assessment_input_fingerprint': 'fixture',
            'requested_bounds_27700': None,
            'survey_metadata': deepcopy(HEIGHT_SURVEY_METADATA),
            'artifacts': [], 'limitations': 'Fixture source unavailable.',
            'missing_reason': 'Fixture source unavailable.',
            'results': [{
                'source_object_key': item['source_object_key'], 'state': 'gap',
                'reason_code': 'acquisition_failed',
                'reason': 'Fixture source unavailable.',
            } for item in buildings],
        }

    monkeypatch.setattr(
        building_heights, 'acquire_for_assessment', unavailable_height_fixture,
    )
    parcel, summary = synthetic_summary()
    dataset_id = 'openmap-local-database-test'
    with snapshot_database.begin() as connection:
        connection.execute(insert(core.datasets).values(
            id=dataset_id, key='built_world', state='available',
            retrieved='2026-09-10T00:00:00+00:00', metadata={
                'name': 'OS OpenMap - Local', 'publisher': 'Ordnance Survey',
                'url': PRODUCT_URL, 'bbox': core.PILOT,
                'coverage_geometry': mapping(box(*core.PILOT)),
                'limitations': LIMITATIONS, 'attribution': ATTRIBUTION,
                'licence_text': 'Open Government Licence v3.0.',
                'synthetic': False, 'source_release': SOURCE_RELEASE,
                'sha256': 'b' * 64, 'raw_object_key': f'reference/{dataset_id}/source.zip',
                'raw_semantics': 'Original official pinned OS archive.',
            },
        ))
        # Reuse the exact source rows that produced the reference summary.
        rows = []
        for source_object in summary['objects']:
            rows.append({
                'geometry': source_object['source_geometry'],
                'properties': {
                    key: value for key, value in source_object.items()
                    if key in ('object_type', 'source_feature_id', 'feature_code',
                               'distinctive_name', 'site_theme', 'classification')
                },
            })
        for index, row in enumerate(rows):
            wgs = transform(BACKWARD, shape(row['geometry']))
            minx, miny, maxx, maxy = wgs.bounds
            connection.execute(insert(core.features).values(
                id=f'feature-{index}', dataset_id=dataset_id,
                geometry=row['geometry'], properties=row['properties'],
                minx=minx, miny=miny, maxx=maxx, maxy=maxy,
            ))
    result = core.analyze({
        'id': 'openmap-database-analysis', 'site_id': 'openmap-database-site',
        'site_name': 'OpenMap database path', 'version': 1, 'geometry': parcel,
        'dataset_ids': [dataset_id], 'created': '2026-09-10T00:01:00+00:00',
    })
    finding = result['findings'][0]
    assert finding['coverage'] == 'covered'
    assert result['environmental_state']['raw'] == []
    assert result['environmental_state']['selected'].get(
        'human.infrastructure_fraction'
    ) is None
    assert finding['built_world']['source_release'] == SOURCE_RELEASE
    assert len([item for item in finding['built_world']['objects']
                if item['object_type'] == 'building']) == 3
    assert finding['building_heights']['status'] == 'unavailable'
    projection = project_land_evidence(result)
    assert projection.identity.registry_version == BUILDING_HEIGHT_REGISTRY_VERSION
    assert len([item for item in projection.gaps
                if isinstance(item, BuildingHeightEvidenceGap)]) == 3
    building = next(item for item in finding['built_world']['observations']
                    if item['definition_id'] == 'built.building.mapped_overlap_fraction')
    assert building['value'] == pytest.approx(1, abs=2e-4)
