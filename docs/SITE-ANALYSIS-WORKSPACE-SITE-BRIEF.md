# Site Analysis Workspace site brief

Implemented 11 September 2026. This is a frontend/product-UX iteration over the existing saved assessment, Screening Context and map-feature contracts. It creates no new reasoning model, evidence semantics, dataset or backend synthesis record.

## Outcome

The Site Analysis Workspace now opens as a professional site brief rather than an evidence-count dashboard. The first screen establishes the saved site and boundary, then presents a deterministic site picture, high-signal evidence, important known gaps and existing human-review questions before technical drill-down.

The durable product boundaries remain explicit:

- Overview summarizes retained facts and gaps for human diligence.
- Evidence exposes exact observations, definitions, support, source metadata, identifiers, provenance and methods.
- Models contains versioned reasoning modules, including the unchanged wetland assessment.
- History selects the immutable assessment, boundary and artifact context being reproduced.

## Presentation policy

`app/site-brief.ts` is a deterministic display policy, not a scientific model. It assigns presentation priority and concise labels to an allow-list of existing Screening Context definitions. It prefers built/development context, building objects, Priority Habitat Inventory, flood and watercourse context, material transport relationships and designations. Terrain appears only as a fallback after these higher-signal families.

Mapped zero, partial availability and unavailable evidence remain distinct. Important unknowns are selected from existing Evidence Gaps; the Overview does not reinterpret every registered-but-unconnected capability as an equal-priority issue. Review questions are reused from the immutable Screening Context result and remain questions, not recommendations.

Overview values use restrained display precision. Exact values and complete source definitions remain available under Evidence.

## Map interaction

The workspace now reads the existing authenticated `screening_context_map_features_v1` endpoint after a saved Screening Context run is discovered or prepared. The read is keyed to the exact run/site/boundary/snapshot identity and is cancelled when selection changes. It creates no persistence.

Persisted Building, FunctionalSite, RailwayTrack and RailwayStation objects are rendered from their WGS84 presentation geometry while the EPSG:27700 evidence remains authoritative. Overview rows offer a map action only when displayable retained geometry exists; otherwise they route to Evidence. Map clicks continue to use one spatial-evidence inspector, extended to show safe object classification, source, parcel relationship and geometry-CRS information.

## Chrome and Models

Site identity, boundary, area, assessment status/date, team review state and secondary actions now share one compact site band. Wetland export moved into the wetland module under Models. Product-facing workspace branding now uses Terrene while legacy technical `CRC`/`crc` identifiers and retained historical artifacts remain unchanged.

The wetland module remains scientifically and historically unchanged. Its nested tabs now have an explicit column layout and bounded navigation row, preventing the module content from collapsing into narrow vertical columns.

## Empty and unprepared states

A site without an assessment still shows its location, boundary version and assessment state, with one action to establish saved evidence. A saved assessment without Screening Context shows area, boundary and assessment context plus one explicit preparation action and an explanation of the immutable artifact it adds. Ordinary reads never prepare a run automatically.

## Verification

- Frontend Node regression suite: **31 passed** after the final presentation-policy refinement.
- `npx tsc --noEmit`: passed.
- Focused lint passed on the new/refined modules. A direct page lint reports the 19 existing broad-page diagnostics from the known baseline.
- Production build passed with the existing large-chunk advisory.
- Browser QA covered Westgate, Port Meadow, Redbridge and an Oxford station boundary at 1280 px, plus Port Meadow at 1024 px and 390 px. It verified compact chrome, useful unprepared context, site-brief hierarchy, mapped-zero wording, Overview-to-map routing and usable wetland-module navigation.
- Live QA caught and corrected the nested wetland tab direction defect.

The connected local QA database did not contain the retained OpenMap Local/PHI dataset versions, so the Oxford station browser run verified the UI with current locally connected sources but could not exercise its persisted railway-object layer. Deterministic priority tests cover railway placement, and the existing backend map-feature suite remains the authoritative real-data verification for Oxford station object geometry and relationships.

## Historical and compatibility impact

No saved assessment, Evidence Snapshot, ModuleRun, Screening Context rule, wetland binding/calculation, model identifier, evidence definition or historical artifact was rewritten. Browser QA created new immutable Screening Context runs for the selected existing Port Meadow and Redbridge assessments and created a separate local Oxford station QA site/assessment from the retained real boundary; existing records were preserved.

## Known limitations

- The brief is a fixed pilot presentation policy and still requires prospective-reviewer validation.
- A high-signal fact without retained display geometry routes to Evidence rather than creating a synthetic map interaction.
- The workspace remains optimized for a small portfolio and does not add pagination or workflow management.
