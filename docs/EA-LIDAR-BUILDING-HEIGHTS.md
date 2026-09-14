# EA LIDAR building-height evidence

## Scope

`land_evidence_registry_v4` adds one narrow object-level evidence type: `BuildingHeightObservation`. It links an immutable OS OpenMap Local `MappedBuildingObject` to a historical Environment Agency surface-height estimate. It does not add height to the building object, infer floors or current use, create a general graph, or change the historical wetland model.

The authoritative inputs are bounded native-grid WCS responses from:

- [EA LIDAR Composite Digital Surface Model (DSM) 1m](https://www.data.gov.uk/dataset/cf3f1137-c12b-44a1-a835-e80fe4a60b92/lidar-composite-digital-surface-model-dsm-1m), coverage `9ba4d5ac-d596-445a-9056-dae3ddec0178__Lidar_Composite_Elevation_LZ_DSM_1m`;
- [EA LIDAR Composite Digital Terrain Model (DTM) 1m](https://www.data.gov.uk/dataset/01b3ee39-da3f-47b6-83da-dc98e73a461f/lidar-composite-digital-terrain-model-dtm-1m), coverage `13787b9a-26a4-4775-8523-806d13af58fc__Lidar_Composite_Elevation_DTM_1m`.

The DSM is a last-return composite containing terrain, buildings, vegetation and vehicles. Its constituent surveys span 2000–2022 and the local survey date is not established by this acquisition. Every output is therefore a historical composite surface-height estimate, never a contemporary, legal or engineering building survey.

## Acquisition and retention

For a new assessment containing retained mapped buildings, the worker requests one DSM and one DTM crop over the complete set of building footprints. Both use the same integer EPSG:27700 bounds. It retains, byte-for-byte:

- both `DescribeCoverage` responses;
- both GeoTIFF `GetCoverage` responses;
- each exact resolved WCS request URL;
- retrieval time and available response identity headers;
- SHA-256 for every response;
- the requested EPSG:27700 bounds; and
- the declared composite survey metadata and limitations.

Raw bytes are content-addressed in private object storage. The assessment-specific acquisition bundle is immutable and reused on retry. Raw rasters, local databases and verification downloads are excluded from Git.

Acquisition runs after the unchanged legacy wetland calculation. DSM/DTM height inputs therefore do not enter `crc_earth_v0_1`, change legacy selections or alter wetland ModuleRuns.

## Deterministic method

Processing version: `crc_ea_lidar_building_height_v1`.

1. Require single-band EPSG:27700 DSM and DTM rasters on matching north-up native 1 m grids. Shape and affine transform must match.
2. Subtract co-registered cells as `DSM − DTM`; never resample, interpolate, fill nodata or substitute a height.
3. Buffer the mapped building footprint inward by exactly 1 m to reduce boundary mixing. Holes remain excluded. Sample native cell centres only.
4. Treat finite paired differences from 0 m through 500 m as numerically valid. Negative or unsafe values are excluded, not clamped.
5. Require at least nine valid cells and at least 80% valid coverage of candidate interior cell centres.
6. Compute the median and median absolute deviation. Retain samples within robust z 3.5, using a fixed 0.0001 m precision floor so float32 subtraction noise around a constant surface is not misclassified as an outlier.
7. Require at least nine retained samples. Store full-precision P50 and linear P90, candidate/valid/retained counts, coverage and MAD. P90 is the declared map-extrusion estimate.

Every mapped building receives exactly one v4 outcome: a `BuildingHeightObservation` or an object-linked `BuildingHeightEvidenceGap`. Explicit reasons cover acquisition failure, grid mismatch, insufficient raster extent, too-small footprints, invalid surface values, insufficient valid coverage and insufficient filtered samples.

## Evidence semantics

- A valid value is evidence about an aged composite surface, not current building height.
- DSM signals can include vegetation and vehicles; footprint generalisation and roof form can mix surfaces even after buffering.
- Coverage describes usable cell centres for this method. It is not predictive confidence.
- A gap is not zero height. A low or zero surface difference is retained only when supported by valid source cells and the same deterministic method.
- The source object remains the immutable OpenMap Local building. The observation carries the DSM/DTM lineage; the object does not acquire mutable measurement fields.

## Oxford Station verification

The retained Oxford Station exemplar contains five mapped buildings. A live verification on 14 September 2026 retrieved a 225 × 233 m paired crop and produced five valid outcomes. P90 estimates were 8.311004638671875 m, 9.844306564331054 m, 2.9220027923583984 m, 8.572006225585938 m and 15.893474578857422 m; valid interior coverage ranged from 98.40432215102399% to 100%.

Exact request URLs, raw hashes, source-object keys, full-precision P50/P90 values and sample counts are retained in [the Oxford verification record](sprints/005-oxford-station-building-heights.json). Run `.venv/bin/python scripts/verify_oxford_building_heights.py` to reacquire the bounded official responses, compare their identities and replay the calculation twice from the same bytes. The script uses a temporary directory and commits no raw source data.

## Compatibility

Registries v1–v3 remain accepted and their definitions, object identities, content documents and stored manifests are unchanged. The retained Oxford v3 content hash remains `507d8ef7b2688ccb911aeeb483c94a1d15924a4b3a7bf6a1cf83e614ae2a6ab8`. A v4 snapshot has a new registry/content identity while retaining the existing v3 building object IDs. `screening_context_map_features_v1` continues to expose the same built-world geometry and measurements; it does not reinterpret height evidence.
