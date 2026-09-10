"""Minimal immutable execution records for the existing wetland module."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from backend import core
from backend.earth import fingerprint
from backend.land_evidence_store import (
    LandEvidenceSnapshotConflict,
    load_land_evidence_snapshot,
    get_land_evidence_snapshot,
)
from backend.wetland import MODEL_VERSION, run_wetland
from backend.wetland_binding import BINDING_VERSION, bind_wetland_input


MODULE_ID = 'wetland_restoration'


class ModuleRunError(RuntimeError):
    """Base class for module-run persistence and integrity failures."""


class ModuleRunNotFound(ModuleRunError):
    """The run is absent or belongs to another organisation."""


class ModuleRunConflict(ModuleRunError):
    """An immutable run row contradicts its deterministic identity/content."""


class ModuleRunRecord(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: str
    org: str
    site_id: str
    boundary_version: int
    evidence_snapshot_id: str
    evidence_content_hash: str
    module_id: str
    module_version: str
    input_binding_version: str
    model_signature: str
    model_spec: dict[str, Any]
    result: dict[str, Any]
    content_hash: str
    created: datetime
    completed: datetime


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
        allow_nan=False,
    ).encode('utf-8')


def module_run_identity(
    *, org: str, evidence_snapshot_id: str, module_id: str,
    module_version: str, input_binding_version: str, model_signature: str,
) -> str:
    """Return the deterministic execution identity for idempotent reuse."""
    return 'module-run:' + fingerprint([
        org, evidence_snapshot_id, module_id, module_version,
        input_binding_version, model_signature,
    ])


def _content_document(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: row[key] for key in (
            'id', 'org', 'site_id', 'boundary_version', 'evidence_snapshot_id',
            'evidence_content_hash', 'module_id', 'module_version',
            'input_binding_version', 'model_signature', 'model_spec', 'result',
        )
    }


def _content_hash(row: dict[str, Any]) -> str:
    return sha256(_canonical_bytes(_content_document(row))).hexdigest()


def _record(row) -> ModuleRunRecord:
    return ModuleRunRecord.model_validate(dict(row))


def _verify(row: dict[str, Any]) -> ModuleRunRecord:
    expected_id = module_run_identity(
        org=row['org'], evidence_snapshot_id=row['evidence_snapshot_id'],
        module_id=row['module_id'], module_version=row['module_version'],
        input_binding_version=row['input_binding_version'],
        model_signature=row['model_signature'],
    )
    if row['id'] != expected_id:
        raise ModuleRunConflict('Stored ModuleRun deterministic identity mismatch')
    if row['content_hash'] != _content_hash(row):
        raise ModuleRunConflict('Stored ModuleRun content hash mismatch')
    if row['model_spec'].get('signature') != row['model_signature']:
        raise ModuleRunConflict('Stored ModuleRun model signature mismatch')
    if row['result'].get('signature') != row['model_signature']:
        raise ModuleRunConflict('Stored ModuleRun result signature mismatch')
    if row['result'].get('model_version') != row['module_version']:
        raise ModuleRunConflict('Stored ModuleRun result version mismatch')
    return _record(row)


def _get_row(run_id: str, org: str) -> dict[str, Any] | None:
    with core.engine.connect() as connection:
        row = connection.execute(select(core.module_runs).where(
            core.module_runs.c.id == run_id,
            core.module_runs.c.org == org,
        )).mappings().first()
    return dict(row) if row else None


def get_module_run(run_id: str, *, org: str) -> ModuleRunRecord:
    """Load and integrity-check one run within its organisation scope."""
    row = _get_row(run_id, org)
    if row is None:
        raise ModuleRunNotFound('ModuleRun not found')
    return _verify(row)


def _boundary_geometry(*, org: str, site_id: str, boundary_version: int,
                       expected_fingerprint: str) -> dict[str, Any]:
    with core.engine.connect() as connection:
        site = connection.execute(select(core.sites).where(
            core.sites.c.id == site_id,
            core.sites.c.org == org,
        )).mappings().first()
    if not site:
        raise ModuleRunNotFound('Snapshot site not found')
    geometry = site['geometry'] if site['version'] == boundary_version else None
    if geometry is None:
        payload = core.load_object(f'{org}/boundaries/{site_id}/{boundary_version}.json')
        if payload is not None:
            try:
                geometry = core.boundary(json.loads(payload))
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                raise LandEvidenceSnapshotConflict('Saved boundary object is invalid') from error
    if geometry is None:
        raise LandEvidenceSnapshotConflict('Immutable snapshot boundary geometry is unavailable')
    if fingerprint(geometry) != expected_fingerprint:
        raise LandEvidenceSnapshotConflict('Snapshot boundary geometry fingerprint mismatch')
    return geometry


def _persist(row: dict[str, Any]) -> ModuleRunRecord:
    existing = _get_row(row['id'], row['org'])
    if existing is not None:
        record = _verify(existing)
        if _content_document(existing) != _content_document(row):
            raise ModuleRunConflict('Existing ModuleRun contradicts deterministic execution')
        return record
    try:
        with core.engine.begin() as connection:
            connection.execute(insert(core.module_runs).values(**row))
    except IntegrityError:
        existing = _get_row(row['id'], row['org'])
        if existing is None:
            raise
        record = _verify(existing)
        if _content_document(existing) != _content_document(row):
            raise ModuleRunConflict('Concurrent ModuleRun contradicts deterministic execution')
        return record
    return _record(row)


def run_wetland_from_snapshot(
    snapshot_id: str, *, org: str, binding_version: str = BINDING_VERSION,
    spec: dict[str, Any],
) -> ModuleRunRecord:
    """Validate one committed snapshot, bind it, run wetland v0.1 and persist.

    The path performs no network acquisition and never updates the Evidence
    Snapshot or a legacy assessment.
    """
    if binding_version != BINDING_VERSION:
        raise ValueError('Unsupported wetland input binding: ' + binding_version)
    snapshot_record = get_land_evidence_snapshot(snapshot_id, org=org)
    projection = load_land_evidence_snapshot(snapshot_id, org=org)
    geometry = _boundary_geometry(
        org=org, site_id=snapshot_record.site_id,
        boundary_version=snapshot_record.boundary_version,
        expected_fingerprint=snapshot_record.boundary_geometry_fingerprint,
    )
    pinned_spec = deepcopy(spec)
    state = bind_wetland_input(
        projection, geometry, binding_version=binding_version,
    )
    created = core.now()
    result = run_wetland(state, pinned_spec)
    completed = core.now()
    if result['model_version'] != MODEL_VERSION:
        raise ModuleRunError('Wetland implementation returned an unexpected module version')

    row = {
        'id': module_run_identity(
            org=org, evidence_snapshot_id=snapshot_id, module_id=MODULE_ID,
            module_version=result['model_version'], input_binding_version=binding_version,
            model_signature=result['signature'],
        ),
        'org': org,
        'site_id': snapshot_record.site_id,
        'boundary_version': snapshot_record.boundary_version,
        'evidence_snapshot_id': snapshot_id,
        'evidence_content_hash': snapshot_record.content_hash,
        'module_id': MODULE_ID,
        'module_version': result['model_version'],
        'input_binding_version': binding_version,
        'model_signature': result['signature'],
        'model_spec': pinned_spec,
        'result': result,
        'created': created,
        'completed': completed,
    }
    row['content_hash'] = _content_hash(row)
    return _persist(row)
