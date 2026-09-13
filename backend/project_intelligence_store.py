"""Immutable execution records for Project Intelligence v1."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from backend import core
from backend.earth import fingerprint
from backend.project_evidence_binding import (
    BINDING_VERSION, BindingSelection, ProjectEvidenceBinding,
    load_project_evidence_binding, verify_project_evidence_binding,
)
from backend.project_intelligence import (
    MODEL_VERSION, MODULE_ID, ProjectIntelligenceResult,
    build_project_intelligence, project_intelligence_spec,
)


class ProjectIntelligenceError(RuntimeError):
    """Base class for Project Intelligence persistence failures."""


class ProjectIntelligenceNotFound(ProjectIntelligenceError):
    """The run is absent or outside the organisation scope."""


class ProjectIntelligenceConflict(ProjectIntelligenceError):
    """Committed evidence, specification or result fails integrity checks."""


@dataclass(frozen=True)
class ProjectIntelligenceImplementation:
    module_id: str
    module_version: str
    input_binding_version: str
    specification: Callable[[], dict[str, Any]]
    execute: Callable[..., ProjectIntelligenceResult]


V1_IMPLEMENTATION = ProjectIntelligenceImplementation(
    module_id=MODULE_ID,
    module_version=MODEL_VERSION,
    input_binding_version=BINDING_VERSION,
    specification=project_intelligence_spec,
    execute=build_project_intelligence,
)
IMPLEMENTATIONS = {
    (V1_IMPLEMENTATION.module_id, V1_IMPLEMENTATION.module_version,
     V1_IMPLEMENTATION.input_binding_version): V1_IMPLEMENTATION,
}
CURRENT_IMPLEMENTATION_KEY = (
    MODULE_ID, MODEL_VERSION, BINDING_VERSION,
)


def _implementation(key: tuple[str, str, str]) -> ProjectIntelligenceImplementation:
    try:
        return IMPLEMENTATIONS[key]
    except KeyError as error:
        raise ProjectIntelligenceConflict(
            'Project Intelligence run uses an unsupported historical implementation'
        ) from error


class Record(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, frozen=True)


class ProjectIntelligenceRunRequest(BindingSelection):
    pass


class ProjectIntelligenceRunRecord(Record):
    id: str
    org: str
    project_subject_id: str
    evidence_binding_id: str
    evidence_binding_content_hash: str
    module_id: str
    module_version: str
    input_binding_version: str
    model_signature: str
    evidence_binding: ProjectEvidenceBinding
    model_spec: dict[str, Any]
    result: ProjectIntelligenceResult
    content_hash: str
    created: datetime
    completed: datetime


class ProjectIntelligenceRunSummary(Record):
    id: str
    org: str
    project_subject_id: str
    evidence_binding_id: str
    evidence_binding_content_hash: str
    module_id: str
    module_version: str
    input_binding_version: str
    model_signature: str
    content_hash: str
    evidence_as_of: datetime
    evidence_bundle_ids: list[str] = Field(min_length=1)
    created: datetime
    completed: datetime


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
        allow_nan=False,
    ).encode('utf-8')


def project_intelligence_run_identity(
    *, org: str, project_subject_id: str, evidence_binding_id: str,
    module_id: str, module_version: str, input_binding_version: str,
    model_signature: str,
) -> str:
    return 'project-intelligence-run:' + fingerprint([
        org, project_subject_id, evidence_binding_id, module_id,
        module_version, input_binding_version, model_signature,
    ])


def _content_document(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row[key] for key in (
        'id', 'org', 'project_subject_id', 'evidence_binding_id',
        'evidence_binding_content_hash', 'module_id', 'module_version',
        'input_binding_version', 'model_signature', 'evidence_binding',
        'model_spec', 'result', 'created', 'completed',
    )}


def _content_hash(row: dict[str, Any]) -> str:
    return sha256(_canonical_bytes(_content_document(row))).hexdigest()


def _record(row: dict[str, Any]) -> ProjectIntelligenceRunRecord:
    return ProjectIntelligenceRunRecord.model_validate(row)


def _get_row(run_id: str, *, org: str) -> dict[str, Any] | None:
    with core.engine.connect() as connection:
        row = connection.execute(select(core.project_intelligence_runs).where(
            core.project_intelligence_runs.c.id == run_id,
            core.project_intelligence_runs.c.org == org,
        )).mappings().first()
    return dict(row) if row else None


def _verify(row: dict[str, Any], *, reconstruct: bool = True) -> ProjectIntelligenceRunRecord:
    try:
        record = _record(row)
        expected_id = project_intelligence_run_identity(
            org=record.org, project_subject_id=record.project_subject_id,
            evidence_binding_id=record.evidence_binding_id,
            module_id=record.module_id, module_version=record.module_version,
            input_binding_version=record.input_binding_version,
            model_signature=record.model_signature,
        )
        normalized = record.model_dump(mode='json')
        if record.id != expected_id or record.content_hash != _content_hash(normalized):
            raise ValueError('Run identity or content hash mismatch')
        binding = verify_project_evidence_binding(record.evidence_binding)
        implementation = _implementation((
            record.module_id, record.module_version,
            record.input_binding_version,
        ))
        if (record.project_subject_id != binding.project_subject.id
                or record.evidence_binding_id != binding.id
                or record.evidence_binding_content_hash != binding.content_hash):
            raise ValueError('Run envelope contradicts its binding')
        expected_spec = implementation.specification()
        if record.model_spec != expected_spec or record.model_signature != expected_spec['signature']:
            raise ValueError('Run specification is unsupported or contradictory')
        expected_result = implementation.execute(binding, spec=expected_spec)
        if record.result != expected_result:
            raise ValueError('Stored result contradicts its evidence binding')
        if reconstruct:
            rebuilt = load_project_evidence_binding(
                record.project_subject_id,
                [bundle.id for bundle in binding.bundles], org=record.org,
            )
            if rebuilt != binding:
                raise ValueError('Stored binding contradicts committed evidence')
        return record
    except ProjectIntelligenceConflict:
        raise
    except Exception as error:
        raise ProjectIntelligenceConflict(
            'Project Intelligence run integrity check failed'
        ) from error


def run_project_intelligence(
    project_subject_id: str,
    value: ProjectIntelligenceRunRequest | dict[str, Any], *, org: str,
) -> ProjectIntelligenceRunRecord:
    request = (value if isinstance(value, ProjectIntelligenceRunRequest)
               else ProjectIntelligenceRunRequest.model_validate(value))
    binding = load_project_evidence_binding(
        project_subject_id, request.evidence_bundle_ids, org=org,
    )
    implementation = _implementation(CURRENT_IMPLEMENTATION_KEY)
    spec = implementation.specification()
    result = implementation.execute(binding, spec=spec)
    timestamp = core.now()
    row = {
        'id': project_intelligence_run_identity(
            org=org, project_subject_id=project_subject_id,
            evidence_binding_id=binding.id, module_id=implementation.module_id,
            module_version=implementation.module_version,
            input_binding_version=implementation.input_binding_version,
            model_signature=spec['signature'],
        ),
        'org': org, 'project_subject_id': project_subject_id,
        'evidence_binding_id': binding.id,
        'evidence_binding_content_hash': binding.content_hash,
        'module_id': implementation.module_id,
        'module_version': implementation.module_version,
        'input_binding_version': implementation.input_binding_version,
        'model_signature': spec['signature'],
        'evidence_binding': binding.model_dump(mode='json'),
        'model_spec': spec, 'result': result.model_dump(mode='json'),
        'created': timestamp, 'completed': timestamp,
    }
    normalized = _record({**row, 'content_hash': 'pending'})
    candidate = normalized.model_copy(update={
        'content_hash': _content_hash(normalized.model_dump(mode='json')),
    })
    candidate = _verify(candidate.model_dump(mode='json'), reconstruct=False)
    try:
        with core.engine.begin() as connection:
            connection.execute(insert(core.project_intelligence_runs).values(
                **candidate.model_dump(mode='json')
            ))
    except IntegrityError:
        winner = _get_row(candidate.id, org=org)
        if winner is None:
            raise
        return _verify(winner)
    return _verify(candidate.model_dump(mode='json'))


def get_project_intelligence_run(
    run_id: str, *, org: str,
) -> ProjectIntelligenceRunRecord:
    row = _get_row(run_id, org=org)
    if row is None:
        raise ProjectIntelligenceNotFound('Project Intelligence run not found')
    return _verify(row)


def _summary(record: ProjectIntelligenceRunRecord) -> ProjectIntelligenceRunSummary:
    return ProjectIntelligenceRunSummary(
        **record.model_dump(exclude={'evidence_binding', 'model_spec', 'result'}),
        evidence_as_of=record.evidence_binding.evidence_as_of,
        evidence_bundle_ids=[bundle.id for bundle in record.evidence_binding.bundles],
    )


def list_project_intelligence_runs(
    project_subject_id: str, *, org: str,
) -> list[ProjectIntelligenceRunSummary]:
    # Resolve ownership even when no runs exist.
    from backend.project_evidence import get_project_subject
    get_project_subject(project_subject_id, org=org)
    with core.engine.connect() as connection:
        rows = [dict(row) for row in connection.execute(select(
            core.project_intelligence_runs,
        ).where(
            core.project_intelligence_runs.c.org == org,
            core.project_intelligence_runs.c.project_subject_id
            == project_subject_id,
        ).order_by(
            core.project_intelligence_runs.c.created.desc(),
            core.project_intelligence_runs.c.id,
        )).mappings()]
    return [_summary(_verify(row)) for row in rows]
