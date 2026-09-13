"""Typed Project Evidence v1 contracts and immutable persistence.

The records in this module preserve attributed source assertions. They do not
select a winning claim, verify a publisher's assertion, or derive project
stage, risk, confidence, opportunity, recommendation or workflow decisions.
"""
from __future__ import annotations

from datetime import date, datetime
from hashlib import sha256
import json
import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from backend import core
from backend.earth import fingerprint
from backend.land_evidence_store import (
    get_land_evidence_snapshot,
    load_land_evidence_snapshot,
)


SCHEMA_VERSION = 'project_evidence_v1'
IDENTIFIER_PATTERN = r'^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$'
SHA256_FIELD_PATTERN = r'^[0-9a-f]{64}$'
SHA256_PATTERN = re.compile(r'^[0-9a-f]{64}$')

ProjectType = Literal[
    'energy_infrastructure', 'transport_infrastructure',
    'water_infrastructure', 'digital_infrastructure',
    'social_infrastructure', 'other_infrastructure',
]
ProjectPhase = Literal[
    'concept', 'planning', 'pre_construction', 'construction',
    'commissioning', 'operational', 'decommissioning',
]
PlanningStatus = Literal[
    'unknown', 'not_submitted', 'submitted', 'under_review',
    'approved', 'refused', 'withdrawn',
]
ConstructionStatus = Literal[
    'unknown', 'not_started', 'preparation', 'under_construction',
    'paused', 'completed', 'cancelled',
]


class ProjectEvidenceError(RuntimeError):
    """Base class for Project Evidence persistence failures."""


class ProjectNotFound(ProjectEvidenceError):
    """The project is absent or belongs to another organisation."""


class ProjectEvidenceNotFound(ProjectEvidenceError):
    """The evidence bundle is absent or outside the project/tenant scope."""


class ProjectEvidenceValidationError(ProjectEvidenceError, ValueError):
    """A submitted relationship cannot resolve within the authorized graph."""


class ProjectEvidenceConflict(ProjectEvidenceError):
    """Immutable stored identity or content is contradictory."""


class Record(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, frozen=True)


class ProjectCreate(Record):
    name: str = Field(min_length=1, max_length=160)
    project_type: ProjectType
    site_id: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN)

    @field_validator('name')
    @classmethod
    def nonblank_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError('Project name cannot be blank')
        return value


class ProjectRecord(Record):
    id: str = Field(pattern=IDENTIFIER_PATTERN)
    org: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=160)
    project_type: ProjectType
    site_id: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN)
    content_hash: str = Field(pattern=SHA256_FIELD_PATTERN)
    created: datetime


class ProjectIdentity(Record):
    id: str = Field(pattern=IDENTIFIER_PATTERN)
    org: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=160)
    project_type: ProjectType
    site_id: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN)
    content_hash: str = Field(pattern=SHA256_FIELD_PATTERN)


class SourceRecord(Record):
    id: str = Field(pattern=IDENTIFIER_PATTERN)
    source_version: str = Field(min_length=1, max_length=240)
    publisher: str = Field(min_length=1, max_length=240)
    title: str = Field(min_length=1, max_length=500)
    reference: str = Field(min_length=1, max_length=2048)
    published_at: datetime | None = None
    recorded_at: datetime
    retained_excerpt: str = Field(min_length=1, max_length=50_000)
    content_hash: str
    entry_method: Literal['human_submitted_structured']

    @field_validator('published_at', 'recorded_at')
    @classmethod
    def timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError('Source times must include a timezone')
        return value

    @field_validator('content_hash')
    @classmethod
    def valid_sha256(cls, value: str) -> str:
        if not SHA256_PATTERN.fullmatch(value):
            raise ValueError('Source content_hash must be a lowercase SHA-256 digest')
        return value


class EvidenceLocator(Record):
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    exact_passage: str = Field(min_length=1, max_length=20_000)

    @model_validator(mode='after')
    def ordered(self):
        if self.end <= self.start:
            raise ValueError('Evidence locator end must be greater than start')
        return self


class ClaimTime(Record):
    kind: Literal['reported_occurrence', 'future_target', 'unknown']
    effective_or_event_date: date | None = None

    @model_validator(mode='after')
    def consistent(self):
        if self.kind == 'unknown' and self.effective_or_event_date is not None:
            raise ValueError('Unknown claim time cannot contain a date')
        if self.kind != 'unknown' and self.effective_or_event_date is None:
            raise ValueError('Reported occurrences and future targets require a date')
        return self


class ClaimBase(Record):
    id: str = Field(pattern=IDENTIFIER_PATTERN)
    project_id: str = Field(pattern=IDENTIFIER_PATTERN)
    phase: ProjectPhase | None = None
    source_record_id: str = Field(pattern=IDENTIFIER_PATTERN)
    locator: EvidenceLocator
    time: ClaimTime
    supersedes_claim_id: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN)

    @model_validator(mode='after')
    def not_self_superseding(self):
        if self.supersedes_claim_id == self.id:
            raise ValueError('A claim cannot supersede itself')
        return self


class PlanningStatusClaim(ClaimBase):
    predicate: Literal['planning_status']
    value: PlanningStatus
    unknown_reason: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode='after')
    def unknown_is_explicit(self):
        if (self.value == 'unknown') != (self.unknown_reason is not None):
            raise ValueError('Unknown planning status requires only an unknown_reason')
        return self


class ConstructionStatusClaim(ClaimBase):
    predicate: Literal['construction_status']
    value: ConstructionStatus
    unknown_reason: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode='after')
    def unknown_is_explicit(self):
        if (self.value == 'unknown') != (self.unknown_reason is not None):
            raise ValueError('Unknown construction status requires only an unknown_reason')
        return self


class KnownDateValue(Record):
    state: Literal['known']
    date: date


class UnknownDateValue(Record):
    state: Literal['unknown']
    reason: str = Field(min_length=1, max_length=1000)


TargetDateValue = Annotated[
    KnownDateValue | UnknownDateValue, Field(discriminator='state')
]


class TargetGridConnectionDateClaim(ClaimBase):
    predicate: Literal['target_grid_connection_date']
    value: TargetDateValue

    @model_validator(mode='after')
    def target_semantics(self):
        if isinstance(self.value, KnownDateValue):
            if (self.time.kind != 'future_target'
                    or self.time.effective_or_event_date != self.value.date):
                raise ValueError('A known grid-connection date must remain an explicit future target')
        elif self.time.kind != 'unknown' or self.time.effective_or_event_date is not None:
            raise ValueError('An unknown grid-connection date requires unknown time')
        return self


ProjectClaim = Annotated[
    PlanningStatusClaim | ConstructionStatusClaim | TargetGridConnectionDateClaim,
    Field(discriminator='predicate'),
]


class ProjectEvidenceSubmission(Record):
    schema_version: Literal['project_evidence_v1'] = SCHEMA_VERSION
    land_evidence_snapshot_id: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN)
    sources: list[SourceRecord] = Field(min_length=1, max_length=100)
    claims: list[ProjectClaim] = Field(min_length=1, max_length=500)


class LandEvidenceSnapshotLink(Record):
    snapshot_id: str = Field(pattern=IDENTIFIER_PATTERN)
    site_id: str = Field(pattern=IDENTIFIER_PATTERN)
    boundary_version: int = Field(ge=1)
    content_hash: str = Field(pattern=SHA256_FIELD_PATTERN)


class ProjectEvidenceBundle(Record):
    schema_version: Literal['project_evidence_v1'] = SCHEMA_VERSION
    project: ProjectIdentity
    land_evidence_snapshot: LandEvidenceSnapshotLink | None = None
    sources: list[SourceRecord] = Field(min_length=1, max_length=100)
    claims: list[ProjectClaim] = Field(min_length=1, max_length=500)

    @model_validator(mode='after')
    def references_resolve(self):
        source_by_id = {item.id: item for item in self.sources}
        if len(source_by_id) != len(self.sources):
            raise ValueError('Source record IDs must be unique within a bundle')
        claim_by_id = {item.id: item for item in self.claims}
        if len(claim_by_id) != len(self.claims):
            raise ValueError('Claim IDs must be unique within a bundle')
        for claim in self.claims:
            if claim.project_id != self.project.id:
                raise ValueError('Every claim must identify the owning project')
            source = source_by_id.get(claim.source_record_id)
            if source is None:
                raise ValueError('Every claim must reference a source record in its bundle')
            locator = claim.locator
            if (locator.end > len(source.retained_excerpt)
                    or source.retained_excerpt[locator.start:locator.end]
                    != locator.exact_passage):
                raise ValueError('Evidence locator does not match the retained source passage')
        # Relationships within this bundle must be acyclic. Relationships to
        # historical claims are resolved by the organization-scoped store.
        for claim in self.claims:
            seen = {claim.id}
            target = claim.supersedes_claim_id
            while target in claim_by_id:
                if target in seen:
                    raise ValueError('Claim supersession relationships cannot form a cycle')
                seen.add(target)
                target = claim_by_id[target].supersedes_claim_id
        return self


class ProjectEvidenceBundleRecord(Record):
    id: str = Field(pattern=IDENTIFIER_PATTERN)
    org: str = Field(min_length=1, max_length=160)
    project_id: str = Field(pattern=IDENTIFIER_PATTERN)
    schema_version: Literal['project_evidence_v1']
    content_hash: str = Field(pattern=SHA256_FIELD_PATTERN)
    manifest_sha256: str = Field(pattern=SHA256_FIELD_PATTERN)
    source_count: int = Field(ge=1, le=100)
    claim_count: int = Field(ge=1, le=500)
    land_evidence_snapshot_id: str | None = Field(
        default=None, pattern=IDENTIFIER_PATTERN,
    )
    created: datetime


class ProjectEvidenceBundleRead(ProjectEvidenceBundleRecord):
    evidence: ProjectEvidenceBundle


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
        allow_nan=False,
    ).encode('utf-8')


def _hash(value: Any) -> str:
    return sha256(_canonical_bytes(value)).hexdigest()


def _project_content(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row[key] for key in ('id', 'org', 'name', 'project_type', 'site_id')}


def _project_record(row: dict[str, Any]) -> ProjectRecord:
    record = ProjectRecord.model_validate(row)
    if record.content_hash != _hash(_project_content(dict(row))):
        raise ProjectEvidenceConflict('Stored Project content hash mismatch')
    return record


def create_project(value: ProjectCreate | dict[str, Any], *, org: str) -> ProjectRecord:
    data = value if isinstance(value, ProjectCreate) else ProjectCreate.model_validate(value)
    if data.site_id is not None:
        with core.engine.connect() as connection:
            site = connection.execute(select(core.sites.c.id).where(
                core.sites.c.id == data.site_id, core.sites.c.org == org,
            )).first()
        if site is None:
            raise ProjectEvidenceValidationError('Site does not resolve in this organisation')
    row = {
        'id': core.uid(), 'org': org, 'name': data.name,
        'project_type': data.project_type, 'site_id': data.site_id,
        'created': core.now(),
    }
    row['content_hash'] = _hash(_project_content(row))
    with core.engine.begin() as connection:
        connection.execute(insert(core.projects).values(**row))
    return _project_record(row)


def get_project(project_id: str, *, org: str) -> ProjectRecord:
    with core.engine.connect() as connection:
        row = connection.execute(select(core.projects).where(
            core.projects.c.id == project_id, core.projects.c.org == org,
        )).mappings().first()
    if row is None:
        raise ProjectNotFound('Project not found')
    return _project_record(dict(row))


def _project_identity(project: ProjectRecord) -> ProjectIdentity:
    return ProjectIdentity(**project.model_dump(exclude={'created'}))


def _snapshot_link(snapshot_id: str | None, project: ProjectRecord,
                   *, org: str) -> LandEvidenceSnapshotLink | None:
    if snapshot_id is None:
        return None
    if project.site_id is None:
        raise ProjectEvidenceValidationError(
            'A project without a Site cannot link land evidence'
        )
    try:
        snapshot = get_land_evidence_snapshot(snapshot_id, org=org)
        load_land_evidence_snapshot(snapshot_id, org=org)
    except Exception as error:
        from backend.land_evidence_store import LandEvidenceSnapshotNotFound
        if isinstance(error, LandEvidenceSnapshotNotFound):
            raise ProjectEvidenceValidationError(
                'Evidence Snapshot does not resolve in this organisation'
            ) from error
        raise
    if snapshot.site_id != project.site_id:
        raise ProjectEvidenceValidationError(
            'Evidence Snapshot does not belong to the Project Site'
        )
    return LandEvidenceSnapshotLink(
        snapshot_id=snapshot.id, site_id=snapshot.site_id,
        boundary_version=snapshot.boundary_version,
        content_hash=snapshot.content_hash,
    )


def build_bundle(value: ProjectEvidenceSubmission | dict[str, Any], *,
                 project: ProjectRecord, org: str) -> ProjectEvidenceBundle:
    submission = (value if isinstance(value, ProjectEvidenceSubmission)
                  else ProjectEvidenceSubmission.model_validate(value))
    return ProjectEvidenceBundle(
        project=_project_identity(project),
        land_evidence_snapshot=_snapshot_link(
            submission.land_evidence_snapshot_id, project, org=org,
        ),
        sources=sorted(submission.sources, key=lambda item: item.id),
        claims=sorted(submission.claims, key=lambda item: item.id),
    )


def bundle_content_hash(bundle: ProjectEvidenceBundle | dict[str, Any]) -> str:
    value = (bundle if isinstance(bundle, ProjectEvidenceBundle)
             else ProjectEvidenceBundle.model_validate(bundle))
    return _hash(value.model_dump(mode='json'))


def bundle_identity(*, org: str, project_id: str, content_hash: str) -> str:
    return 'project-evidence-bundle:' + fingerprint([
        org, project_id, SCHEMA_VERSION, content_hash,
    ])


def _member_rows(bundle_id: str, bundle: ProjectEvidenceBundle) -> list[dict[str, Any]]:
    rows = []
    for kind, items in (('source', bundle.sources), ('claim', bundle.claims)):
        rows.extend({
            'bundle_id': bundle_id, 'kind': kind, 'member_id': item.id,
            'position': position, 'content_hash': _hash(item.model_dump(mode='json')),
        } for position, item in enumerate(items))
    if bundle.land_evidence_snapshot is not None:
        item = bundle.land_evidence_snapshot
        rows.append({
            'bundle_id': bundle_id, 'kind': 'land_evidence_snapshot',
            'member_id': item.snapshot_id, 'position': 0,
            'content_hash': _hash(item.model_dump(mode='json')),
        })
    return rows


def _record(row: dict[str, Any]) -> ProjectEvidenceBundleRecord:
    safe = {key: value for key, value in row.items() if key != 'manifest_key'}
    return ProjectEvidenceBundleRecord.model_validate(safe)


def _get_row(bundle_id: str, *, org: str,
             project_id: str | None = None) -> dict[str, Any] | None:
    query = select(core.project_evidence_bundles).where(
        core.project_evidence_bundles.c.id == bundle_id,
        core.project_evidence_bundles.c.org == org,
    )
    if project_id is not None:
        query = query.where(core.project_evidence_bundles.c.project_id == project_id)
    with core.engine.connect() as connection:
        row = connection.execute(query).mappings().first()
    return dict(row) if row else None


def _find_content_row(*, org: str, project_id: str,
                      content_hash: str) -> dict[str, Any] | None:
    with core.engine.connect() as connection:
        row = connection.execute(select(core.project_evidence_bundles).where(
            core.project_evidence_bundles.c.org == org,
            core.project_evidence_bundles.c.project_id == project_id,
            core.project_evidence_bundles.c.schema_version == SCHEMA_VERSION,
            core.project_evidence_bundles.c.content_hash == content_hash,
        )).mappings().first()
    return dict(row) if row else None


def _historical_claim_hashes(project_id: str, org: str,
                             claim_ids: set[str]) -> dict[str, str]:
    return {
        claim_id: row['claim_hash']
        for claim_id, row in _historical_claim_records(
            project_id, org, claim_ids,
        ).items()
    }


def _historical_claim_records(project_id: str, org: str,
                              claim_ids: set[str]) -> dict[str, dict[str, Any]]:
    if not claim_ids:
        return {}
    with core.engine.connect() as connection:
        rows = connection.execute(select(core.project_evidence_claims).where(
            core.project_evidence_claims.c.project_id == project_id,
            core.project_evidence_claims.c.org == org,
            core.project_evidence_claims.c.claim_id.in_(claim_ids),
        )).mappings()
        return {row['claim_id']: dict(row) for row in rows}


def _historical_source_hashes(
    project_id: str, org: str, source_keys: set[tuple[str, str]],
) -> dict[tuple[str, str], str]:
    if not source_keys:
        return {}
    with core.engine.connect() as connection:
        rows = connection.execute(select(core.project_evidence_sources).where(
            core.project_evidence_sources.c.project_id == project_id,
            core.project_evidence_sources.c.org == org,
        )).mappings()
        return {
            (row['source_id'], row['source_version']): row['source_hash']
            for row in rows
            if (row['source_id'], row['source_version']) in source_keys
        }


def _validate_historical_references(bundle: ProjectEvidenceBundle, *, org: str) -> None:
    claim_by_id = {claim.id: claim for claim in bundle.claims}
    for claim in bundle.claims:
        if (claim.supersedes_claim_id in claim_by_id
                and claim_by_id[claim.supersedes_claim_id].predicate != claim.predicate):
            raise ProjectEvidenceValidationError(
                'A correction must supersede a claim with the same predicate'
            )
    current_ids = {claim.id for claim in bundle.claims}
    external = {
        claim.supersedes_claim_id for claim in bundle.claims
        if claim.supersedes_claim_id is not None
        and claim.supersedes_claim_id not in current_ids
    }
    historical = _historical_claim_records(bundle.project.id, org, external)
    if set(historical) != external:
        raise ProjectEvidenceValidationError(
            'Superseded claim does not resolve in this project and organisation'
        )
    for claim in bundle.claims:
        target_id = claim.supersedes_claim_id
        if target_id not in historical:
            continue
        target = historical[target_id]
        target_bundle_row = _get_row(
            target['first_bundle_id'], org=org, project_id=bundle.project.id,
        )
        if target_bundle_row is None:
            raise ProjectEvidenceConflict(
                'Superseded claim does not resolve through committed history'
            )
        target_bundle = _load_and_verify(target_bundle_row).evidence
        target_claim = next(
            (item for item in target_bundle.claims if item.id == target_id), None,
        )
        if target_claim is None or _hash(
            target_claim.model_dump(mode='json')
        ) != target['claim_hash']:
            raise ProjectEvidenceConflict(
                'Superseded claim does not match its committed history'
            )
        if target_claim.predicate != claim.predicate:
            raise ProjectEvidenceValidationError(
                'A correction must supersede a claim with the same predicate'
            )


def _verify_catalogue(row: dict[str, Any], bundle: ProjectEvidenceBundle) -> None:
    expected = _member_rows(row['id'], bundle)
    with core.engine.connect() as connection:
        actual = [dict(item) for item in connection.execute(select(
            core.project_evidence_bundle_members,
        ).where(
            core.project_evidence_bundle_members.c.bundle_id == row['id'],
        )).mappings()]
    sort_key = lambda item: (item['kind'], item['position'], item['member_id'])
    if sorted(actual, key=sort_key) != sorted(expected, key=sort_key):
        raise ProjectEvidenceConflict('Committed Project Evidence membership mismatch')
    claim_hashes = {
        claim.id: _hash(claim.model_dump(mode='json')) for claim in bundle.claims
    }
    claim_records = _historical_claim_records(
        bundle.project.id, row['org'], set(claim_hashes),
    )
    if (set(claim_records) != set(claim_hashes)
            or any(claim_records[claim.id]['claim_hash'] != claim_hashes[claim.id]
                   or claim_records[claim.id]['predicate'] != claim.predicate
                   for claim in bundle.claims)):
        raise ProjectEvidenceConflict('Committed Project Evidence claim catalogue mismatch')
    source_hashes = {
        (source.id, source.source_version): _hash(source.model_dump(mode='json'))
        for source in bundle.sources
    }
    if _historical_source_hashes(
        bundle.project.id, row['org'], set(source_hashes),
    ) != source_hashes:
        raise ProjectEvidenceConflict('Committed Project Evidence source catalogue mismatch')


def _load_and_verify(row: dict[str, Any]) -> ProjectEvidenceBundleRead:
    content = core.load_object(row['manifest_key'])
    if content is None:
        raise ProjectEvidenceConflict('Committed Project Evidence manifest is missing')
    if sha256(content).hexdigest() != row['manifest_sha256']:
        raise ProjectEvidenceConflict('Committed Project Evidence manifest checksum mismatch')
    try:
        bundle = ProjectEvidenceBundle.model_validate(json.loads(content))
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        raise ProjectEvidenceConflict('Committed Project Evidence manifest is invalid') from error
    calculated_hash = bundle_content_hash(bundle)
    expected_id = bundle_identity(
        org=row['org'], project_id=row['project_id'], content_hash=calculated_hash,
    )
    if (row['id'] != expected_id or row['project_id'] != bundle.project.id
            or row['org'] != bundle.project.org
            or row['schema_version'] != bundle.schema_version
            or row['content_hash'] != calculated_hash
            or row['source_count'] != len(bundle.sources)
            or row['claim_count'] != len(bundle.claims)
            or row['land_evidence_snapshot_id'] != (
                bundle.land_evidence_snapshot.snapshot_id
                if bundle.land_evidence_snapshot else None
            )):
        raise ProjectEvidenceConflict('Committed Project Evidence identity mismatch')
    _verify_catalogue(row, bundle)
    _validate_historical_references(bundle, org=row['org'])
    record = _record(row)
    return ProjectEvidenceBundleRead(**record.model_dump(), evidence=bundle)


def persist_project_evidence(
    project_id: str, value: ProjectEvidenceSubmission | dict[str, Any], *, org: str,
) -> ProjectEvidenceBundleRead:
    """Validate and publish one immutable source-assertion bundle idempotently."""
    project = get_project(project_id, org=org)
    bundle = build_bundle(value, project=project, org=org)
    _validate_historical_references(bundle, org=org)
    content_hash = bundle_content_hash(bundle)
    bundle_id = bundle_identity(org=org, project_id=project_id, content_hash=content_hash)

    existing = _get_row(bundle_id, org=org, project_id=project_id)
    if existing is not None:
        return _load_and_verify(existing)

    claim_hashes = {
        claim.id: _hash(claim.model_dump(mode='json')) for claim in bundle.claims
    }
    historical = _historical_claim_hashes(project_id, org, set(claim_hashes))
    if any(historical[claim_id] != claim_hashes[claim_id] for claim_id in historical):
        raise ProjectEvidenceConflict(
            'A stable claim ID is already committed with different content'
        )
    source_hashes = {
        (source.id, source.source_version): _hash(source.model_dump(mode='json'))
        for source in bundle.sources
    }
    historical_sources = _historical_source_hashes(
        project_id, org, set(source_hashes),
    )
    if any(historical_sources[key] != source_hashes[key]
           for key in historical_sources):
        raise ProjectEvidenceConflict(
            'A stable source version is already committed with different content'
        )

    manifest = _canonical_bytes(bundle.model_dump(mode='json'))
    manifest_sha256 = sha256(manifest).hexdigest()
    manifest_key = (
        f'project-evidence/{fingerprint(org)}/{fingerprint(project_id)}/'
        f'{content_hash}/{manifest_sha256}.json'
    )
    core.store_object_immutable(manifest_key, manifest)
    verified = core.load_object(manifest_key)
    if verified != manifest or sha256(verified).hexdigest() != manifest_sha256:
        raise ProjectEvidenceConflict('Project Evidence manifest did not verify after write')

    created = core.now()
    row = {
        'id': bundle_id, 'org': org, 'project_id': project_id,
        'schema_version': SCHEMA_VERSION, 'content_hash': content_hash,
        'manifest_sha256': manifest_sha256, 'manifest_key': manifest_key,
        'source_count': len(bundle.sources), 'claim_count': len(bundle.claims),
        'land_evidence_snapshot_id': (
            bundle.land_evidence_snapshot.snapshot_id
            if bundle.land_evidence_snapshot else None
        ),
        'created': created,
    }
    try:
        with core.engine.begin() as connection:
            connection.execute(insert(core.project_evidence_bundles).values(**row))
            members = _member_rows(bundle_id, bundle)
            if members:
                connection.execute(insert(core.project_evidence_bundle_members), members)
            for claim in bundle.claims:
                if claim.id not in historical:
                    connection.execute(insert(core.project_evidence_claims).values(
                        project_id=project_id, claim_id=claim.id, org=org,
                        predicate=claim.predicate,
                        claim_hash=claim_hashes[claim.id], first_bundle_id=bundle_id,
                        created=created,
                    ))
            for source in bundle.sources:
                source_key = (source.id, source.source_version)
                if source_key not in historical_sources:
                    connection.execute(insert(core.project_evidence_sources).values(
                        project_id=project_id, source_id=source.id,
                        source_version=source.source_version, org=org,
                        source_hash=source_hashes[source_key],
                        first_bundle_id=bundle_id, created=created,
                    ))
    except IntegrityError:
        existing = _find_content_row(
            org=org, project_id=project_id, content_hash=content_hash,
        )
        if existing is None:
            raise
        return _load_and_verify(existing)
    return _load_and_verify(row)


def get_project_evidence(project_id: str, bundle_id: str, *,
                         org: str) -> ProjectEvidenceBundleRead:
    get_project(project_id, org=org)
    row = _get_row(bundle_id, org=org, project_id=project_id)
    if row is None:
        raise ProjectEvidenceNotFound('Project Evidence bundle not found')
    return _load_and_verify(row)


def list_project_evidence(project_id: str, *,
                          org: str) -> list[ProjectEvidenceBundleRecord]:
    get_project(project_id, org=org)
    with core.engine.connect() as connection:
        rows = [dict(row) for row in connection.execute(select(
            core.project_evidence_bundles,
        ).where(
            core.project_evidence_bundles.c.org == org,
            core.project_evidence_bundles.c.project_id == project_id,
        ).order_by(
            core.project_evidence_bundles.c.created.desc(),
            core.project_evidence_bundles.c.id,
        )).mappings()]
    # Listing is read-only but still fails closed on corrupt immutable history.
    return [ProjectEvidenceBundleRecord.model_validate(
        _load_and_verify(row).model_dump(exclude={'evidence'})
    ) for row in rows]
