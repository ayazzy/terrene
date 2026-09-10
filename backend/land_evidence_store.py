"""Immutable, organisation-scoped persistence for ``land_evidence_v1``.

The validated projection remains one canonical JSON manifest. Relational rows
only catalogue identity, membership and reference edges needed for discovery
and integrity checks; they do not duplicate or reinterpret observation values.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from backend import core
from backend.earth import fingerprint
from backend.land_evidence import (
    BUILT_WORLD_REGISTRY_VERSION,
    BuiltWorldObservation,
    LandEvidenceProjection,
    PHI_REGISTRY_VERSION,
    PriorityHabitatObservation,
    project_land_evidence,
    validate_land_evidence,
)


class LandEvidenceSnapshotError(RuntimeError):
    """Base class for persistence or integrity failures."""


class LandEvidenceSnapshotNotFound(LandEvidenceSnapshotError):
    """The snapshot is absent or belongs to another organisation."""


class LandEvidenceSnapshotConflict(LandEvidenceSnapshotError):
    """Stored immutable identity or content contradicts the supplied data."""


class LandEvidenceSnapshotRecord(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: str
    org: str
    site_id: str
    boundary_version: int
    boundary_geometry_fingerprint: str
    schema_version: str
    registry_version: str
    content_hash: str
    manifest_sha256: str
    manifest_key: str
    created: datetime


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
        allow_nan=False,
    ).encode('utf-8')


def snapshot_content_document(
    value: LandEvidenceProjection | dict[str, Any],
) -> dict[str, Any]:
    """Return the exact core content used for deterministic snapshot identity.

    Legacy assessment and wetland/module references stay in the stored bridge
    manifest, but are intentionally excluded from reusable evidence identity.
    """
    projection = validate_land_evidence(value)
    identity = projection.identity
    document = {
        'schema_version': identity.schema_version,
        'registry_version': identity.registry_version,
        'projection_id': identity.projection_id,
        'boundary': {
            'site_id': identity.legacy_location_id,
            'version': identity.boundary_version,
            'reference': identity.boundary_reference,
            'geometry_fingerprint': identity.boundary_geometry_fingerprint,
            'geography': identity.geography,
        },
        'evidence_as_of': identity.evidence_as_of.isoformat(),
        'definitions': [item.model_dump(mode='json') for item in projection.definitions],
        'raw_references': [item.model_dump(mode='json') for item in projection.raw_references],
        'source_references': [item.model_dump(mode='json') for item in projection.source_references],
        'observations': [item.model_dump(mode='json') for item in projection.observations],
        'selections': [item.model_dump(mode='json') for item in projection.selections],
        'gaps': [item.model_dump(mode='json') for item in projection.gaps],
        'capabilities': [item.model_dump(mode='json') for item in projection.capabilities],
        'diagnostics': [item.model_dump(mode='json') for item in projection.diagnostics],
    }
    if identity.registry_version in (PHI_REGISTRY_VERSION, BUILT_WORLD_REGISTRY_VERSION):
        document['source_feature_references'] = [
            item.model_dump(mode='json') for item in projection.source_feature_references
        ]
    if identity.registry_version == BUILT_WORLD_REGISTRY_VERSION:
        document['objects'] = [item.model_dump(mode='json') for item in projection.objects]
        document['relationships'] = [
            item.model_dump(mode='json') for item in projection.relationships
        ]
    return document


def snapshot_content_hash(value: LandEvidenceProjection | dict[str, Any]) -> str:
    """Digest schema, immutable boundary and complete reusable core evidence."""
    return sha256(_canonical_bytes(snapshot_content_document(value))).hexdigest()


def _snapshot_id(org: str, site_id: str, projection: LandEvidenceProjection,
                 content_hash: str) -> str:
    identity = projection.identity
    digest = fingerprint([
        org, site_id, identity.boundary_version,
        identity.boundary_geometry_fingerprint,
        identity.schema_version, identity.registry_version, content_hash,
    ])
    return 'land-evidence-snapshot:' + digest


def _record(row: dict[str, Any]) -> LandEvidenceSnapshotRecord:
    return LandEvidenceSnapshotRecord.model_validate(row)


def _get_row(connection, snapshot_id: str, org: str) -> dict[str, Any] | None:
    row = connection.execute(select(core.land_evidence_snapshots).where(
        core.land_evidence_snapshots.c.id == snapshot_id,
        core.land_evidence_snapshots.c.org == org,
    )).mappings().first()
    return dict(row) if row else None


def _find_content_row(connection, org: str, site_id: str, boundary_version: int,
                      schema_version: str, content_hash: str) -> dict[str, Any] | None:
    row = connection.execute(select(core.land_evidence_snapshots).where(
        core.land_evidence_snapshots.c.org == org,
        core.land_evidence_snapshots.c.site_id == site_id,
        core.land_evidence_snapshots.c.boundary_version == boundary_version,
        core.land_evidence_snapshots.c.schema_version == schema_version,
        core.land_evidence_snapshots.c.content_hash == content_hash,
    )).mappings().first()
    return dict(row) if row else None


def _verify_existing(row: dict[str, Any], *, snapshot_id: str, org: str,
                     site_id: str, projection: LandEvidenceProjection,
                     content_hash: str) -> LandEvidenceSnapshotRecord:
    identity = projection.identity
    expected = {
        'id': snapshot_id,
        'org': org,
        'site_id': site_id,
        'boundary_version': identity.boundary_version,
        'boundary_geometry_fingerprint': identity.boundary_geometry_fingerprint,
        'schema_version': identity.schema_version,
        'registry_version': identity.registry_version,
        'content_hash': content_hash,
    }
    differences = [key for key, expected_value in expected.items()
                   if row.get(key) != expected_value]
    if differences:
        raise LandEvidenceSnapshotConflict(
            'Existing snapshot contradicts deterministic identity: ' + ', '.join(differences)
        )
    manifest = core.load_object(row['manifest_key'])
    if manifest is None:
        raise LandEvidenceSnapshotConflict('Committed snapshot manifest is missing')
    if sha256(manifest).hexdigest() != row['manifest_sha256']:
        raise LandEvidenceSnapshotConflict('Committed snapshot manifest checksum mismatch')
    try:
        stored = validate_land_evidence(json.loads(manifest))
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        raise LandEvidenceSnapshotConflict('Committed snapshot manifest is invalid') from error
    computed_content_hash = snapshot_content_hash(stored)
    if computed_content_hash != content_hash:
        raise LandEvidenceSnapshotConflict('Committed snapshot content hash mismatch')
    if _snapshot_id(org, site_id, stored, computed_content_hash) != snapshot_id:
        raise LandEvidenceSnapshotConflict('Committed snapshot deterministic ID mismatch')
    _verify_relational_catalogue(snapshot_id, stored)
    return _record(row)


def _member_rows(snapshot_id: str, projection: LandEvidenceProjection) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(kind: str, member_id: str, position: int, definition_id: str | None = None,
            legacy_variable: str | None = None) -> None:
        rows.append({
            'snapshot_id': snapshot_id, 'kind': kind, 'member_id': member_id,
            'position': position, 'definition_id': definition_id,
            'legacy_variable': legacy_variable,
        })

    for position, item in enumerate(projection.definitions):
        add('definition', item.id, position, definition_id=item.id)
    for position, item in enumerate(projection.raw_references):
        add('raw_reference', item.id, position)
    for position, item in enumerate(projection.source_references):
        add('source_reference', item.id, position)
    for position, item in enumerate(projection.source_feature_references):
        add('source_feature_reference', item.id, position)
    for position, item in enumerate(projection.objects):
        add('object', item.id, position)
    for position, item in enumerate(projection.relationships):
        add('relationship', item.id, position)
    for position, item in enumerate(projection.observations):
        add('observation', item.id, position, definition_id=item.definition_id,
            legacy_variable=(None if isinstance(item, (PriorityHabitatObservation,
                                                        BuiltWorldObservation))
                             else item.provenance.legacy_variable))
    for position, item in enumerate(projection.selections):
        add('selection', item.semantic_key, position)
    for position, item in enumerate(projection.gaps):
        add('gap', item.id, position, definition_id=item.definition_id,
            legacy_variable=item.legacy_variable)
    for position, item in enumerate(projection.capabilities):
        add('capability', item.legacy_variable, position,
            legacy_variable=item.legacy_variable)
    for position, item in enumerate(projection.diagnostics):
        add('diagnostic', item.id, position)
    return rows


def _link_rows(snapshot_id: str, projection: LandEvidenceProjection) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(owner_kind: str, owner_id: str, relationship: str,
            references: list[str]) -> None:
        for position, reference_id in enumerate(references):
            rows.append({
                'snapshot_id': snapshot_id, 'owner_kind': owner_kind,
                'owner_id': owner_id, 'relationship': relationship,
                'reference_id': reference_id, 'position': position,
            })

    for item in projection.source_references:
        add('source_reference', item.id, 'raw_reference', item.raw_reference_ids)
    for item in projection.source_feature_references:
        add('source_feature_reference', item.id, 'source_reference', [item.source_reference_id])
        add('source_feature_reference', item.id, 'raw_reference', item.raw_reference_ids)
    for item in projection.objects:
        add('object', item.id, 'source_reference', [item.source_reference_id])
        add('object', item.id, 'raw_reference', item.raw_reference_ids)
    for item in projection.relationships:
        add('relationship', item.id, 'object', [item.object_id])
        add('relationship', item.id, 'source_reference',
            [item.provenance.source_reference_id])
        add('relationship', item.id, 'raw_reference', item.provenance.raw_reference_ids)
    for item in projection.observations:
        add('observation', item.id, 'source_reference', item.source_reference_ids)
        add('observation', item.id, 'raw_reference', item.raw_reference_ids)
        add('observation', item.id, 'parent_observation', item.parent_observation_ids)
        if isinstance(item, PriorityHabitatObservation):
            add('observation', item.id, 'source_feature_reference',
                item.source_feature_reference_ids)
        if isinstance(item, BuiltWorldObservation):
            add('observation', item.id, 'object', item.supporting_object_ids)
    for item in projection.gaps:
        add('gap', item.id, 'source_reference', item.source_reference_ids)
        add('gap', item.id, 'raw_reference', item.raw_reference_ids)
    for item in projection.selections:
        add('selection', item.semantic_key, 'selected_observation', [item.observation_id])
    return rows


def _verify_relational_catalogue(snapshot_id: str,
                                 projection: LandEvidenceProjection) -> None:
    expected_members = _member_rows(snapshot_id, projection)
    expected_links = _link_rows(snapshot_id, projection)
    with core.engine.connect() as connection:
        actual_members = [dict(row) for row in connection.execute(select(
            core.land_evidence_snapshot_members
        ).where(
            core.land_evidence_snapshot_members.c.snapshot_id == snapshot_id
        )).mappings()]
        actual_links = [dict(row) for row in connection.execute(select(
            core.land_evidence_snapshot_links
        ).where(
            core.land_evidence_snapshot_links.c.snapshot_id == snapshot_id
        )).mappings()]
    canonical_sort = lambda rows: sorted(_canonical_bytes(row) for row in rows)
    if canonical_sort(actual_members) != canonical_sort(expected_members):
        raise LandEvidenceSnapshotConflict('Committed snapshot membership catalogue mismatch')
    if canonical_sort(actual_links) != canonical_sort(expected_links):
        raise LandEvidenceSnapshotConflict('Committed snapshot reference catalogue mismatch')


def _insert_memberships(connection, snapshot_id: str,
                        projection: LandEvidenceProjection) -> None:
    """Insert all relational catalogue rows in the caller's transaction."""
    members = _member_rows(snapshot_id, projection)
    links = _link_rows(snapshot_id, projection)
    if members:
        connection.execute(insert(core.land_evidence_snapshot_members), members)
    if links:
        connection.execute(insert(core.land_evidence_snapshot_links), links)


def _add_origin(connection, snapshot_id: str, org: str,
                assessment_id: str | None, assessment_fingerprint: str,
                created: str) -> None:
    if assessment_id is None:
        return
    prior = connection.execute(select(core.land_evidence_snapshot_origins).where(
        core.land_evidence_snapshot_origins.c.snapshot_id == snapshot_id,
        core.land_evidence_snapshot_origins.c.assessment_id == assessment_id,
    )).mappings().first()
    if prior:
        if prior['org'] != org or prior['assessment_fingerprint'] != assessment_fingerprint:
            raise LandEvidenceSnapshotConflict('Legacy assessment origin was previously recorded differently')
        return
    connection.execute(insert(core.land_evidence_snapshot_origins).values(
        snapshot_id=snapshot_id, assessment_id=assessment_id, org=org,
        assessment_fingerprint=assessment_fingerprint, created=created,
    ))


def _record_origin_idempotently(snapshot_id: str, org: str,
                                assessment_id: str | None,
                                assessment_fingerprint: str,
                                created: str) -> None:
    if assessment_id is None:
        return
    try:
        with core.engine.begin() as connection:
            _add_origin(connection, snapshot_id, org, assessment_id,
                        assessment_fingerprint, created)
    except IntegrityError:
        # A concurrent association of the same immutable assessment is benign;
        # any differing association remains a conflict.
        with core.engine.connect() as connection:
            prior = connection.execute(select(core.land_evidence_snapshot_origins).where(
                core.land_evidence_snapshot_origins.c.snapshot_id == snapshot_id,
                core.land_evidence_snapshot_origins.c.assessment_id == assessment_id,
            )).mappings().first()
        if (not prior or prior['org'] != org
                or prior['assessment_fingerprint'] != assessment_fingerprint):
            raise


def _validate_origin_assessment(org: str, site_id: str,
                                assessment_id: str | None,
                                projection: LandEvidenceProjection) -> None:
    if assessment_id is None:
        return
    with core.engine.connect() as connection:
        assessment = connection.execute(select(core.assessments).where(
            core.assessments.c.id == assessment_id,
            core.assessments.c.org == org,
            core.assessments.c.site_id == site_id,
        )).mappings().first()
    if not assessment or not isinstance(assessment['result'], dict):
        raise LandEvidenceSnapshotConflict('Legacy assessment origin does not resolve in this organisation')
    identity = projection.identity
    if fingerprint(assessment['result']) != identity.legacy_assessment_fingerprint:
        raise LandEvidenceSnapshotConflict('Legacy assessment origin fingerprint does not match projection')
    if (assessment['version'] != identity.boundary_version
            or fingerprint(assessment['geometry']) != identity.boundary_geometry_fingerprint):
        raise LandEvidenceSnapshotConflict('Legacy assessment origin boundary does not match projection')


def persist_land_evidence_snapshot(
    value: LandEvidenceProjection | dict[str, Any], *, org: str, site_id: str,
    origin_assessment_id: str | None = None,
) -> LandEvidenceSnapshotRecord:
    """Validate and commit one immutable snapshot, idempotently.

    Publication order is object first, then a single database transaction for
    the snapshot, all memberships/links and its optional legacy origin. An
    object left by a failed transaction is unreachable and safely reusable by
    an identical retry.
    """
    if not org or not site_id:
        raise ValueError('Organisation and site ID are required')
    projection = validate_land_evidence(value)
    identity = projection.identity
    if identity.legacy_location_id != site_id:
        raise LandEvidenceSnapshotConflict('Projection site does not match persistence site')
    _validate_origin_assessment(org, site_id, origin_assessment_id, projection)

    content_hash = snapshot_content_hash(projection)
    snapshot_id = _snapshot_id(org, site_id, projection, content_hash)
    assessment_fingerprint = identity.legacy_assessment_fingerprint
    created = core.now()

    with core.engine.connect() as connection:
        existing = _get_row(connection, snapshot_id, org)
    if existing:
        record = _verify_existing(
            existing, snapshot_id=snapshot_id, org=org, site_id=site_id,
            projection=projection, content_hash=content_hash,
        )
        _record_origin_idempotently(
            snapshot_id, org, origin_assessment_id, assessment_fingerprint, created,
        )
        return record

    manifest = _canonical_bytes(projection.model_dump(mode='json'))
    manifest_sha256 = sha256(manifest).hexdigest()
    manifest_key = (
        f'land-evidence/{fingerprint(org)}/{fingerprint(site_id)}/{identity.boundary_version}/'
        f'{content_hash}/{manifest_sha256}.json'
    )
    core.store_object_immutable(manifest_key, manifest)
    verified = core.load_object(manifest_key)
    if verified != manifest or sha256(verified).hexdigest() != manifest_sha256:
        raise LandEvidenceSnapshotError('Snapshot manifest did not verify after immutable write')

    row = {
        'id': snapshot_id, 'org': org, 'site_id': site_id,
        'boundary_version': identity.boundary_version,
        'boundary_geometry_fingerprint': identity.boundary_geometry_fingerprint,
        'schema_version': identity.schema_version,
        'registry_version': identity.registry_version,
        'content_hash': content_hash, 'manifest_sha256': manifest_sha256,
        'manifest_key': manifest_key, 'created': created,
    }
    try:
        with core.engine.begin() as connection:
            connection.execute(insert(core.land_evidence_snapshots).values(**row))
            _insert_memberships(connection, snapshot_id, projection)
            _add_origin(connection, snapshot_id, org, origin_assessment_id,
                        assessment_fingerprint, created)
    except IntegrityError:
        # A concurrent identical writer may have published first. Resolve by the
        # complete unique content key and reject any contradictory identity.
        with core.engine.connect() as connection:
            existing = _find_content_row(
                connection, org, site_id, identity.boundary_version,
                identity.schema_version, content_hash,
            )
        if not existing:
            raise
        record = _verify_existing(
            existing, snapshot_id=snapshot_id, org=org, site_id=site_id,
            projection=projection, content_hash=content_hash,
        )
        _record_origin_idempotently(
            snapshot_id, org, origin_assessment_id, assessment_fingerprint, created,
        )
        return record
    return _record(row)


def create_snapshot_from_legacy_assessment(
    assessment_id: str, *, org: str,
) -> LandEvidenceSnapshotRecord:
    """Project and persist an existing assessment without updating it."""
    with core.engine.connect() as connection:
        assessment = connection.execute(select(core.assessments).where(
            core.assessments.c.id == assessment_id,
            core.assessments.c.org == org,
        )).mappings().first()
        if not assessment:
            raise LandEvidenceSnapshotNotFound('Assessment not found')
        site = connection.execute(select(core.sites.c.id).where(
            core.sites.c.id == assessment['site_id'], core.sites.c.org == org,
        )).first()
        if not site:
            raise LandEvidenceSnapshotNotFound('Assessment site not found')
        saved = assessment['result']
        if not isinstance(saved, dict):
            raise LandEvidenceSnapshotError('Assessment has no saved result to project')
        assessment = dict(assessment)

    projection = project_land_evidence(saved)
    identity = projection.identity
    if identity.legacy_location_id != assessment['site_id']:
        raise LandEvidenceSnapshotConflict('Saved assessment location does not match its site')
    if identity.boundary_version != assessment['version']:
        raise LandEvidenceSnapshotConflict('Saved assessment boundary version does not match its row')
    if identity.boundary_geometry_fingerprint != fingerprint(assessment['geometry']):
        raise LandEvidenceSnapshotConflict('Saved assessment boundary geometry does not match its row')
    return persist_land_evidence_snapshot(
        projection, org=org, site_id=assessment['site_id'],
        origin_assessment_id=assessment_id,
    )


def get_land_evidence_snapshot(snapshot_id: str, *, org: str) -> LandEvidenceSnapshotRecord:
    """Resolve metadata only inside the supplied organisation scope."""
    with core.engine.connect() as connection:
        row = _get_row(connection, snapshot_id, org)
    if not row:
        raise LandEvidenceSnapshotNotFound('Snapshot not found')
    return _record(row)


def list_land_evidence_snapshots(
    *, org: str, site_id: str, boundary_version: int | None = None,
) -> list[LandEvidenceSnapshotRecord]:
    """Find committed snapshots for an organisation's parcel/boundary."""
    query = select(core.land_evidence_snapshots).where(
        core.land_evidence_snapshots.c.org == org,
        core.land_evidence_snapshots.c.site_id == site_id,
    )
    if boundary_version is not None:
        query = query.where(core.land_evidence_snapshots.c.boundary_version == boundary_version)
    query = query.order_by(core.land_evidence_snapshots.c.created.desc())
    with core.engine.connect() as connection:
        return [_record(dict(row)) for row in connection.execute(query).mappings()]


def load_land_evidence_snapshot(
    snapshot_id: str, *, org: str,
) -> LandEvidenceProjection:
    """Load and revalidate a committed private manifest."""
    with core.engine.connect() as connection:
        row = _get_row(connection, snapshot_id, org)
    if not row:
        raise LandEvidenceSnapshotNotFound('Snapshot not found')
    manifest = core.load_object(row['manifest_key'])
    if manifest is None:
        raise LandEvidenceSnapshotConflict('Committed snapshot manifest is missing')
    try:
        projection = validate_land_evidence(json.loads(manifest))
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        raise LandEvidenceSnapshotConflict('Committed snapshot manifest is invalid') from error
    _verify_existing(
        row, snapshot_id=snapshot_id, org=org, site_id=row['site_id'],
        projection=projection,
        content_hash=row['content_hash'],
    )
    return projection
