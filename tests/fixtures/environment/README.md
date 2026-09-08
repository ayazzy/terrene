# Real environmental regression fixtures

These files retain real provider values, not synthetic production substitutes.

- `port_meadow_worldcover.tif`: lossless native COG window from ESA WorldCover 2021 v200, all original classification codes unchanged. JSON retains the original tile URL, retrieval time, native transform and SHA-256. The annual reference year is 2021; it does not describe today's habitat condition. © ESA WorldCover project 2021; CC BY 4.0. https://esa-worldcover.org/en/data-access
- `port_meadow_rivers.json`: unchanged OS Open Rivers native coordinates/IDs extracted from the verified April 2026 GeoPackage, retaining original archive checksum and download URL. EPSG:27700, not WGS84. Generalized mapping, not a ditch survey. Contains OS data © Crown copyright and database right 2026; Open Government Licence v3. https://osdatahub.os.uk/downloads/open/OpenRivers

Full production source artifacts remain under `data/environmental` and private object storage; fixture paths in captured metadata identify the original local acquisition, while tests open the adjacent retained fixtures and verify their checksums. Tests separately create explicitly synthetic analytical grids/networks for edge cases, never selected by production code.
