"""Deterministic binding of explicit Project Evidence bundle sets."""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.earth import fingerprint
from backend.project_evidence import (
    ProjectClaim, ProjectEvidenceBundleRead, ProjectSubjectIdentity,
    ProjectSubjectRecord, SourceRecord, get_project_evidence,
    get_project_subject,
)


BINDING_VERSION = 'project_evidence_binding_v1'
MAX_BUNDLES = 100


class ProjectEvidenceBindingError(ValueError):
    """An explicit bundle selection cannot form a closed deterministic binding."""


class Record(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, frozen=True)


class BindingSelection(Record):
    evidence_bundle_ids: list[str] = Field(min_length=1, max_length=MAX_BUNDLES)

    @model_validator(mode='after')
    def unique_ids(self):
        if len(set(self.evidence_bundle_ids)) != len(self.evidence_bundle_ids):
            raise ValueError('Evidence bundle IDs must be unique')
        return self


class SourceVersionIdentity(Record):
    id: str
    source_version: str
    content_hash: str
    record_hash: str


class BoundBundle(Record):
    id: str
    content_hash: str
    manifest_sha256: str
    schema_version: Literal['project_evidence_v1']
    source_versions: list[SourceVersionIdentity]
    claim_ids: list[str]
    land_evidence_snapshot_id: str | None


class BoundSource(Record):
    source: SourceRecord
    record_hash: str
    bundle_ids: list[str]


class BoundClaim(Record):
    claim: ProjectClaim
    claim_hash: str
    source_record_id: str
    source_version: str
    source_content_hash: str
    source_record_hash: str
    bundle_ids: list[str]


class ProjectEvidenceBinding(Record):
    id: str
    binding_version: Literal['project_evidence_binding_v1'] = BINDING_VERSION
    content_hash: str
    project_subject: ProjectSubjectIdentity
    bundles: list[BoundBundle] = Field(min_length=1, max_length=MAX_BUNDLES)
    sources: list[BoundSource] = Field(min_length=1)
    claims: list[BoundClaim] = Field(min_length=1)
    active_claim_ids: list[str]
    superseded_claim_ids: list[str]
    evidence_as_of: datetime


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
        allow_nan=False,
    ).encode('utf-8')


def _hash(value: Any) -> str:
    return sha256(_canonical_bytes(value)).hexdigest()


def _subject_identity(subject: ProjectSubjectRecord) -> ProjectSubjectIdentity:
    return ProjectSubjectIdentity(**subject.model_dump(exclude={'created'}))


def _content_document(value: ProjectEvidenceBinding | dict[str, Any]) -> dict[str, Any]:
    data = (value.model_dump(mode='json')
            if isinstance(value, ProjectEvidenceBinding) else dict(value))
    return {key: data[key] for key in (
        'binding_version', 'project_subject', 'bundles', 'sources', 'claims',
        'active_claim_ids', 'superseded_claim_ids', 'evidence_as_of',
    )}


def binding_identity(*, org: str, project_subject_id: str,
                     content_hash: str) -> str:
    return 'project-evidence-binding:' + fingerprint([
        org, project_subject_id, BINDING_VERSION, content_hash,
    ])


def verify_project_evidence_binding(
    value: ProjectEvidenceBinding | dict[str, Any],
) -> ProjectEvidenceBinding:
    binding = (value if isinstance(value, ProjectEvidenceBinding)
               else ProjectEvidenceBinding.model_validate(value))
    calculated_hash = _hash(_content_document(binding))
    expected_id = binding_identity(
        org=binding.project_subject.org,
        project_subject_id=binding.project_subject.id,
        content_hash=calculated_hash,
    )
    if binding.content_hash != calculated_hash or binding.id != expected_id:
        raise ProjectEvidenceBindingError('Project Evidence binding identity mismatch')

    bundle_ids = [bundle.id for bundle in binding.bundles]
    if bundle_ids != sorted(bundle_ids) or len(set(bundle_ids)) != len(bundle_ids):
        raise ProjectEvidenceBindingError('Bound evidence bundles are not canonical')
    source_keys = [(item.source.id, item.source.source_version) for item in binding.sources]
    if source_keys != sorted(source_keys) or len(set(source_keys)) != len(source_keys):
        raise ProjectEvidenceBindingError('Bound source versions are not canonical')
    claim_ids = [item.claim.id for item in binding.claims]
    if claim_ids != sorted(claim_ids) or len(set(claim_ids)) != len(claim_ids):
        raise ProjectEvidenceBindingError('Bound claims are not canonical')

    claims = {item.claim.id: item for item in binding.claims}
    sources = {(item.source.id, item.source.source_version): item
               for item in binding.sources}
    bundle_by_id = {item.id: item for item in binding.bundles}
    for item in binding.sources:
        if (_hash(item.source.model_dump(mode='json')) != item.record_hash
                or not item.bundle_ids
                or not set(item.bundle_ids) <= set(bundle_ids)):
            raise ProjectEvidenceBindingError('Bound source membership or content is invalid')
    targets: set[str] = set()
    for item in binding.claims:
        claim = item.claim
        if claim.project_subject_id != binding.project_subject.id:
            raise ProjectEvidenceBindingError('Bound claim belongs to another Project Subject')
        source = sources.get((item.source_record_id, item.source_version))
        if source is None or source.record_hash != item.source_record_hash:
            raise ProjectEvidenceBindingError('Bound claim source version does not resolve')
        if (source.source.content_hash != item.source_content_hash
                or _hash(claim.model_dump(mode='json')) != item.claim_hash):
            raise ProjectEvidenceBindingError('Bound claim or source content mismatch')
        if not set(item.bundle_ids) <= set(bundle_ids) or not item.bundle_ids:
            raise ProjectEvidenceBindingError('Bound claim bundle membership is invalid')
        target = claim.supersedes_claim_id
        if target is not None:
            if target not in claims:
                raise ProjectEvidenceBindingError(
                    'Selected bundles do not include complete correction ancestry'
                )
            if claims[target].claim.predicate != claim.predicate:
                raise ProjectEvidenceBindingError(
                    'A correction must preserve the superseded claim predicate'
                )
            targets.add(target)

    for bundle_id, bundle in bundle_by_id.items():
        expected_claim_ids = sorted(
            item.claim.id for item in binding.claims
            if bundle_id in item.bundle_ids
        )
        if bundle.claim_ids != expected_claim_ids:
            raise ProjectEvidenceBindingError('Bound bundle claim membership is invalid')
        source_versions = [(item.id, item.source_version)
                           for item in bundle.source_versions]
        if source_versions != sorted(source_versions) or len(set(source_versions)) != len(source_versions):
            raise ProjectEvidenceBindingError('Bound bundle source membership is not canonical')
        expected_sources = sorted(
            (item.source.id, item.source.source_version)
            for item in binding.sources if bundle_id in item.bundle_ids
        )
        if source_versions != expected_sources:
            raise ProjectEvidenceBindingError('Bound bundle source membership is invalid')
        for source_ref in bundle.source_versions:
            source = sources[(source_ref.id, source_ref.source_version)]
            if (source_ref.content_hash != source.source.content_hash
                    or source_ref.record_hash != source.record_hash):
                raise ProjectEvidenceBindingError('Bound bundle source identity is invalid')

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(claim_id: str) -> None:
        if claim_id in visiting:
            raise ProjectEvidenceBindingError('Claim supersession graph contains a cycle')
        if claim_id in visited:
            return
        visiting.add(claim_id)
        target = claims[claim_id].claim.supersedes_claim_id
        if target is not None:
            visit(target)
        visiting.remove(claim_id)
        visited.add(claim_id)

    for claim_id in claims:
        visit(claim_id)

    active = sorted(set(claims) - targets)
    if binding.active_claim_ids != active:
        raise ProjectEvidenceBindingError('Active claim membership mismatch')
    if binding.superseded_claim_ids != sorted(targets):
        raise ProjectEvidenceBindingError('Superseded claim membership mismatch')
    if binding.evidence_as_of != max(item.source.recorded_at for item in binding.sources):
        raise ProjectEvidenceBindingError('Evidence as-of time mismatch')
    return binding


def build_project_evidence_binding(
    subject: ProjectSubjectRecord,
    bundles: list[ProjectEvidenceBundleRead],
) -> ProjectEvidenceBinding:
    if not bundles:
        raise ProjectEvidenceBindingError('Select at least one evidence bundle')
    if len(bundles) > MAX_BUNDLES:
        raise ProjectEvidenceBindingError('Too many evidence bundles selected')
    if len({bundle.id for bundle in bundles}) != len(bundles):
        raise ProjectEvidenceBindingError('Evidence bundle IDs must be unique')

    identity = _subject_identity(subject)
    source_values: dict[tuple[str, str], dict[str, Any]] = {}
    claim_values: dict[str, dict[str, Any]] = {}
    descriptors: list[BoundBundle] = []

    for bundle in sorted(bundles, key=lambda item: item.id):
        if (bundle.project_subject_id != subject.id
                or bundle.org != subject.org
                or bundle.evidence.project_subject != identity):
            raise ProjectEvidenceBindingError(
                'Evidence bundle belongs to another Project Subject'
            )
        local_sources = {source.id: source for source in bundle.evidence.sources}
        source_refs: list[SourceVersionIdentity] = []
        for source in sorted(bundle.evidence.sources,
                             key=lambda item: (item.id, item.source_version)):
            record_hash = _hash(source.model_dump(mode='json'))
            key = (source.id, source.source_version)
            existing = source_values.get(key)
            if existing is not None and existing['record_hash'] != record_hash:
                raise ProjectEvidenceBindingError(
                    'Selected bundles disagree about a stable source version'
                )
            if existing is None:
                source_values[key] = {
                    'source': source, 'record_hash': record_hash,
                    'bundle_ids': {bundle.id},
                }
            else:
                existing['bundle_ids'].add(bundle.id)
            source_refs.append(SourceVersionIdentity(
                id=source.id, source_version=source.source_version,
                content_hash=source.content_hash, record_hash=record_hash,
            ))

        for claim in bundle.evidence.claims:
            source = local_sources[claim.source_record_id]
            source_record_hash = _hash(source.model_dump(mode='json'))
            claim_hash = _hash(claim.model_dump(mode='json'))
            candidate = {
                'claim': claim, 'claim_hash': claim_hash,
                'source_record_id': source.id,
                'source_version': source.source_version,
                'source_content_hash': source.content_hash,
                'source_record_hash': source_record_hash,
            }
            existing = claim_values.get(claim.id)
            if existing is not None and any(
                existing[key] != candidate[key] for key in candidate
            ):
                raise ProjectEvidenceBindingError(
                    'Selected bundles bind a stable claim to different content or source versions'
                )
            if existing is None:
                claim_values[claim.id] = {**candidate, 'bundle_ids': {bundle.id}}
            else:
                existing['bundle_ids'].add(bundle.id)

        descriptors.append(BoundBundle(
            id=bundle.id, content_hash=bundle.content_hash,
            manifest_sha256=bundle.manifest_sha256,
            schema_version=bundle.schema_version,
            source_versions=source_refs,
            claim_ids=sorted(claim.id for claim in bundle.evidence.claims),
            land_evidence_snapshot_id=bundle.land_evidence_snapshot_id,
        ))

    sources = [BoundSource(
        source=value['source'], record_hash=value['record_hash'],
        bundle_ids=sorted(value['bundle_ids']),
    ) for _, value in sorted(source_values.items())]
    claims = [BoundClaim(
        claim=value['claim'], claim_hash=value['claim_hash'],
        source_record_id=value['source_record_id'],
        source_version=value['source_version'],
        source_content_hash=value['source_content_hash'],
        source_record_hash=value['source_record_hash'],
        bundle_ids=sorted(value['bundle_ids']),
    ) for _, value in sorted(claim_values.items())]
    targets = sorted({item.claim.supersedes_claim_id for item in claims
                      if item.claim.supersedes_claim_id is not None})
    selected_claim_ids = {item.claim.id for item in claims}
    missing = sorted(set(targets) - selected_claim_ids)
    if missing:
        raise ProjectEvidenceBindingError(
            'Selected bundles do not include complete correction ancestry: '
            + ', '.join(missing)
        )
    active = sorted(selected_claim_ids - set(targets))
    body = {
        'binding_version': BINDING_VERSION,
        'project_subject': identity.model_dump(mode='json'),
        'bundles': [item.model_dump(mode='json') for item in descriptors],
        'sources': [item.model_dump(mode='json') for item in sources],
        'claims': [item.model_dump(mode='json') for item in claims],
        'active_claim_ids': active,
        'superseded_claim_ids': targets,
        'evidence_as_of': max(item.source.recorded_at for item in sources),
    }
    normalized = ProjectEvidenceBinding.model_validate({
        'id': 'pending',
        'content_hash': 'pending',
        **body,
    })
    content_hash = _hash(_content_document(normalized))
    binding = normalized.model_copy(update={
        'id': binding_identity(
            org=subject.org, project_subject_id=subject.id,
            content_hash=content_hash,
        ),
        'content_hash': content_hash,
    })
    return verify_project_evidence_binding(binding)


def load_project_evidence_binding(
    project_subject_id: str, evidence_bundle_ids: list[str], *, org: str,
) -> ProjectEvidenceBinding:
    selection = BindingSelection(evidence_bundle_ids=evidence_bundle_ids)
    subject = get_project_subject(project_subject_id, org=org)
    bundles = [get_project_evidence(
        project_subject_id, bundle_id, org=org,
    ) for bundle_id in selection.evidence_bundle_ids]
    return build_project_evidence_binding(subject, bundles)
