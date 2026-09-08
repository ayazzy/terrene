# CRC Nature Intelligence: operational real-data iteration

CRC now calculates real terrain and watercourse features and exposes mapped land cover for English parcels. Twelve Oxford locations were inspected. Required-input availability increased from 1/10 to 5/10 at every location; the model provides inspectable physical/hydrological components. **It cannot yet provide a defensible overall restoration ranking for these sites.** Soil drainage, actual wetland extent/condition and complete infrastructure/irreplaceable-habitat evidence remain unknown. No completeness gate was relaxed and no production values were invented.

See [real-site results](REAL-VERIFICATION.md), [machine-readable results](real-verification-results.json), [soil access gap](SOIL-DATA-GAP.md), and [initial inspection/plan](WETLAND-IMPLEMENTATION-PLAN.md).

## Retained architecture and deterministic execution

The existing FastAPI, lease-based Python worker, PostGIS/SQLite, private object storage, CRC Earth Schema, adapters, feature functions and model UI remain. There is no new model service, ML platform, LLM inference, generalized assistant or additional product domain.

The API pins a model specification and signature at submission. The specification includes `wetland_restoration_v0_1`, feature revision `crc_wetland_features_v0_1_1`, environmental acquisition revision `crc_england_real_inputs_v1`, configuration and refresh policy. Its signature participates in job deduplication. Unsupported old pinned implementations are rejected explicitly; historical saved results/reports are read without recalculation. There were no pending old jobs when the local database was checked.

The worker first computes existing pinned vector overlays, acquires the new real sources, translates them into canonical observations, computes features, and executes the model. An assessment-specific environmental snapshot is retained before feature/model execution. Worker retries reuse that exact source snapshot. Long acquisitions renew their fenced lease every 30 seconds; an obsolete worker cannot overwrite the current job. Acquisition is separate from inference: `run_wetland(saved_state, saved_spec)` uses no network, wall clock or ambient source configuration.

Raw files are content-addressed by SHA-256, retained through the existing local/R2 object-storage adapter, and referenced by observations. Reusable source caches verify their artifacts; they never substitute synthetic data. Report exports show saved evidence. `POST /api/sites/{id}/assessments?refresh_environment=true` requests a distinct assessment and refreshed source acquisition. Normal repeated submissions retain deduplication. `CRC_ENVIRONMENT_ACQUISITION=disabled` is an explicitly pinned offline mode used by isolated regression tests, not a favourable-data fallback.

## Earth Schema and provenance

`backend/earth.py` retains validated observations with canonical units/bounds, source, dataset, checksum/version, source URL, observation timestamp where known, retrieval timestamp, resolution, CRS, spatial support, aggregation, processing method/version, observed/derived and epistemic status, source-quality judgement, missing reason, source IDs and parent input IDs. Unknowns are null, require a reason and zero confidence, and have unknown status. All competing observations remain available; deterministic provider selection is recorded.

Raw native rasters/vectors remain assets, not flattened synthetic measurements. Terrain statistics link directly to the DEM input and metadata; slope is not falsely derived from parcel mean elevation. CRC feature observations retain every contributing observation/raw ID. All real verification states passed lineage resolution and deterministic replay.

A state `as_of` is the submission time, not a claim all inputs were observed then. Retrieval does not substitute for observation time. The ESA timestamp is explicitly the start of its 2021 annual reference period. EA composite survey dates and OS field-observation dates remain unknown.

## Connected real sources

| Source | Canonical outputs / processing | Limits |
|---|---|---|
| [EA LIDAR Composite DTM 1m](https://www.data.gov.uk/dataset/01b3ee39-da3f-47b6-83da-dc98e73a461f/lidar-composite-digital-terrain-model-dtm-1m) through official WCS | Mean/min/max/population SD elevation; mean/p90/max slope | Bare-earth composite, multiple survey years; local observation date unknown. Native 1m spacing; vertical noise, filtering, bridges, water surfaces and small features affect derivatives. |
| [OS Open Rivers](https://osdatahub.os.uk/downloads/open/OpenRivers) official GeoPackage | Parcel-to-line distance, intersection and fraction within 100m | April 2026 downloaded file, immutable checksums retained. Generalized 1:15,000–1:30,000 network; not all drains, no river width, flow permanence or hydraulic connectivity. |
| [ESA WorldCover 2021 v200](https://esa-worldcover.org/en/data-access) official public COG | Dominant mapped cover, mapped built-up fraction, mapped herbaceous-wetland fraction, mapped permanent-water fraction; complete class proportions retained | Dated 2021, nominal 10m satellite classification. Not a current habitat/condition survey. Grassland is not improved/degraded grassland; wet grassland/wet woodland may be omitted from herbaceous wetlands. |
| Existing [EA Flood Zones 2/3](https://www.data.gov.uk/dataset/104434b0-5263-4c90-9b1e-e43b1d57c750/flood-map-for-planning-flood-zones1) | Parcel union overlap `hydrology.mapped_flood_extent_fraction` | Bounded Oxford corridor; not a probability or functional-floodplain/groundwater assessment. |
| Existing Natural England SSSI / ancient woodland inventories | Protected-area review flag and known irreplaceable-habitat overlap | No protected-area score penalty. Incomplete ancient-woodland absence stays unknown; competing inventories never erase positive overlap or get summed. |

Raw EA WCS TIFF/XML and original OS archive/GeoPackage/download metadata are retained. WorldCover is retained as a lossless native-pixel window with original COG URL, reference year and checksum. It is explicitly a subset, not the untouched complete remote COG; there is no resampling or reclassification of original saved pixels. OGL applies to EA/OS; ESA WorldCover uses CC BY 4.0. Publisher terms/attribution accompany the fixture documentation.

The preferred England soil source is now the free registered LandIS Portal, opened in April 2026. Access still requires a registered account and acceptance of the applicable licence. The user confirmed no existing access and requested this gap remain documented. No account was created or terms accepted. See [precise access and interpretation notes](SOIL-DATA-GAP.md); do not describe the source as inherently unavailable or necessarily paid.

## Canonical inputs now populated

- `terrain.elevation_m`, `terrain.elevation_min_m`, `terrain.elevation_max_m`, `terrain.elevation_std_m`: metres above Ordnance Datum Newlyn.
- `terrain.slope_deg`, `terrain.slope_p90_deg`, `terrain.slope_max_deg`: degrees.
- `hydrology.distance_to_water_m`, `hydrology.watercourse_intersection`, `hydrology.within_100m_watercourse_fraction`.
- `land_use.current_cover`, `land_use.developed_fraction`, `ecology.mapped_wetland_fraction`, `hydrology.surface_water_fraction`.
- Existing flood/protected-area observations and positive ancient-woodland evidence continue to populate when genuinely covered.

`ecology.mapped_wetland_fraction` is deliberately separate from actual `ecology.wetland_fraction`. A mapped zero cannot remove the need to establish true extent and condition. `soil.drainage_class` and the separately named derived `soil.retention_index` are supported by explicit code but no production soil source is connected. Registered concepts alone are not connected data.

Still missing: actual wetland extent/condition, soil drainage/permeability/texture, complete road/rail/infrastructure footprints, complete irreplaceable-habitat evidence, relevant habitat distance, measured groundwater, reliable water supply, hydroperiod/water quality and catchment flow routing. Source-specific failures and outside-coverage cases remain unknown. No economics, carbon, agriculture model, tenure, groundwater simulator or other geography was added.

## Terrain calculation

`backend/terrain.py` uses `crc_ea_dtm_horn_v1`:

1. Project the exact WGS84 parcel, including holes, to EPSG:27700.
2. Request its integer-aligned bounding box plus a 3m halo from the EA **elevation** WCS coverage. Reject a response with the wrong CRS, band structure, non-native spacing, rotation, invalid values or insufficient full-parcel/slope-halo extent. The bounded request is at most 25 million native cells / 128 MiB response; a larger parcel remains unknown with a reason.
3. Use native cell centres inside the exact parcel. No filling, interpolation or resampling is introduced. Preserve nodata/nonfinite values as missing; require at least four parcel centres. All elevation statistics use valid cells; population SD uses `ddof=0`.
4. For each complete 3×3 neighbourhood `a b c / d e f / g h i`, compute:

```text
dz/dx = ((c + 2f + i) - (a + 2d + g)) / (8 × horizontal spacing)
dz/dy = ((g + 2h + i) - (a + 2b + c)) / (8 × vertical spacing)
slope_deg = atan(hypot(dz/dx, dz/dy)) × 180 / pi
```

5. Report slope mean, maximum and linearly interpolated 90th percentile. Any missing stencil cell invalidates that slope cell. Both elevation and slope retain their actual valid-cell fractions; partial coverage cannot round up to unlock a complete model component.

The EA catalogue establishes elevation units as metres above ODN. Its WCS `DescribeCoverage` carries an erroneous radiance unit tag; that inconsistency is explicitly recorded rather than treating the tag as a physical conversion. Port Meadow had 1,671,506 valid parcel centres, mean elevation 57.528m and mean slope 1.176°. Its local maximum slope is much greater; parcel means can obscure small banks and artefacts, which remain inspectable through min/max/p90 and raw DEM.

No D8 flow direction, contributing area, drainage pathway or TWI is claimed. A parcel-sized DEM cannot establish upstream catchment contribution, and unconditioned routing through bridges, culverts, depressions and flats would mislead. A wider conditioned catchment with defensible outlet/edge handling is necessary before those features are added.

## Watercourse and land-cover calculation

OS geometry stays in EPSG:27700. An exhaustive GeoPackage spatial-index envelope extends 5km beyond the parcel, retaining entire intersecting lines. A nearest line within that distance is the true minimum against the mapped source; if no such line exists, the exact distance remains unknown, not 5km or zero. Intersections and 100m-buffer overlap are geometry-derived. They are mapped adjacency, not observed water availability or functional connectivity.

WorldCover reads native COG ranges at base resolution, rejects unsupported class IDs and grids, and retains a lossless pixel subset. Cell-centre fractions are weighted by geodesic cell area at each latitude row; degrees are never relabelled as metres. Partial valid-class coverage is retained. Parcel boundaries crossing its 3° source tile boundaries remain explicitly unsupported in this implementation; no synthetic substitute is used. Dominant-class ties use stable class-code order. Class definitions and full fractions remain in each observation's method.

Mappings: tree cover→woodland, shrubland→shrubland, grassland→grassland, cropland→arable, built-up→developed, bare/sparse→bare_ground, snow/ice→snow_ice, permanent water→water, herbaceous wetland→wetland, mangroves→mangroves, moss/lichen→moss_lichen. These names represent mapped classes, not degradation or habitat condition.

## Wetland model and safeguards

Physical potential keeps slope / soil retention / water-context weights 0.35 / 0.30 / 0.35. Slope index is `max(0,1-slope_deg/10)`. Soil retention is `1-permeability` only for explicitly normalized numeric evidence; otherwise the new categorical path uses explicit ordinal priors: very poorly drained 1, poorly drained .85, imperfectly drained .65, moderately well drained .4, well drained .2, excessively drained 0. Unknown/mixed/unrecognized categories stay unknown. These priors are **not measured hydraulic coefficients or calibrated predictions**. No real categorical source was populated merely to use this path.

Water context remains the mean of mapped flood fraction and `max(0,1-distance_m/1000)`. Partial input produces an explicitly partial index. Restoration need remains `(1-wetland_fraction) × managed-cover prior + wetland_fraction × (1-condition)`, with arable .70, improved grassland .60 and wetland 0. Generic grassland, woodland, developed land or an inconsistent wetland label cannot establish this quantity. Condition is unnecessary only when actual wetland extent is established as zero. An existing healthy wetland can have high physical potential and zero restoration need.

Implementation feasibility remains the conservative bound `max(0,1-developed-infrastructure-irreplaceable_habitat)`. All constituent evidence is required. Category overlap can double-count constraints; no precise feasible footprint is claimed. Protected ecological designations prompt review without being automatic exclusions. More than half mapped built-up cover prompts a major-development review flag. Relevant-habitat proximity remains an optional ecological term.

Overall calculation retains `weighted_mean(physical .70, hydrological .20, ecological .10) × restoration_need / 100 × feasibility / 100`; missing optional ecological evidence is omitted with reduced support. **Complete physical, restoration-need and feasibility evidence is still required.** Five required slots remain missing in every real example, so there is no overall result to rank. Existing overall thresholds remain HIGH ≥65, MODERATE ≥35, otherwise LOW. Component display categories add VERY HIGH ≥85 and VERY LOW <15. These are explanatory bins, not calibrated boundaries. Internal indices remain in inspectable details/JSON rather than being the primary UX.

## Coverage, quality and model confidence

- **Required coverage:** available inputs needed by the three gating components, counted once; 10 applicable slots when wetland extent/condition are unknown. The optional habitat-proximity input is excluded. Availability alone does not prove sufficient spatial coverage or an interpretable cover category.
- **All scored-input coverage:** retains 11 applicable slots including optional habitat proximity, supporting comparison with the previous combined metric. This is retained in the evidence JSON; the primary UI shows required-input coverage, not predicted accuracy.
- **Available data quality:** mean heuristic quality among available scored evidence. Source judgements: terrain .85, rivers .80, WorldCover .65; existing overlay judgements remain. Resolution factors: ≤10m ×1, ≤30m ×.85, coarser ×.6, unknown ×.75. Unknown observation date ×.75; known age relative to the saved state ≤2 years ×1, ≤5 years ×.8, older ×.6. These are conservative engineering rules, not empirical accuracy estimates; annual/unknown dates and native resolutions remain visible.
- **Legacy combined data support:** sum adjusted quality across applicable scored evidence divided by all applicable slots, with missing=0. Port Meadow improves from 3.3/100 to 20.3/100. This is distinct from 50% required-input availability.
- **Model confidence:** always `UNVALIDATED`; no statistical intervals or predictive-accuracy claims. Derived feature quality propagates source quality and provisional inference factors without double-discounting. Time-dependent quality uses saved state time, not the current wall clock.

## Real-world verification and practical answer

The 12 examples include six actual SSSI polygons and six clearly labelled sample windows at real developed/steeper locations. No generated measurements or expected labels enter the model. Wet floodplain examples have VERY HIGH physical components on 70% physical input coverage; Wytham's hillside has LOW; urban examples vary, with mapped development identifying obvious conflict. Osney Mead's high partial physical potential alongside 99.3% built-up cover illustrates why physical potential must not become an overall restoration recommendation.

EA WWNP floodplain-reconnection geometry is benchmark-only. The bounded real extract contains 294 features, with raw geometry and seven audited repairs retained. Seven sites overlap; five do not. Absence does not mean EA considers wetland potential low. CRC cannot yet compare complete restoration rankings with this benchmark; discrepancies, missing evidence and dated land-cover conflicts are recorded per site in the report. No threshold was fitted to the examples.

**Practical answer:** CRC can now support serious inspection of terrain, mapped hydrology and land cover on these real parcels. It still cannot justify an overall restoration ranking. The highest-priority next step is an authorized Oxfordshire LandIS drainage/wetness extract, mapped conservatively with its map-scale limits; habitat extent/condition and infrastructure review will still be needed afterward.

The Sites reservation still lacks `CRC_API_URL` and its externally configured backend/auth/storage deployment. Local operation is verified separately; a disconnected frontend is not a deployed assessment product.
