# Site Analysis Workspace v2

Implemented 11 September 2026.

## Outcome

The existing Site Analysis Workspace now presents the buildings, functional sites, railway tracks and railway stations persisted in the selected Screening Context run. A reviewer can move from map object to parcel relationship and measurement to source/release and limitation without turning the workspace into a general GIS viewer.

## Implementation

- The shared workspace controller reads `GET /api/screening-context-runs/{run_id}/map-features`, checks the response envelope against the selected immutable run and rejects stale or contradictory responses.
- Site boundary, environmental evidence and four Terrene Earth layers share the existing map controls. Built-world geometry uses restrained source-specific styling distinct from the raster basemap.
- Layer controls preserve `available`, `mapped_zero`, `unavailable`, `partial` and `unsupported` semantics. Partial or missing coverage is never displayed as zero; unsupported runs never receive current objects.
- Selecting a map object or its Overview/Evidence entry populates one shared inspector. It leads with useful type/name, parcel relationship and measurement, source/release and a plain limitation. Raw IDs, geometry fingerprints, exact predicates and detailed provenance are disclosed only under Advanced provenance.
- Selection alone preserves parcel focus. Locate object is an explicit action. Site, assessment or run changes, and hiding the selected layer, clear the selection.

## Evidence semantics

WGS84 geometry is presentation-only. Persisted EPSG:27700 geometry, fingerprints, source identities and measurements remain authoritative and unchanged. OS OpenMap - Local is generalized contextual mapping, not surveyed, cadastral, legal or engineering geometry. No evidence snapshots, ModuleRuns, historical assessments, Screening Context rules or wetland reasoning were mutated.

## Verification

- Frontend regression: 32 passed.
- TypeScript: passed.
- Focused lint: passed for new/refined map, state, inspector, panel and contract modules. The unchanged page-level baseline retains its documented diagnostics.
- Production build: passed with the existing large-chunk advisory.
- Browser QA: 1280px desktop, 1024px compact and 390px phone; no page-level horizontal overflow and no browser warnings/errors.

## Retained real-data acceptance

- Westgate: 13 mapped buildings visible; object relationship/source inspection clear; 43.3473% building-union evidence retained with OS OpenMap - Local 2026-04 qualification.
- Oxford station: 5 buildings, 2 functional sites, 7 railway tracks and 1 station visible; 279.31 m mapped in-parcel rail length retained.
- Port Meadow: no building geometry fabricated; buildings and functional sites display qualified mapped zero; supported track/station evidence remains inspectable and explicitly generalized.
- Redbridge: building and functional-site mapped zero retained; railway layers display partial coverage with no complete-zero claim and no minimum-distance value.
- Historical switch: a current Westgate building selection cleared immediately; the pre-built historical run displayed all four built-world layers as unsupported and did not substitute current geometry.

The browser pass used a disposable SQLite database populated from the retained `england-real-openmap-local-2026-04` records. The disposable database and object store were removed after QA. The backend and PostgreSQL suites were not rerun because this iteration did not change the already-verified v2B contract or persistence.
