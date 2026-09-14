"""Explicit, snapshot-bound public contract for Site reasoning.

This module exposes already-committed Evidence Snapshots as immutable reasoning
inputs.  It performs no acquisition and never mutates a Site, snapshot or legacy
assessment.  A client must echo the complete published run envelope so stale or
contradictory inputs fail closed before execution.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from backend import core
from backend.earth import fingerprint
from backend.land_evidence_store import (
    LandEvidenceSnapshotRecord,
    get_land_evidence_snapshot,
    list_land_evidence_snapshots,
    load_land_evidence_snapshot,
)
from backend.module_runs import (
    MODULE_ID,
    ModuleRunConflict,
    ModuleRunRecord,
    get_module_run,
    run_wetland_from_snapshot,
)
from backend.wetland import LIMITATIONS, MODEL_VERSION, model_spec
from backend.wetland_binding import BINDING_VERSION


CATALOGUE_VERSION = 'site_reasoning_input_catalogue_v1'
RUN_REQUEST_VERSION = 'site_reasoning_run_request_v1'


class SiteReasoningError(RuntimeError):
    """Base class for client-visible Site reasoning contract failures."""


class SiteReasoningNotFound(SiteReasoningError):
    """The requested Site or snapshot is not visible in the organisation."""


class SiteReasoningConflict(SiteReasoningError):
    """The submitted immutable run envelope no longer matches its source."""


class SiteReasoningRunRequest(BaseModel):
    """Complete immutable envelope required to execute one supported module."""

    model_config = ConfigDict(extra='forbid')

    contract_version: Literal['site_reasoning_run_request_v1'] = RUN_REQUEST_VERSION
    site_id: str = Field(min_length=1)
    evidence_snapshot_id: str = Field(min_length=1)
    evidence_content_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    boundary_version: int = Field(ge=1)
    boundary_geometry_fingerprint: str = Field(min_length=1)
    module_id: Literal['wetland_restoration'] = MODULE_ID
    module_version: Literal['wetland_restoration_v0_1'] = MODEL_VERSION
    input_binding_version: Literal['wetland_input_binding_v1'] = BINDING_VERSION
    model_signature: str = Field(min_length=1)
    model_spec: dict[str, Any]


class SiteReasoningSource(BaseModel):
    """Client-safe source identity without private raw-artifact locations."""

    model_config = ConfigDict(extra='forbid')

    id: str
    provider: str
    dataset: str
    source_version: str
    source_url: str
    reference_period_status: str
    reference_period_value: datetime | None
    reference_period_qualification: str | None
    retrieved_at: datetime
    licence_or_attribution: str | None
    licence_metadata_status: str


class SiteReasoningSnapshotInput(BaseModel):
    model_config = ConfigDict(extra='forbid')

    snapshot_id: str
    content_hash: str
    schema_version: str
    registry_version: str
    site_id: str
    boundary_version: int
    boundary_geometry_fingerprint: str
    current_boundary: bool
    created: datetime
    evidence_as_of: datetime
    source_count: int
    observation_count: int
    evidence_gap_count: int
    sources: list[SiteReasoningSource]
    run_request: SiteReasoningRunRequest


class SiteReasoningModuleDescriptor(BaseModel):
    model_config = ConfigDict(extra='forbid')

    module_id: str
    module_version: str
    input_binding_version: str
    model_signature: str
    model_spec: dict[str, Any]
    limitations: str
    input_semantics: str


class SiteReasoningInputCatalogue(BaseModel):
    model_config = ConfigDict(extra='forbid')

    contract_version: Literal['site_reasoning_input_catalogue_v1'] = CATALOGUE_VERSION
    site_id: str
    current_boundary_version: int
    current_boundary_geometry_fingerprint: str
    modules: list[SiteReasoningModuleDescriptor]
    snapshots: list[SiteReasoningSnapshotInput]


class SiteReasoningRunSummary(BaseModel):
    """Client-safe, integrity-checked projection of one retained wetland run."""

    model_config = ConfigDict(extra='forbid')

    id: str
    content_hash: str
    site_id: str
    boundary_version: int
    evidence_snapshot_id: str
    evidence_content_hash: str
    evidence_as_of: datetime
    current_boundary: bool
    module_id: str
    module_version: str
    input_binding_version: str
    model_signature: str
    result_band: str
    result_score: float | None
    data_coverage_available: int | None
    data_coverage_required: int | None
    missing_input_count: int
    review_flag_count: int
    synthetic: bool
    created: datetime
    completed: datetime


class SiteReasoningRunCatalogue(BaseModel):
    model_config = ConfigDict(extra='forbid')

    contract_version: Literal['site_reasoning_run_catalogue_v1'] = (
        'site_reasoning_run_catalogue_v1'
    )
    site_id: str
    current_boundary_version: int
    current_boundary_geometry_fingerprint: str
    runs: list[SiteReasoningRunSummary]


def _site(site_id: str, org: str) -> dict[str, Any]:
    with core.engine.connect() as connection:
        row = connection.execute(select(core.sites).where(
            core.sites.c.id == site_id,
            core.sites.c.org == org,
        )).mappings().first()
    if row is None:
        raise SiteReasoningNotFound('Site not found')
    return dict(row)


def _published_spec() -> dict[str, Any]:
    # A snapshot-bound run performs no acquisition.  Pinning this explicitly
    # prevents deployment configuration from changing the published signature.
    return model_spec(environment_version=None, refresh_sources=False)


def _run_request(
    snapshot: LandEvidenceSnapshotRecord, spec: dict[str, Any],
) -> SiteReasoningRunRequest:
    return SiteReasoningRunRequest(
        site_id=snapshot.site_id,
        evidence_snapshot_id=snapshot.id,
        evidence_content_hash=snapshot.content_hash,
        boundary_version=snapshot.boundary_version,
        boundary_geometry_fingerprint=snapshot.boundary_geometry_fingerprint,
        model_signature=spec['signature'],
        model_spec=spec,
    )


def list_site_reasoning_inputs(
    site_id: str, *, org: str,
) -> SiteReasoningInputCatalogue:
    """Return verified immutable inputs and exact runnable request envelopes."""
    site = _site(site_id, org)
    current_fingerprint = fingerprint(site['geometry'])
    spec = _published_spec()
    snapshots: list[SiteReasoningSnapshotInput] = []
    for snapshot in list_land_evidence_snapshots(org=org, site_id=site_id):
        projection = load_land_evidence_snapshot(snapshot.id, org=org)
        sources = [SiteReasoningSource(
            id=source.id,
            provider=source.provider,
            dataset=source.dataset,
            source_version=source.source_version,
            source_url=source.source_url,
            reference_period_status=source.reference_period.status,
            reference_period_value=source.reference_period.value,
            reference_period_qualification=source.reference_period.qualification,
            retrieved_at=source.retrieved_at,
            licence_or_attribution=source.licence_or_attribution,
            licence_metadata_status=source.licence_metadata_status,
        ) for source in projection.source_references]
        snapshots.append(SiteReasoningSnapshotInput(
            snapshot_id=snapshot.id,
            content_hash=snapshot.content_hash,
            schema_version=snapshot.schema_version,
            registry_version=snapshot.registry_version,
            site_id=snapshot.site_id,
            boundary_version=snapshot.boundary_version,
            boundary_geometry_fingerprint=snapshot.boundary_geometry_fingerprint,
            current_boundary=(
                snapshot.boundary_version == site['version']
                and snapshot.boundary_geometry_fingerprint == current_fingerprint
            ),
            created=snapshot.created,
            evidence_as_of=projection.identity.evidence_as_of,
            source_count=len(sources),
            observation_count=len(projection.observations),
            evidence_gap_count=len(projection.gaps),
            sources=sources,
            run_request=_run_request(snapshot, spec),
        ))
    return SiteReasoningInputCatalogue(
        site_id=site_id,
        current_boundary_version=site['version'],
        current_boundary_geometry_fingerprint=current_fingerprint,
        modules=[SiteReasoningModuleDescriptor(
            module_id=MODULE_ID,
            module_version=MODEL_VERSION,
            input_binding_version=BINDING_VERSION,
            model_signature=spec['signature'],
            model_spec=spec,
            limitations=LIMITATIONS,
            input_semantics=(
                'Only evidence explicitly mapped by wetland_input_binding_v1 affects '
                'wetland_restoration_v0_1. Newer built-world and height evidence is '
                'retained but does not silently broaden this model input contract.'
            ),
        )],
        snapshots=snapshots,
    )


def list_site_reasoning_runs(
    site_id: str, *, org: str,
) -> SiteReasoningRunCatalogue:
    """Return verified wetland ModuleRuns for one Site without creating state."""
    site = _site(site_id, org)
    current_fingerprint = fingerprint(site['geometry'])
    with core.engine.connect() as connection:
        run_ids = connection.execute(select(core.module_runs.c.id).where(
            core.module_runs.c.org == org,
            core.module_runs.c.site_id == site_id,
            core.module_runs.c.module_id == MODULE_ID,
        ).order_by(
            core.module_runs.c.completed.desc(),
            core.module_runs.c.id,
        )).scalars().all()

    summaries: list[SiteReasoningRunSummary] = []
    for run_id in run_ids:
        run = get_module_run(run_id, org=org)
        snapshot = get_land_evidence_snapshot(run.evidence_snapshot_id, org=org)
        projection = load_land_evidence_snapshot(snapshot.id, org=org)
        if (
            snapshot.site_id != site_id
            or snapshot.content_hash != run.evidence_content_hash
            or snapshot.boundary_version != run.boundary_version
        ):
            raise ModuleRunConflict(
                'Stored ModuleRun and Evidence Snapshot identity mismatch'
            )
        overall = run.result.get('overall')
        evidence_summary = run.result.get('evidence_summary')
        coverage = (
            evidence_summary.get('data_coverage')
            if isinstance(evidence_summary, dict) else None
        )
        if not isinstance(overall, dict) or not isinstance(coverage, dict):
            raise ModuleRunConflict('Stored wetland ModuleRun summary is invalid')
        missing_inputs = run.result.get('missing_inputs')
        review_flags = run.result.get('review_flags')
        result_band = overall.get('band')
        result_score = overall.get('score')
        coverage_available = coverage.get('available')
        coverage_required = coverage.get('required')
        synthetic = run.result.get('synthetic')
        if (
            not isinstance(result_band, str)
            or (
                result_score is not None
                and (
                    isinstance(result_score, bool)
                    or not isinstance(result_score, (int, float))
                )
            )
            or (
                coverage_available is not None
                and (
                    isinstance(coverage_available, bool)
                    or not isinstance(coverage_available, int)
                )
            )
            or (
                coverage_required is not None
                and (
                    isinstance(coverage_required, bool)
                    or not isinstance(coverage_required, int)
                )
            )
            or not isinstance(missing_inputs, list)
            or not isinstance(review_flags, list)
            or not isinstance(synthetic, bool)
        ):
            raise ModuleRunConflict('Stored wetland ModuleRun summary is invalid')
        summaries.append(SiteReasoningRunSummary(
            id=run.id,
            content_hash=run.content_hash,
            site_id=run.site_id,
            boundary_version=run.boundary_version,
            evidence_snapshot_id=run.evidence_snapshot_id,
            evidence_content_hash=run.evidence_content_hash,
            evidence_as_of=projection.identity.evidence_as_of,
            current_boundary=(
                snapshot.boundary_version == site['version']
                and snapshot.boundary_geometry_fingerprint == current_fingerprint
            ),
            module_id=run.module_id,
            module_version=run.module_version,
            input_binding_version=run.input_binding_version,
            model_signature=run.model_signature,
            result_band=result_band,
            result_score=result_score,
            data_coverage_available=coverage_available,
            data_coverage_required=coverage_required,
            missing_input_count=len(missing_inputs),
            review_flag_count=len(review_flags),
            synthetic=synthetic,
            created=run.created,
            completed=run.completed,
        ))
    return SiteReasoningRunCatalogue(
        site_id=site_id,
        current_boundary_version=site['version'],
        current_boundary_geometry_fingerprint=current_fingerprint,
        runs=summaries,
    )


def run_site_reasoning(
    site_id: str, request: SiteReasoningRunRequest, *, org: str,
) -> ModuleRunRecord:
    """Validate an exact published envelope, then create or reuse its ModuleRun."""
    _site(site_id, org)
    if request.site_id != site_id:
        raise SiteReasoningConflict('Run request Site does not match the route')
    snapshot = get_land_evidence_snapshot(request.evidence_snapshot_id, org=org)
    if snapshot.site_id != site_id:
        # Avoid confirming that another same-organisation Site owns the supplied ID.
        raise SiteReasoningNotFound('Evidence Snapshot not found for Site')
    expected = _run_request(snapshot, _published_spec())
    if request.model_dump(mode='json') != expected.model_dump(mode='json'):
        raise SiteReasoningConflict(
            'Run request does not match the published immutable snapshot and model envelope'
        )
    return run_wetland_from_snapshot(
        snapshot.id,
        org=org,
        binding_version=request.input_binding_version,
        spec=request.model_spec,
    )
