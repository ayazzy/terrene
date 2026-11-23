# Sprint 005 Task 4 — Oxford Station operating scene

## Outcome

Oxford Station is now a reproducible analyst workflow rather than an implicit local demo. One command provisions a fresh database outside the repository from the retained Oxford assessment, reacquires the official Environment Agency DSM/DTM pair, verifies the exact object inventory and exposes the result through the existing application. The operating picture moves explicitly from Portfolio to Site diligence to Asset intelligence, with the selected immutable object and related-parcel view preserved in the URL.

This iteration improves Terrene's ability to represent and inspect reality.

## Source

The provisioner reads `data/verification/england-real-openmap-local-2026-04/oxford-station-after.json`. It does not copy that retained record into a new tracked fixture. It performs a new paired acquisition from the official Environment Agency WCS and writes the DescribeCoverage responses, exact DSM/DTM bytes, acquisition manifest, content-addressed evidence and SQLite database only beneath the caller-supplied external QA directory.

The command refuses a directory inside the repository, refuses a non-empty destination and requires an explicit `--live-ea-wcs` acknowledgement:

```sh
.venv/bin/python scripts/provision_oxford_operating_scene.py \
  --data-dir /tmp/terrene-oxford-operating-scene \
  --live-ea-wcs
```

## Evidence semantics

- The five building extrusions remain historical EA composite `DSM − DTM` estimates, not current, legal or engineering building heights.
- The two functional sites, seven railway tracks and one station retain only their OS OpenMap – Local `2026-04` classifications. No route, service or network identity is inferred.
- “Show related objects” highlights the retained parcel endpoint of exact typed relationships. It does not draw or imply object-to-object connections.
- The retained evidence payload keeps its historical location and boundary-support identity. The isolated database and assessment are newly provisioned without modifying the source record.
- Acquisition failure remains a five-object evidence gap in the external directory; the provisioner refuses to present an incomplete scene as the verified exemplar.

## Implementation / architecture

- `scripts/provision_oxford_operating_scene.py` creates the isolated Site and assessment, acquires object-level heights, prepares the registry-v4 Evidence Snapshot and Screening Context run, then validates the projected scene before returning its identities and launch URL.
- Operating-picture state now includes an exact `asset` identifier and optional `related=1` state. Both are normalized against the authorized selected scene and restored through reload and browser history.
- The map exposes Portfolio, Site diligence and Asset intelligence as one compact spatial path. Selecting an object opens the existing evidence inspector without losing Site, assessment, section or layer state.
- The inspector can reveal the exact parcel relationship through MapLibre feature state. No fictional edge layer exists.
- Changing Site, assessment or unavailable scene clears incompatible asset state. Stale scene responses remain fenced by the existing workspace lifecycle.

## Real-data verification

On 14 September 2026 a fresh external replay produced `land_evidence_registry_v4` snapshot `land-evidence-snapshot:ca72c13cc5b07b9a6eb35ef9b84ed9c73ba9a3516d2b6a9e18c97c1d73f7fe42` with:

- 5 height-backed buildings
- 2 functional sites
- 7 railway tracks
- 1 railway station
- 23 retained parcel relationships

The acquired artifact hashes were `9f970493…958`, `f6bd81ab…b72`, `ba03668c…bca` and `c7101a59…560`. The five full-precision P90 extrusion estimates were 8.311004638671875 m, 9.844306564331054 m, 2.9220027923583984 m, 8.572006225585938 m and 15.893474578857422 m.

## Verification

- Focused Oxford provisioner and map-scene backend tests: 6 passed.
- Frontend Node regression suite: 78 passed.
- TypeScript: passed with `npx tsc --noEmit`.
- Python compilation: passed for the provisioner and its test.
- Production build: passed with the existing large-chunk advisory.
- Focused lint passes on the changed map, state, workspace, inspector and test modules. Repository-wide lint retains the known generated-component and `app/page.tsx` baseline; no new Task 4 diagnostic remains.
- Live browser QA verified exact object selection, height/source/relationship inspection, URL-backed related-parcel state and a non-colliding Portfolio → Site diligence → Asset intelligence path at the available desktop viewport.

## Historical / compatibility impact

Historical assessments, v1–v3 snapshots, wetland ModuleRuns, `screening_context_map_features_v1` and `infrastructure_map_scene_v1` remain unchanged. The QA database and official raw raster responses are external runtime artifacts and are not tracked.

## Known limitations

The public development basemap remains non-SLA. Full responsive certification, failed-basemap and missing/partial DSM hardening, durable architecture decisions and the final staging audit remain Sprint 005 Task 5.
