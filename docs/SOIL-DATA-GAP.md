# England soil evidence: access and interpretation

Checked 8 September 2026. No production soil drainage or permeability measurements were downloaded or populated in this iteration.

## Best practical next source

Cranfield/Defra's LandIS Portal is the preferred next route for England and Wales soil information. Its access status changed recently: Cranfield announced free access on **28 April 2026**. Older descriptions of Soilscapes as solely a paid product are therefore not an adequate description of current access. [Cranfield announcement](https://www.cranfield.ac.uk/press/news-2026/uks-national-soil-database-goes-open-access).

The public [LandIS Portal](https://portal.landis.org.uk/) was inspected in the browser. It explicitly requires a free registered account to access the data. Its public legal summary makes access subject to its [End User Licence Agreement](https://cranfield-portal.maps.arcgis.com/sharing/rest/content/items/91f00fd749314faa8356f9e41b65ff8c/data) and requires attribution naming the source file/report, publication date and access year. The [account instructions](https://portal.landis.org.uk/pages/create-account) are the published access route. No account was created, agreement accepted, or authenticated dataset endpoint verified during this task. **The present gap is an unconnected registered data source, not evidence that English soil data does not exist or must be purchased.**

Soilscapes provides a categorical `DRAINAGE` description, plus general soil and texture descriptions. It is a simplified national map intended for **1:250,000** use. Its expected land-cover and habitat descriptions describe associations with a soil type; they are not observations of the parcel's current cover or habitat condition. [Cranfield Soilscapes description](https://www.landis.org.uk/data/nmsoilscapes.cfm).

The more explicit NATMAP Wetness product represents six soil wetness classes, combines soil associations with climate zones, and preserves percentages of classes within a map polygon. These percentages describe the composition of the mapped association; a small parcel inside that polygon does not necessarily have the same composition. Product availability under the new portal agreement still needs verification after registration. [Cranfield NATMAP Wetness description](https://www.landis.org.uk/data/nmwetness.cfm).

## Conservative integration contract

1. Acquire an authorized extract with its original geometry, attribute dictionary, publication metadata and licence/attribution. Keep the original file and checksum alongside the processing snapshot.
2. Preserve explicit drainage categories as `soil.drainage_class`; retain the provider description and source map scale in provenance. Unknown, variable or mixed descriptions must not be forced into a single drainage category.
3. Do not convert an ordinal drainage description to a measured coefficient. `soil.permeability` remains null unless an independently justified numeric source and normalization are available. A CRC drainage-based retention index, if used, stays a separately named, uncalibrated inference.
4. Intersect all relevant map units; preserve their competing or mixed evidence. Do not treat a centroid sample, dominant regional association or map-unit percentage as a parcel soil survey. Report boundary uncertainty and coarse spatial support.
5. Retain the source observation dates as unknown when not supplied. A 2026 portal release or retrieval date does not establish that its constituent soil surveys were performed in 2026.
6. Do not infer actual wetland absence, habitat condition, current land cover, artificial drainage or measured groundwater from soil classifications. Field verification remains necessary before an intervention decision.

## Alternatives considered

| Source | Actual information and access | Why it does not close this gap now |
|---|---|---|
| [ISRIC SoilGrids](https://docs.isric.org/globaldata/soilgrids/) and its [WCS access documentation](https://docs.isric.org/globaldata/soilgrids/wcs.html) | Modelled texture and other soil properties at 250 m; documented public spatial subsetting. | Clay is useful contextual evidence, but is neither drainage class nor hydraulic conductivity. No clay-only conversion to permeability is justified here. No live SoilGrids extract was verified in this task. |
| [European Soil Database v2 raster library](https://esdac.jrc.ec.europa.eu/content/european-soil-database-v2-raster-library-1kmx1km) | Categorical interpretations of the European database in 1 km cells, with attribute legends; access uses a request form. | Registered access is not yet established, and regional support is too coarse to claim a parcel soil measurement. |
| [EU-SoilHydroGrids](https://esdac.jrc.ec.europa.eu/content/3d-soil-hydraulic-database-europe-1-km-and-250-m-resolution) | Predicted hydraulic properties including saturated hydraulic conductivity at 250 m/1 km and multiple depths; derived from SoilGrids and pedotransfer functions. | Requires a data request and interpretation of the supplied terms. These are modelled hydraulic properties for catchment/continental use, not measured parcel permeability. The publisher page lists ODbL and also restrictions on passing data to third parties; CRC's raw-data export needs the applicable terms resolved before integration. |
| [NATMAP HOST](https://www.landis.org.uk/data/nmhost.cfm) | Twenty-nine soil hydrological response classes, preserving component proportions. | Its current product page explicitly excludes it from the open datasets. HOST codes must not be treated as a linear permeability scale. |

The next concrete step is to establish the LandIS registered access and applicable rights, obtain an Oxfordshire drainage/wetness extract, and test its map-unit interpretation against local soil observations. Existing null soil values should remain visible until that extract is actually connected.
