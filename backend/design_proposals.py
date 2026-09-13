"""Versioned proposed infrastructure designs pinned to immutable Earth evidence.

These records describe proposed state. They are deliberately separate from Sites,
Terrene Earth Evidence Snapshots and reasoning ModuleRuns.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from shapely.errors import ShapelyError
from shapely.geometry import shape
from shapely.ops import unary_union
from shapely.validation import explain_validity
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from backend import core
from backend.earth import fingerprint
from backend import land_evidence_store as evidence_store


MAX_FEATURES = 250
MAX_POSITIONS = 50_000
MAX_PAYLOAD_BYTES = 1_000_000
FEATURE_ROLES = {
    'development_footprint', 'access_road_footprint', 'temporary_work_area',
}


class ProposalError(RuntimeError):
    """Base class for safe proposal persistence failures."""


class ProposalNotFound(ProposalError):
    """The requested record is absent or outside the organisation scope."""


class ProposalConflict(ProposalError):
    """The requested immutable write conflicts with stored state."""


class ProposalIntegrityError(ProposalError):
    """Stored project or revision identity no longer verifies."""


class InputModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ProjectInput(InputModel):
    name: str = Field(min_length=1, max_length=160)
    project_type: Literal['solar']
    site_id: str = Field(min_length=1, max_length=200)
    evidence_snapshot_id: str = Field(min_length=1, max_length=300)


class AlternativeInput(InputModel):
    name: str = Field(min_length=1, max_length=160)


class SubmissionProvenance(InputModel):
    source: Literal['api', 'geojson_upload', 'other'] = 'api'
    source_reference: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)


class RevisionInput(InputModel):
    geometry: dict[str, Any]
    parent_revision_id: str | None = Field(default=None, max_length=200)
    idempotency_key: str = Field(min_length=1, max_length=200)
    source_provenance: SubmissionProvenance = Field(default_factory=SubmissionProvenance)


class EvidenceBaseline(BaseModel):
    model_config = ConfigDict(extra='forbid')

    snapshot_id: str
    content_hash: str
    schema_version: str
    registry_version: str
    snapshot_created: datetime
    site_id: str
    boundary_version: int
    boundary_geometry_fingerprint: str


class ProjectRecord(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: str
    org: str
    name: str
    project_type: Literal['solar']
    site_id: str
    baseline: EvidenceBaseline
    created: datetime


class AlternativeRecord(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: str
    org: str
    project_id: str
    name: str
    created: datetime


class RevisionRecord(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: str
    org: str
    project_id: str
    alternative_id: str
    revision_number: int
    parent_revision_id: str | None
    evidence_snapshot_id: str
    baseline: EvidenceBaseline
    geometry: dict[str, Any]
    geometry_fingerprint: str
    source_provenance: SubmissionProvenance
    extends_beyond_baseline: bool
    content_fingerprint: str
    idempotency_key: str
    created: datetime


def _owned(connection, table, record_id: str, org: str) -> dict[str, Any]:
    row = connection.execute(select(table).where(
        table.c.id == record_id, table.c.org == org,
    )).mappings().first()
    if not row:
        raise ProposalNotFound('Record not found')
    return dict(row)


def _clean_name(value: str, label: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f'Enter a {label} name')
    return cleaned


def _project_record(row: dict[str, Any]) -> ProjectRecord:
    return ProjectRecord.model_validate({
        'id': row['id'], 'org': row['org'], 'name': row['name'],
        'project_type': row['project_type'], 'site_id': row['site_id'],
        'baseline': {
            'snapshot_id': row['evidence_snapshot_id'],
            'content_hash': row['evidence_content_hash'],
            'schema_version': row['evidence_schema_version'],
            'registry_version': row['evidence_registry_version'],
            'snapshot_created': row['evidence_snapshot_created'],
            'site_id': row['site_id'],
            'boundary_version': row['boundary_version'],
            'boundary_geometry_fingerprint': row['boundary_geometry_fingerprint'],
        },
        'created': row['created'],
    })


def _alternative_record(row: dict[str, Any]) -> AlternativeRecord:
    return AlternativeRecord.model_validate({key: row[key] for key in (
        'id', 'org', 'project_id', 'name', 'created',
    )})


def _revision_document(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'project_id': row['project_id'],
        'site_id': row['site_id'],
        'alternative_id': row['alternative_id'],
        'revision_number': row['revision_number'],
        'parent_revision_id': row['parent_revision_id'],
        'evidence_snapshot_id': row['evidence_snapshot_id'],
        'evidence_content_hash': row['evidence_content_hash'],
        'evidence_schema_version': row['evidence_schema_version'],
        'evidence_registry_version': row['evidence_registry_version'],
        'evidence_snapshot_created': row['evidence_snapshot_created'],
        'boundary_version': row['boundary_version'],
        'boundary_geometry_fingerprint': row['boundary_geometry_fingerprint'],
        'geometry': row['geometry'],
        'source_provenance': row['source_provenance'],
        'extends_beyond_baseline': bool(row['extends_beyond_baseline']),
    }


def _revision_record(row: dict[str, Any]) -> RevisionRecord:
    if fingerprint(row['geometry']) != row['geometry_fingerprint']:
        raise ProposalIntegrityError('Stored design geometry fingerprint mismatch')
    if fingerprint(_revision_document(row)) != row['content_fingerprint']:
        raise ProposalIntegrityError('Stored design revision fingerprint mismatch')
    result = {
        key: row[key] for key in (
            'id', 'org', 'project_id', 'alternative_id', 'revision_number',
            'parent_revision_id', 'evidence_snapshot_id', 'geometry',
            'geometry_fingerprint', 'source_provenance',
            'extends_beyond_baseline', 'content_fingerprint',
            'idempotency_key', 'created',
        )
    }
    result['baseline'] = {
        'snapshot_id': row['evidence_snapshot_id'],
        'content_hash': row['evidence_content_hash'],
        'schema_version': row['evidence_schema_version'],
        'registry_version': row['evidence_registry_version'],
        'snapshot_created': row['evidence_snapshot_created'],
        'site_id': row['site_id'],
        'boundary_version': row['boundary_version'],
        'boundary_geometry_fingerprint': row['boundary_geometry_fingerprint'],
    }
    return RevisionRecord.model_validate(result)


def _position(value: Any) -> None:
    if (not isinstance(value, list) or len(value) != 2
            or any(isinstance(item, bool) or not isinstance(item, (int, float))
                   for item in value)):
        raise ValueError('Use finite two-dimensional longitude/latitude positions')
    # Range comparisons safely reject NaN, infinity and arbitrarily large ints
    # without coercing them to floats (which can raise OverflowError).
    if not (-180 <= value[0] <= 180) or not (-90 <= value[1] <= 90):
        raise ValueError('Design coordinates must be valid WGS84 longitude/latitude')


def _validate_polygon_coordinates(coordinates: Any, *, multipolygon: bool) -> int:
    polygons = coordinates if multipolygon else [coordinates]
    if not isinstance(polygons, list) or not polygons:
        raise ValueError('Polygon geometry must contain coordinates')
    count = 0
    for polygon in polygons:
        if not isinstance(polygon, list) or not polygon:
            raise ValueError('Every polygon must contain at least one ring')
        for ring in polygon:
            if not isinstance(ring, list) or len(ring) < 4:
                raise ValueError('Every design ring must contain at least four positions')
            for position in ring:
                _position(position)
                count += 1
            if ring[0] != ring[-1]:
                raise ValueError('Every design ring must be explicitly closed')
    return count


def validate_feature_collection(value: dict[str, Any]) -> tuple[dict[str, Any], Any]:
    """Validate and return the exact accepted GeoJSON document plus its union."""
    try:
        payload = json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (TypeError, ValueError) as error:
        raise ValueError('Design must be valid finite JSON') from error
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise ValueError('Design payload exceeds the 1 MB limit')
    if value.get('crs') is not None:
        raise ValueError('Remove the CRS member and supply WGS84 GeoJSON')
    if value.get('type') != 'FeatureCollection' or not isinstance(value.get('features'), list):
        raise ValueError('Design geometry must be a GeoJSON FeatureCollection')
    features = value['features']
    if not features or len(features) > MAX_FEATURES:
        raise ValueError(f'Design must contain between 1 and {MAX_FEATURES} features')

    ids: set[str] = set()
    geometries = []
    positions = 0
    for feature in features:
        if not isinstance(feature, dict) or feature.get('type') != 'Feature':
            raise ValueError('Every design member must be a GeoJSON Feature')
        feature_id = feature.get('id')
        if (not isinstance(feature_id, str) or not feature_id.strip()
                or len(feature_id) > 128):
            raise ValueError('Every design feature requires a stable string ID')
        if feature_id in ids:
            raise ValueError('Design feature IDs must be unique')
        ids.add(feature_id)
        properties = feature.get('properties')
        if not isinstance(properties, dict):
            raise ValueError('Every design feature requires properties')
        if properties.get('role') not in FEATURE_ROLES:
            raise ValueError('Unsupported design feature role')
        label = properties.get('label')
        if not isinstance(label, str) or not label.strip() or len(label) > 200:
            raise ValueError('Every design feature requires a human-readable label')
        geometry = feature.get('geometry')
        if not isinstance(geometry, dict) or geometry.get('type') not in ('Polygon', 'MultiPolygon'):
            raise ValueError('Design features must use Polygon or MultiPolygon geometry')
        positions += _validate_polygon_coordinates(
            geometry.get('coordinates'), multipolygon=geometry['type'] == 'MultiPolygon',
        )
        if positions > MAX_POSITIONS:
            raise ValueError(f'Design exceeds the {MAX_POSITIONS:,}-position limit')
        shaped = shape(geometry)
        if shaped.is_empty or not shaped.is_valid or shaped.area <= 0:
            reason = explain_validity(shaped)
            raise ValueError('Invalid design geometry topology: ' + reason)
        geometries.append(shaped)
    return deepcopy(value), unary_union(geometries)


def _verified_snapshot(site_id: str, snapshot_id: str, org: str):
    try:
        metadata = evidence_store.get_land_evidence_snapshot(snapshot_id, org=org)
        projection = evidence_store.load_land_evidence_snapshot(snapshot_id, org=org)
    except evidence_store.LandEvidenceSnapshotNotFound as error:
        raise ProposalNotFound('Record not found') from error
    except evidence_store.LandEvidenceSnapshotError as error:
        raise ProposalIntegrityError('Evidence Snapshot integrity check failed') from error
    identity = projection.identity
    if metadata.site_id != site_id or identity.legacy_location_id != site_id:
        raise ProposalConflict('Evidence Snapshot is not associated with the selected Site')
    if (identity.boundary_version != metadata.boundary_version
            or identity.boundary_geometry_fingerprint
            != metadata.boundary_geometry_fingerprint):
        raise ProposalIntegrityError('Evidence Snapshot boundary identity mismatch')
    return metadata


def _historical_boundary(*, org: str, site_id: str, boundary_version: int,
                         expected_fingerprint: str):
    key = f'{org}/boundaries/{site_id}/{boundary_version}.json'
    content = core.load_object(key)
    if content is None:
        raise ProposalIntegrityError('Pinned historical Site boundary is unavailable')
    try:
        submitted = json.loads(content)
        normalized = core.boundary(submitted)
        geometry = shape(normalized)
    except (json.JSONDecodeError, TypeError, ValueError, KeyError, AttributeError,
            IndexError, OverflowError, ShapelyError) as error:
        raise ProposalIntegrityError('Pinned historical Site boundary is invalid') from error
    if fingerprint(normalized) != expected_fingerprint:
        raise ProposalIntegrityError('Pinned historical Site boundary fingerprint mismatch')
    return geometry


def _verify_project_baseline(project: dict[str, Any], *, org: str):
    """Revalidate a Project's copied baseline before extending its lineage."""
    snapshot = _verified_snapshot(
        project['site_id'], project['evidence_snapshot_id'], org,
    )
    expected = {
        'evidence_content_hash': snapshot.content_hash,
        'evidence_schema_version': snapshot.schema_version,
        'evidence_registry_version': snapshot.registry_version,
        'evidence_snapshot_created': snapshot.created.isoformat(),
        'boundary_version': snapshot.boundary_version,
        'boundary_geometry_fingerprint': snapshot.boundary_geometry_fingerprint,
    }
    differences = [
        field for field, value in expected.items() if project[field] != value
    ]
    if differences:
        raise ProposalIntegrityError(
            'Project baseline contradicts its committed Evidence Snapshot: '
            + ', '.join(differences)
        )
    return snapshot


def _verify_revision_lineage(row: dict[str, Any],
                             project: dict[str, Any]) -> RevisionRecord:
    """Integrity-check a stored revision and its copied Project baseline."""
    record = _revision_record(row)
    expected = {
        'project_id': project['id'],
        'site_id': project['site_id'],
        'evidence_snapshot_id': project['evidence_snapshot_id'],
        'evidence_content_hash': project['evidence_content_hash'],
        'evidence_schema_version': project['evidence_schema_version'],
        'evidence_registry_version': project['evidence_registry_version'],
        'evidence_snapshot_created': project['evidence_snapshot_created'],
        'boundary_version': project['boundary_version'],
        'boundary_geometry_fingerprint': project['boundary_geometry_fingerprint'],
    }
    differences = [
        field for field, value in expected.items() if row[field] != value
    ]
    if differences:
        raise ProposalIntegrityError(
            'Stored revision contradicts its Project baseline: '
            + ', '.join(differences)
        )
    return record


def create_project(data: ProjectInput, *, org: str) -> ProjectRecord:
    name = _clean_name(data.name, 'project')
    with core.engine.connect() as connection:
        _owned(connection, core.sites, data.site_id, org)
    snapshot = _verified_snapshot(data.site_id, data.evidence_snapshot_id, org)
    _historical_boundary(
        org=org, site_id=data.site_id, boundary_version=snapshot.boundary_version,
        expected_fingerprint=snapshot.boundary_geometry_fingerprint,
    )
    row = {
        'id': core.uid(), 'org': org, 'name': name,
        'project_type': data.project_type, 'site_id': data.site_id,
        'evidence_snapshot_id': snapshot.id,
        'evidence_content_hash': snapshot.content_hash,
        'evidence_schema_version': snapshot.schema_version,
        'evidence_registry_version': snapshot.registry_version,
        'evidence_snapshot_created': snapshot.created.isoformat(),
        'boundary_version': snapshot.boundary_version,
        'boundary_geometry_fingerprint': snapshot.boundary_geometry_fingerprint,
        'created': core.now(),
    }
    with core.engine.begin() as connection:
        connection.execute(insert(core.infrastructure_projects).values(**row))
    return _project_record(row)


def get_project(project_id: str, *, org: str) -> ProjectRecord:
    with core.engine.connect() as connection:
        return _project_record(_owned(
            connection, core.infrastructure_projects, project_id, org,
        ))


def list_projects(*, org: str, site_id: str | None = None) -> list[ProjectRecord]:
    query = select(core.infrastructure_projects).where(
        core.infrastructure_projects.c.org == org,
    )
    with core.engine.connect() as connection:
        if site_id is not None:
            _owned(connection, core.sites, site_id, org)
            query = query.where(core.infrastructure_projects.c.site_id == site_id)
        rows = connection.execute(query.order_by(
            core.infrastructure_projects.c.created.desc(),
        )).mappings()
        return [_project_record(dict(row)) for row in rows]


def create_alternative(project_id: str, data: AlternativeInput, *,
                       org: str) -> AlternativeRecord:
    name = _clean_name(data.name, 'alternative')
    row = {
        'id': core.uid(), 'org': org, 'project_id': project_id,
        'name': name, 'name_key': name.casefold(), 'created': core.now(),
    }
    try:
        with core.engine.begin() as connection:
            _owned(connection, core.infrastructure_projects, project_id, org)
            connection.execute(insert(core.design_alternatives).values(**row))
    except IntegrityError as error:
        raise ProposalConflict('An alternative with this name already exists') from error
    return _alternative_record(row)


def get_alternative(alternative_id: str, *, org: str) -> AlternativeRecord:
    with core.engine.connect() as connection:
        return _alternative_record(_owned(
            connection, core.design_alternatives, alternative_id, org,
        ))


def list_alternatives(project_id: str, *, org: str) -> list[AlternativeRecord]:
    with core.engine.connect() as connection:
        _owned(connection, core.infrastructure_projects, project_id, org)
        rows = connection.execute(select(core.design_alternatives).where(
            core.design_alternatives.c.org == org,
            core.design_alternatives.c.project_id == project_id,
        ).order_by(core.design_alternatives.c.created)).mappings()
        return [_alternative_record(dict(row)) for row in rows]


def _request_fingerprint(data: RevisionInput, geometry: dict[str, Any]) -> str:
    return fingerprint({
        'parent_revision_id': data.parent_revision_id,
        'geometry': geometry,
        'source_provenance': data.source_provenance.model_dump(mode='json'),
    })


def create_revision(alternative_id: str, data: RevisionInput, *,
                    org: str) -> RevisionRecord:
    geometry, proposed_shape = validate_feature_collection(data.geometry)
    provenance = data.source_provenance.model_dump(mode='json')
    request_hash = _request_fingerprint(data, geometry)
    idempotency_key = data.idempotency_key.strip()
    if not idempotency_key:
        raise ValueError('Idempotency key must not be blank')

    try:
        with core.engine.begin() as connection:
            alternative = _owned(connection, core.design_alternatives,
                                 alternative_id, org)
            project = _owned(connection, core.infrastructure_projects,
                             alternative['project_id'], org)
            # Serialize writers per alternative on PostgreSQL. Unique constraints
            # remain the final guard in every database.
            alternative = dict(connection.execute(select(core.design_alternatives).where(
                core.design_alternatives.c.id == alternative_id,
                core.design_alternatives.c.org == org,
            ).with_for_update()).mappings().one())

            prior_retry = connection.execute(select(core.design_revisions).where(
                core.design_revisions.c.org == org,
                core.design_revisions.c.alternative_id == alternative_id,
                core.design_revisions.c.idempotency_key == idempotency_key,
            )).mappings().first()
            if prior_retry:
                if prior_retry['request_fingerprint'] != request_hash:
                    raise ProposalConflict(
                        'Idempotency key was already used for a different revision request'
                    )
                return _verify_revision_lineage(dict(prior_retry), project)

            _verify_project_baseline(project, org=org)

            head = connection.execute(select(core.design_revisions).where(
                core.design_revisions.c.org == org,
                core.design_revisions.c.alternative_id == alternative_id,
            ).order_by(core.design_revisions.c.revision_number.desc())).mappings().first()
            head_record = _verify_revision_lineage(dict(head), project) if head else None
            if data.parent_revision_id is not None:
                parent = connection.execute(select(core.design_revisions).where(
                    core.design_revisions.c.id == data.parent_revision_id,
                    core.design_revisions.c.org == org,
                    core.design_revisions.c.project_id == project['id'],
                    core.design_revisions.c.alternative_id == alternative_id,
                )).mappings().first()
                if not parent:
                    raise ProposalNotFound('Parent revision not found')
                _verify_revision_lineage(dict(parent), project)
            expected_head = head_record.id if head_record else None
            if data.parent_revision_id != expected_head:
                raise ProposalConflict(
                    'Alternative changed. Refresh and base the revision on its current head.'
                )

            boundary = _historical_boundary(
                org=org, site_id=project['site_id'],
                boundary_version=project['boundary_version'],
                expected_fingerprint=project['boundary_geometry_fingerprint'],
            )
            extends = not boundary.covers(proposed_shape)
            row = {
                'id': core.uid(), 'org': org, 'project_id': project['id'],
                'site_id': project['site_id'],
                'alternative_id': alternative_id,
                'revision_number': 1 if head is None else head['revision_number'] + 1,
                'parent_revision_id': data.parent_revision_id,
                'evidence_snapshot_id': project['evidence_snapshot_id'],
                'evidence_content_hash': project['evidence_content_hash'],
                'evidence_schema_version': project['evidence_schema_version'],
                'evidence_registry_version': project['evidence_registry_version'],
                'evidence_snapshot_created': project['evidence_snapshot_created'],
                'boundary_version': project['boundary_version'],
                'boundary_geometry_fingerprint': project['boundary_geometry_fingerprint'],
                'geometry': geometry, 'geometry_fingerprint': fingerprint(geometry),
                'source_provenance': provenance,
                'extends_beyond_baseline': extends,
                'idempotency_key': idempotency_key,
                'request_fingerprint': request_hash, 'created': core.now(),
            }
            row['content_fingerprint'] = fingerprint(_revision_document(row))
            connection.execute(insert(core.design_revisions).values(**row))
            return _revision_record(row)
    except IntegrityError as error:
        # A concurrent identical retry can win the unique-key race. Resolve it
        # only when its immutable request fingerprint is identical.
        with core.engine.connect() as connection:
            retry = connection.execute(select(core.design_revisions).where(
                core.design_revisions.c.org == org,
                core.design_revisions.c.alternative_id == alternative_id,
                core.design_revisions.c.idempotency_key == idempotency_key,
            )).mappings().first()
        if retry and retry['request_fingerprint'] == request_hash:
            return _revision_record(dict(retry))
        if retry:
            raise ProposalConflict(
                'Idempotency key was already used for a different revision request'
            ) from error
        raise ProposalConflict(
            'Alternative changed. Refresh and base the revision on its current head.'
        ) from error


def get_revision(revision_id: str, *, org: str) -> RevisionRecord:
    with core.engine.connect() as connection:
        return _revision_record(_owned(
            connection, core.design_revisions, revision_id, org,
        ))


def list_revisions(alternative_id: str, *, org: str) -> list[RevisionRecord]:
    with core.engine.connect() as connection:
        _owned(connection, core.design_alternatives, alternative_id, org)
        rows = connection.execute(select(core.design_revisions).where(
            core.design_revisions.c.org == org,
            core.design_revisions.c.alternative_id == alternative_id,
        ).order_by(core.design_revisions.c.revision_number)).mappings()
        return [_revision_record(dict(row)) for row in rows]
