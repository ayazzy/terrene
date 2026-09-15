# Terrene

Terrene is building a computational model of land and human interventions. The current England-first application implements evidence-backed land representation, deterministic wetland reasoning and an evidence-aware site-screening workflow. Real missing inputs remain unknown; no BNG units are inferred.

Start with the [North Star](docs/TERRENE-NORTH-STAR.md), [Current State](docs/CURRENT-STATE.md), [Architecture](docs/ARCHITECTURE.md), [Decision Log](docs/DECISIONS.md) and [Customer Discovery](docs/CUSTOMER-DISCOVERY.md). Repository implementation is authoritative where documentation has drifted; detailed historical implementation reports remain the record of their versions.

For bounded, allowance-aware Codex work, use the [Codex working agreement](docs/CODEX-WORKING-AGREEMENT.md) and its copyable task card.

See [Nature Intelligence](docs/NATURE-INTELLIGENCE.md) for sources, canonical variables, exact calculations and limitations, [OS OpenMap – Local built-world objects](docs/OPENMAP-LOCAL-BUILT-WORLD.md) for the latest Terrene Earth object/relationship iteration, and [12 real parcel results](docs/REAL-VERIFICATION.md) for evidence. EA 1m DTM terrain, OS Open Rivers and ESA WorldCover are connected. Required-input coverage rose from 1/10 to 5/10; real physical/hydrological components are inspectable. Overall rankings remain **insufficient data** because soil drainage, actual wetland extent/condition and complete constraints are still missing. No thresholds were weakened to force a result.

The project was formerly developed under the working name CRC / Climate Restoration Company. Existing `CRC_*` configuration variables, `crc_*` model and processing identifiers, database names, signatures, hashes and historical reports are intentionally retained where changing them could damage compatibility or reproducibility. New project and product language uses Terrene.

## Run locally

Requires Node 22.13+ and Python 3.14. Docker is recommended for PostGIS; a development-only SQLite/Shapely fallback works without it.

```bash
npm ci
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cp .env.example .env
```

Preferred PostGIS route:

```bash
docker compose up -d db
# Enable this in .env:
# DATABASE_URL=postgresql+psycopg://crc:crc_local_only@127.0.0.1:54329/crc
set -a; source .env; set +a
.venv/bin/python -m backend.migrate
.venv/bin/python -m backend.import_data
./scripts/dev.sh
```

Open **http://localhost:3000/**. The API is on loopback port 8000. The starter's frontend port is 3000. `scripts/dev.sh` starts the API, worker and frontend together; Ctrl+C stops them. The example Postgres password is only for the loopback-bound development container. AMD64 emulation is specified for the PostGIS image on Apple Silicon.

Without Docker, leave `DATABASE_URL` unset: migrations/imports use `data/crc.db` and `data/objects/`. The API still performs actual projected spatial analysis on the server, using a bounding-box database index plus Shapely; it is not a browser-only demonstration. Hosted mode refuses SQLite or absent Supabase/R2 configuration.

The current checked-out environment already has two persisted verification sites and imported data, and is configured to use local PostGIS. The original SQLite database remains as a backup. Never run the copying utility against a non-empty target; it explicitly refuses.

## Main workflow

Sites now opens as a dark geographic portfolio overview, framed around the saved boundaries. Select a site to open its analysis, or switch to **List** for the existing search, filtering, review and comparison tools. **New site** opens the existing drawing/upload workflow from either view. See [map-first home implementation and QA](docs/UI-STAGE-3-MAP-HOME.md).

1. New site → enter name/notes → draw and finish a boundary, or upload a single GeoJSON Polygon/MultiPolygon.
2. Save → Run screening. The persisted job progresses queued → running → completed or partial. The page polls active jobs. This job status describes source-layer coverage; wetland-model data sufficiency is reported separately.
3. Open a site into the map workspace. Overview separates physical potential, restoration need, feasibility, evidence completeness and unvalidated model confidence. Physical, Ecology and Constraints expose reasons; Evidence contains missing inputs, observations, source lineage and JSON export. History switches both analysis and the saved boundary. The Layers control independently toggles saved intersections; evidence links highlight their exact footprint. See [Stage 2 UI implementation and verification](docs/UI-STAGE-2.md).
4. Save Unreviewed, Investigate, Hold or Archived as a **team decision**. This never changes calculated findings.
5. Select two or three sites in the workspace → Compare selected.
6. Export report opens a preview of a self-contained HTML report. Use Download HTML or Print / Save as PDF. Every finding includes evidence and limitations. Historical reports are explicitly marked.
7. Edit site → upload/draw a replacement boundary. Previous results are labelled historical; rerun to assess the new version. Notes-only edits keep the boundary version unchanged. History lets you reopen any assessment.

For a first real reference workflow, upload `docs/port-meadow-reference.geojson`, name it “Port Meadow — public reference site”, and note that this is a public SSSI reference boundary, not a commercial opportunity. Do not treat it as a restoration recommendation. Synthetic fixtures are separate and explicitly named.

## Architecture and stack choices

- React + TypeScript, Vite through the environment-mandated **Vinext Sites scaffold**, Tailwind and the generated shadcn/Base UI components. This is the documented deviation from plain Vite React. There is no additional frontend service.
- MapLibre interactive raster basemap with configurable `NEXT_PUBLIC_BASEMAP_URL`; bounded vector evidence uses exact MapLibre-projected SVG paths, including holes and MultiPolygons. This avoids a browser blob-worker rendering issue observed in verification. It is geographic data rendering, not a static mock map.
- One FastAPI API and one Python worker, sharing `backend/core.py` and SQLAlchemy models. Shapely/pyproj implement the narrow geometry pipeline; GeoPandas was unnecessary for these bounded GeoJSON features.
- Supabase-compatible Postgres/PostGIS: queryable geometry columns, GiST indexes, server-side candidate queries. `python -m backend.migrate` applies nine idempotent additive migrations (including pinned model specifications, immutable evidence snapshots/ModuleRuns, retained source-feature attributes, Design Studies, Project Evidence, Project Intelligence runs and independent geographic acquisitions) and RLS hardening.
- The assessments table also acts as the jobs table. A unique submission fingerprint covers organization, site, boundary version, pinned dataset versions and model-configuration signature. Workers use `FOR UPDATE SKIP LOCKED`, 120-second leases, fencing tokens, maximum three attempts and exponential retry delays. Expired final attempts terminate as failed. SQLite uses conditional atomic updates for local testing.
- `land_evidence_v1` snapshots are an additive, independently identified projection of saved assessments. Their validated manifests live in private content-addressed object storage; relational tables index parcel/boundary membership, observations, gaps/capabilities, source/raw references and lineage. Legacy assessment execution remains preserved, while a parity-verified snapshot path uses `wetland_input_binding_v1` and persists immutable ModuleRuns without changing historical assessment behavior or results. See [snapshot persistence](docs/LAND-EVIDENCE-SNAPSHOT-PERSISTENCE.md) and [snapshot-driven wetland execution](docs/WETLAND-SNAPSHOT-MODULE-RUN.md).
- Registry v3 carries a narrow typed union of OpenMap Local Building, FunctionalSite, RailwayTrack and RailwayStation objects plus deterministic parcel relationships. Registry v4 adds object-linked historical EA DSM/DTM building-height evidence and explicit gaps without mutating those objects. Derived building/site unions and rail length/distance observations preserve object lineage; WorldCover and PHI remain separate. The wetland binding and ModuleRuns do not consume these objects or heights.
- Uploads, versioned source snapshots and report exports live in object storage. Local development uses `data/objects`; hosted mode requires an R2 bucket and S3 credentials. Database records contain structured evidence/geometries, not binary archives.
- Immutable dataset versions are shared once across sites. Only server-selected/clipped reference geography is sent to the UI. Workspace sites/history are currently fetched without pagination, so this v0 is for small portfolios.

## Hosted setup

`render.yaml` defines the API and background worker, using `backend/Dockerfile`. Supply the secret environment variables in `.env.example` through Render, never Git or browser code. Use the `postgresql+psycopg://` URL scheme with a Supabase direct/session connection and TLS as required by the provider. Initialize the database with `backend.migrate`, then run `backend.import_data` once using the hosted database and R2 environment. The two services must use the same database.

The frontend follows Sites hosting conventions and has a reserved private project in `.openai/hosting.json`; it is **not yet published**. A production frontend needs server-side `CRC_API_URL` pointing to the HTTPS Render API. The localhost development API is not reachable from hosted Sites. Configure the external services and validate them before publishing; do not present an API-disconnected frontend as the finished deployment.

Hosted Supabase Auth uses email/password sign-in via Supabase and short-lived access tokens stored in sessionStorage. Tokens are checked against Supabase JWKS using ES256/RS256, issuer, audience, expiration and subject. An administrator must provision a string `app_metadata.org_id`; user-editable `user_metadata` is never trusted. Provision users through Supabase administration; self-signup and organization administration are deferred. Sessions currently require sign-in again on expiry; refresh and sign-out UX are a remaining pilot improvement.

All site, job, assessment, report and boundary-file access is authorized server-side against the signed organization. Public browser database roles have no direct table privileges; tenant tables additionally enable RLS with no browser access policies. Use a dedicated server database owner/service role, never its credentials in the browser. Raw R2 objects must remain private. Downloads are served through authenticated API endpoints, not public object paths. Local auth bypass only works with explicit `CRC_ENV=development`; local scripts bind API and database to loopback. Never set that value on a hosted deployment.

Live Supabase, Render and R2 credentials were not supplied. Their live provisioning, real hosted sign-in, private bucket access and end-to-end external deployment have **not** been verified. Signed JWT and tenant isolation tests do pass against local PostGIS.

## Verification

```bash
.venv/bin/python -m pytest -q
npx tsc --noEmit
npm run build
```

The default Python suite is synthetic/captured-data reproducible from a fresh clone. Ignored retained Oxford verification assets are explicit opt-in:

```bash
.venv/bin/python -m pytest -q --retained-data
```

That command exits with a prerequisite error when either retained-data directory is absent. To create the isolated synthetic Project Intelligence history in a disposable or local development database, run `CRC_ENV=development .venv/bin/python -m scripts.seed_project_intelligence_demo`.

To repeat tests on PostGIS, create a **disposable** database named `crc_test` (the test runner refuses any other Postgres test database name):

```bash
docker compose exec -T db createdb -U crc crc_test
CRC_TEST_DATABASE_URL=postgresql+psycopg://crc:crc_local_only@127.0.0.1:54329/crc_test \
  .venv/bin/python -m pytest -q
```

Tests cover one-hectare projected area and actual overlap, invalid input, missing/out-of-area coverage, duplicate submissions, boundary history, reports, decisions, worker lease/retry/fencing behavior, tenant access including reports, invalid tokens and valid signed tokens from different organizations. Tests only write their isolated test database/object directory.

See `docs/VERIFICATION.md` for the recorded browser journey and results, and `docs/DATA.md` for sources, licensing, counts, coverage and rule limitations.

## Smallest customer pilot

With one ecological consultancy, screen 5–10 consented Oxfordshire-area opportunities and compare the evidence/report against their manual desk research. Record time saved, missing datasets and whether prioritization changed. Before giving external users access: expand and validate flood coverage beyond the Oxford corridor, select the applicable AWI revision coverage, configure hosted auth/storage and complete a two-organization hosted acceptance test. More designations, contextual nearby reference layers, report maps, refresh-token UX and large-portfolio pagination are deferred. OS Open Rivers now provides distance and proximity to its mapped line network; this is not distance to all water and does not establish hydraulic connectivity.


Independent area-based source acquisition is available through the trusted
operator CLI, beginning with Natural England SSSI. See the
[setup, versioned request, coverage limits and live verification](docs/GEOGRAPHIC-EVIDENCE-ACQUISITION.md).
The shared geometry contract accommodates all four UK nations; this does not yet
provide four-nation source coverage or customer-facing map/API access.
