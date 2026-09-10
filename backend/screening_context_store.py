"""Intentional assessment action and read-only access to immutable screening runs."""
from __future__ import annotations

from sqlalchemy import select

from backend import core, module_runs
from backend.earth import fingerprint
from backend.land_evidence_store import (
    LandEvidenceSnapshotConflict, create_snapshot_from_legacy_assessment,
    get_land_evidence_snapshot, load_land_evidence_snapshot,
)
from backend.screening_context import (
    BINDING_VERSION, MODULE_ID, MODULE_VERSION, ScreeningConfig, ScreeningResult,
    build_screening_context, screening_spec,
)


class ScreeningUnavailable(ValueError):
    """Saved assessment is not usable by this version; history is preserved."""


def validate_screening_row(row: dict) -> None:
    """Module-specific verification; the generic wetland branch stays unchanged."""
    try:
        result = ScreeningResult.model_validate(row['result'])
        spec = screening_spec(ScreeningConfig.model_validate(row['model_spec']['config']))
        if row['model_spec'] != spec:
            raise ValueError('Unsupported or contradictory screening specification')
        expected = {
            'site_id': result.site_id, 'boundary_version': result.boundary_version,
            'evidence_snapshot_id': result.evidence_snapshot_id,
            'evidence_content_hash': result.evidence_content_hash,
            'module_version': result.model_version,
            'input_binding_version': result.input_binding_version,
            'model_signature': result.signature,
        }
        if any(row[key] != value for key, value in expected.items()) or result.signature != spec['signature']:
            raise ValueError('Screening result envelope mismatch')
    except (ValueError, KeyError, TypeError) as error:
        raise module_runs.ModuleRunConflict('Stored screening contract or specification is invalid') from error


def _calculate(snapshot_id: str, *, org: str, config: ScreeningConfig) -> dict:
    record = get_land_evidence_snapshot(snapshot_id, org=org)
    projection = load_land_evidence_snapshot(snapshot_id, org=org)
    return build_screening_context(
        projection, snapshot_id=record.id, content_hash=record.content_hash, config=config,
    ).model_dump(mode='json')


def run_screening_from_snapshot(snapshot_id: str, *, org: str,
                                config: ScreeningConfig | None = None) -> module_runs.ModuleRunRecord:
    """Resolve committed evidence, calculate without acquisition, insert or reuse."""
    config = config or ScreeningConfig()
    spec = screening_spec(config)
    result = _calculate(snapshot_id, org=org, config=config)
    row = {
        'id': module_runs.module_run_identity(
            org=org, evidence_snapshot_id=snapshot_id, module_id=MODULE_ID,
            module_version=MODULE_VERSION, input_binding_version=BINDING_VERSION,
            model_signature=spec['signature'],
        ),
        'org': org, 'site_id': result['site_id'], 'boundary_version': result['boundary_version'],
        'evidence_snapshot_id': snapshot_id, 'evidence_content_hash': result['evidence_content_hash'],
        'module_id': MODULE_ID, 'module_version': MODULE_VERSION,
        'input_binding_version': BINDING_VERSION, 'model_signature': spec['signature'],
        'model_spec': spec, 'result': result, 'created': core.now(), 'completed': core.now(),
    }
    row['content_hash'] = module_runs._content_hash(row)
    module_runs._verify(row)
    return module_runs._persist(row)


def get_screening_run(run_id: str, *, org: str) -> module_runs.ModuleRunRecord:
    run = module_runs.get_module_run(run_id, org=org)
    if run.module_id != MODULE_ID:
        raise module_runs.ModuleRunNotFound('Screening context not found')
    expected = _calculate(run.evidence_snapshot_id, org=org,
                          config=ScreeningConfig.model_validate(run.model_spec['config']))
    if expected != run.result:
        raise module_runs.ModuleRunConflict('Stored screening result contradicts its committed evidence')
    return run


def _assessment(assessment_id: str, org: str) -> dict:
    with core.engine.connect() as connection:
        row = connection.execute(select(core.assessments).join(
            core.sites, core.sites.c.id == core.assessments.c.site_id,
        ).where(core.assessments.c.id == assessment_id, core.assessments.c.org == org,
                core.sites.c.org == org)).mappings().first()
    if row is None:
        raise module_runs.ModuleRunNotFound('Record not found')
    return dict(row)


def _origin_snapshot(assessment: dict, org: str) -> str | None:
    with core.engine.connect() as connection:
        origins = connection.execute(select(core.land_evidence_snapshot_origins).where(
            core.land_evidence_snapshot_origins.c.assessment_id == assessment['id'],
            core.land_evidence_snapshot_origins.c.org == org,
        )).mappings().all()
    if not origins:
        return None
    if len(origins) != 1:
        raise ScreeningUnavailable('Multiple historical snapshots are associated with this assessment; explicit version selection is not supported in v1.')
    origin = origins[0]
    if origin['assessment_fingerprint'] != fingerprint(assessment['result']):
        raise LandEvidenceSnapshotConflict('Saved assessment contradicts its committed snapshot origin')
    record = get_land_evidence_snapshot(origin['snapshot_id'], org=org)
    load_land_evidence_snapshot(record.id, org=org)
    if (record.site_id != assessment['site_id'] or record.boundary_version != assessment['version']
            or record.boundary_geometry_fingerprint != fingerprint(assessment['geometry'])):
        raise LandEvidenceSnapshotConflict('Snapshot origin boundary contradicts the saved assessment')
    return record.id


def prepare_screening_context(assessment_id: str, *, org: str) -> module_runs.ModuleRunRecord:
    assessment = _assessment(assessment_id, org)
    if assessment['state'] not in ('completed', 'partial') or not isinstance(assessment['result'], dict):
        raise ScreeningUnavailable('Assessment has no usable completed saved result.')
    if not isinstance(assessment['result'].get('environmental_state'), dict):
        raise ScreeningUnavailable('This historical assessment predates supported land evidence. Preserve it and create a new assessment for screening context.')
    snapshot_id = _origin_snapshot(assessment, org)
    if snapshot_id is None:
        snapshot_id = create_snapshot_from_legacy_assessment(assessment_id, org=org).id
    return run_screening_from_snapshot(snapshot_id, org=org)


def read_assessment_context(assessment_id: str, *, org: str) -> module_runs.ModuleRunRecord | None:
    """Discovery only. An ordinary GET never creates snapshots, origins or runs."""
    assessment = _assessment(assessment_id, org)
    snapshot_id = _origin_snapshot(assessment, org)
    if snapshot_id is None:
        if (assessment['state'] in ('completed', 'partial')
                and isinstance(assessment['result'], dict)
                and not isinstance(assessment['result'].get('environmental_state'), dict)):
            raise ScreeningUnavailable(
                'This historical assessment predates supported land evidence. Preserve it and create a new assessment for screening context.'
            )
        return None
    spec = screening_spec()
    with core.engine.connect() as connection:
        run_id = connection.execute(select(core.module_runs.c.id).where(
            core.module_runs.c.org == org, core.module_runs.c.evidence_snapshot_id == snapshot_id,
            core.module_runs.c.module_id == MODULE_ID, core.module_runs.c.module_version == MODULE_VERSION,
            core.module_runs.c.input_binding_version == BINDING_VERSION,
            core.module_runs.c.model_signature == spec['signature'],
        )).scalar_one_or_none()
    return get_screening_run(run_id, org=org) if run_id else None
