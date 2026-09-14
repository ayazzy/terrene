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
    ModuleRunRecord,
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
