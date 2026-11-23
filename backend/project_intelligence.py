"""Pure deterministic Project Intelligence v1 reasoning."""
from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import Field

from backend.earth import fingerprint
from backend.project_evidence import Record
from backend.project_evidence_binding import (
    BINDING_VERSION, BoundClaim, ProjectEvidenceBinding,
    verify_project_evidence_binding,
)


MODULE_ID = 'project_intelligence'
MODEL_VERSION = 'project_intelligence_v1'
LIMITATIONS = [
    'This deterministic result interprets attributed source assertions; it does not independently verify that an assertion is true.',
    'Newer publication or recording time never resolves a conflict without an explicit correction relationship.',
    'Evidence completeness is not predictive confidence. No risk, opportunity or recommendation is produced.',
]

EvidenceState = Literal['supported', 'conflicting', 'insufficient_evidence']
ReportedStageValue = Literal[
    'pre_planning', 'planning', 'consented', 'construction',
    'construction_complete', 'unclear',
]


class EvidenceReference(Record):
    claim_id: str
    source_record_id: str
    source_version: str
    source_content_hash: str
    source_record_hash: str
    exact_passage: str
    bundle_ids: list[str]


class StatusFinding(Record):
    predicate: Literal['planning_status', 'construction_status']
    evidence_state: EvidenceState
    values: list[str]
    unknown_claim_ids: list[str]
    references: list[EvidenceReference]


class ReportedStage(Record):
    value: ReportedStageValue
    evidence_state: EvidenceState
    references: list[EvidenceReference]


class GridTarget(Record):
    date: date
    temporal_state: Literal['future_target', 'elapsed_unverified']
    references: list[EvidenceReference]


class GridTargetFinding(Record):
    evidence_state: EvidenceState
    targets: list[GridTarget]
    unknown_claim_ids: list[str]
    references: list[EvidenceReference]


class ConflictValue(Record):
    value: str
    claim_ids: list[str]
    references: list[EvidenceReference]


class ConflictGroup(Record):
    id: str
    predicate: Literal[
        'planning_status', 'construction_status',
        'target_grid_connection_date',
    ]
    values: list[ConflictValue]


class UnresolvedQuestion(Record):
    id: str
    code: Literal[
        'missing_planning_status', 'unknown_planning_status',
        'conflicting_planning_status', 'missing_construction_status',
        'unknown_construction_status', 'conflicting_construction_status',
        'missing_grid_target', 'unknown_grid_target',
        'conflicting_grid_target', 'elapsed_grid_target_unverified',
    ]
    text: str
    references: list[EvidenceReference] = Field(default_factory=list)


class ProjectIntelligenceResult(Record):
    module_id: Literal['project_intelligence'] = MODULE_ID
    model_version: Literal['project_intelligence_v1'] = MODEL_VERSION
    input_binding_version: Literal['project_evidence_binding_v1'] = BINDING_VERSION
    signature: str
    project_subject_id: str
    project_subject_content_hash: str
    evidence_binding_id: str
    evidence_binding_content_hash: str
    evidence_as_of: str
    reported_stage: ReportedStage
    planning_status: StatusFinding
    construction_status: StatusFinding
    grid_connection_target: GridTargetFinding
    conflicts: list[ConflictGroup]
    unresolved_questions: list[UnresolvedQuestion]
    limitations: list[str]


PLANNING_STAGE_MAP = {
    'not_submitted': 'pre_planning',
    'submitted': 'planning',
    'under_review': 'planning',
    'approved': 'consented',
}
CONSTRUCTION_STAGE_MAP = {
    'preparation': 'construction',
    'under_construction': 'construction',
    'paused': 'construction',
    'completed': 'construction_complete',
}


def project_intelligence_spec() -> dict[str, Any]:
    body = {
        'module_id': MODULE_ID,
        'model_version': MODEL_VERSION,
        'input_binding_version': BINDING_VERSION,
        'result_contract_hash': fingerprint(ProjectIntelligenceResult.model_json_schema()),
        'rules': {
            'planning_stage_map': PLANNING_STAGE_MAP,
            'construction_stage_map': CONSTRUCTION_STAGE_MAP,
            'explicit_supersession_only': True,
            'recency_resolution': 'never',
            'target_clock': 'evidence_as_of',
            'unknown_conflict_policy': 'visible_not_conflicting',
            'limitations': LIMITATIONS,
        },
    }
    return {**body, 'signature': fingerprint(body)}


def _reference(item: BoundClaim) -> EvidenceReference:
    return EvidenceReference(
        claim_id=item.claim.id, source_record_id=item.source_record_id,
        source_version=item.source_version,
        source_content_hash=item.source_content_hash,
        source_record_hash=item.source_record_hash,
        exact_passage=item.claim.locator.exact_passage,
        bundle_ids=item.bundle_ids,
    )


def _active(binding: ProjectEvidenceBinding, predicate: str) -> list[BoundClaim]:
    active = set(binding.active_claim_ids)
    return sorted((item for item in binding.claims
                   if item.claim.id in active and item.claim.predicate == predicate),
                  key=lambda item: item.claim.id)


def _status_finding(binding: ProjectEvidenceBinding, predicate: str) -> StatusFinding:
    items = _active(binding, predicate)
    known = sorted({item.claim.value for item in items if item.claim.value != 'unknown'})
    unknown = sorted(item.claim.id for item in items if item.claim.value == 'unknown')
    state: EvidenceState = ('insufficient_evidence' if not known else
                            'supported' if len(known) == 1 else 'conflicting')
    return StatusFinding(
        predicate=predicate, evidence_state=state, values=known,
        unknown_claim_ids=unknown, references=[_reference(item) for item in items],
    )


def _conflict_group(predicate: str, items: list[BoundClaim]) -> ConflictGroup | None:
    groups: dict[str, list[BoundClaim]] = {}
    for item in items:
        value = item.claim.value
        if predicate == 'target_grid_connection_date':
            if value.state == 'unknown':
                continue
            key = value.date.isoformat()
        else:
            if value == 'unknown':
                continue
            key = value
        groups.setdefault(key, []).append(item)
    if len(groups) <= 1:
        return None
    return ConflictGroup(
        id='conflict:' + predicate, predicate=predicate,
        values=[ConflictValue(
            value=value,
            claim_ids=sorted(item.claim.id for item in grouped),
            references=[_reference(item) for item in sorted(
                grouped, key=lambda candidate: candidate.claim.id,
            )],
        ) for value, grouped in sorted(groups.items())],
    )


def _reported_stage(
    planning: StatusFinding, construction: StatusFinding,
) -> ReportedStage:
    references = construction.references + planning.references
    construction_values = set(construction.values)
    if 'cancelled' in construction_values:
        return ReportedStage(
            value='unclear',
            evidence_state=('conflicting' if len(construction_values) > 1
                            else 'insufficient_evidence'),
            references=references,
        )
    construction_classes = {
        CONSTRUCTION_STAGE_MAP[value] for value in construction_values
        if value in CONSTRUCTION_STAGE_MAP
    }
    unmapped_construction = construction_values - set(CONSTRUCTION_STAGE_MAP)
    if unmapped_construction and construction_classes:
        return ReportedStage(
            value='unclear', evidence_state='conflicting', references=references,
        )
    if len(construction_classes) > 1:
        return ReportedStage(
            value='unclear', evidence_state='conflicting', references=references,
        )
    if len(construction_classes) == 1:
        return ReportedStage(
            value=next(iter(construction_classes)), evidence_state='supported',
            references=references,
        )

    planning_values = set(planning.values)
    if planning_values & {'refused', 'withdrawn'}:
        mapped = {value for value in planning_values if value in PLANNING_STAGE_MAP}
        return ReportedStage(
            value='unclear',
            evidence_state=('conflicting' if mapped else 'insufficient_evidence'),
            references=references,
        )
    planning_classes = {
        PLANNING_STAGE_MAP[value] for value in planning_values
        if value in PLANNING_STAGE_MAP
    }
    if len(planning_classes) > 1:
        return ReportedStage(
            value='unclear', evidence_state='conflicting', references=references,
        )
    if len(planning_classes) == 1:
        return ReportedStage(
            value=next(iter(planning_classes)), evidence_state='supported',
            references=references,
        )
    return ReportedStage(
        value='unclear', evidence_state='insufficient_evidence',
        references=references,
    )


def _grid_finding(binding: ProjectEvidenceBinding) -> GridTargetFinding:
    items = _active(binding, 'target_grid_connection_date')
    known: dict[date, list[BoundClaim]] = {}
    unknown: list[str] = []
    for item in items:
        if item.claim.value.state == 'unknown':
            unknown.append(item.claim.id)
        else:
            known.setdefault(item.claim.value.date, []).append(item)
    state: EvidenceState = ('insufficient_evidence' if not known else
                            'supported' if len(known) == 1 else 'conflicting')
    as_of = binding.evidence_as_of.date()
    targets = [GridTarget(
        date=target,
        temporal_state=('elapsed_unverified' if target < as_of else 'future_target'),
        references=[_reference(item) for item in sorted(
            grouped, key=lambda candidate: candidate.claim.id,
        )],
    ) for target, grouped in sorted(known.items())]
    return GridTargetFinding(
        evidence_state=state, targets=targets,
        unknown_claim_ids=sorted(unknown),
        references=[_reference(item) for item in items],
    )


def _questions(
    planning: StatusFinding, construction: StatusFinding,
    grid: GridTargetFinding, conflicts: list[ConflictGroup],
) -> list[UnresolvedQuestion]:
    questions: list[UnresolvedQuestion] = []
    status_config = (
        (planning, 'planning', 'planning status'),
        (construction, 'construction', 'construction status'),
    )
    conflict_by_predicate = {item.predicate: item for item in conflicts}
    for finding, prefix, label in status_config:
        if finding.evidence_state == 'insufficient_evidence':
            questions.append(UnresolvedQuestion(
                id='question:missing-' + prefix,
                code='missing_' + prefix + '_status',
                text=f'What source-backed evidence establishes the project’s {label}?',
                references=finding.references,
            ))
        if finding.unknown_claim_ids:
            questions.append(UnresolvedQuestion(
                id='question:unknown-' + prefix,
                code='unknown_' + prefix + '_status',
                text=f'What evidence would resolve the reported unknown {label}?',
                references=finding.references,
            ))
        if finding.evidence_state == 'conflicting':
            conflict = conflict_by_predicate[finding.predicate]
            questions.append(UnresolvedQuestion(
                id='question:conflicting-' + prefix,
                code='conflicting_' + prefix + '_status',
                text=f'Which evidence or explicit correction resolves the conflicting {label} reports?',
                references=[ref for value in conflict.values for ref in value.references],
            ))
    if grid.evidence_state == 'insufficient_evidence':
        questions.append(UnresolvedQuestion(
            id='question:missing-grid-target', code='missing_grid_target',
            text='What source-backed evidence establishes a grid-connection target?',
            references=grid.references,
        ))
    if grid.unknown_claim_ids:
        questions.append(UnresolvedQuestion(
            id='question:unknown-grid-target', code='unknown_grid_target',
            text='What evidence would resolve the unknown grid-connection target?',
            references=grid.references,
        ))
    if grid.evidence_state == 'conflicting':
        conflict = conflict_by_predicate['target_grid_connection_date']
        questions.append(UnresolvedQuestion(
            id='question:conflicting-grid-target', code='conflicting_grid_target',
            text='Which evidence or explicit correction resolves the conflicting grid-connection targets?',
            references=[ref for value in conflict.values for ref in value.references],
        ))
    elapsed = [target for target in grid.targets
               if target.temporal_state == 'elapsed_unverified']
    if elapsed:
        questions.append(UnresolvedQuestion(
            id='question:elapsed-grid-target',
            code='elapsed_grid_target_unverified',
            text='The reported target predates the evidence as-of date; what evidence establishes the current outcome?',
            references=[ref for target in elapsed for ref in target.references],
        ))
    return sorted(questions, key=lambda item: item.id)


def build_project_intelligence(
    value: ProjectEvidenceBinding | dict[str, Any],
    *, spec: dict[str, Any] | None = None,
) -> ProjectIntelligenceResult:
    binding = verify_project_evidence_binding(value)
    expected_spec = project_intelligence_spec()
    if spec is not None and spec != expected_spec:
        raise ValueError('Unsupported or contradictory Project Intelligence specification')
    planning = _status_finding(binding, 'planning_status')
    construction = _status_finding(binding, 'construction_status')
    grid = _grid_finding(binding)
    conflicts = [item for item in (
        _conflict_group('planning_status', _active(binding, 'planning_status')),
        _conflict_group('construction_status', _active(binding, 'construction_status')),
        _conflict_group('target_grid_connection_date', _active(
            binding, 'target_grid_connection_date',
        )),
    ) if item is not None]
    return ProjectIntelligenceResult(
        signature=expected_spec['signature'],
        project_subject_id=binding.project_subject.id,
        project_subject_content_hash=binding.project_subject.content_hash,
        evidence_binding_id=binding.id,
        evidence_binding_content_hash=binding.content_hash,
        evidence_as_of=binding.evidence_as_of.isoformat(),
        reported_stage=_reported_stage(planning, construction),
        planning_status=planning, construction_status=construction,
        grid_connection_target=grid, conflicts=conflicts,
        unresolved_questions=_questions(planning, construction, grid, conflicts),
        limitations=LIMITATIONS,
    )
