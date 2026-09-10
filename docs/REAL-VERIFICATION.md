# Real Oxford parcel verification

Run: england-real-openmap-local-2026-04 · 2026-09-10T17:36:35.365706+00:00

This is a purposive engineering inspection of real Oxford locations, not independent predictive validation. Site expectations were documented before results; no example labels become model inputs and no thresholds were fitted to these examples.

Six features use actual Natural England SSSI reference geometries. Six are explicitly bounded sample windows at real developed/woodland locations, not legal property boundaries. All are inside the retained Oxford source coverage. The window coordinates and primary expectation sources are in `real-verification-sites.geojson`.

The historical Port Meadow assessment `18054630-584d-473d-8d04-653c4f2ca268` reported 3.3/100 combined data support and INSUFFICIENT_DATA. That support index is not the percentage of available inputs. The optional habitat-proximity input is excluded from the required denominator. The before/after counts below apply the identical after-applicable input list to the old overlay-only evidence and new real evidence. The before replay uses the current deterministic formula without new acquisition, rather than rewriting historical saved output.

| Site | WorldCover built-up % | OML buildings | OML building union % | Functional sites | Rail length within (m) | Track distance (m) | Station distance (m) | PHI mapped union % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Port Meadow with Wolvercote Common & Green | 0.07 | 0 | 0.00 | 0 | 0.00 | 6.85 | 967.06 | 98.90 |
| Hook Meadow and The Trap Grounds | 0.32 | 1 | 0.05 | 0 | 0.00 | 8.12 | 2197.96 | 96.55 |
| Iffley Meadows | 0.04 | 0 | 0.00 | 0 | 0.00 | unknown | unknown | 95.05 |
| Pixey and Yarnton Meads | 0.02 | 0 | 0.00 | 0 | 0.00 | 281.12 | 2118.69 | 98.89 |
| Wolvercote Meadows | 0.00 | 0 | 0.00 | 0 | 0.00 | 476.54 | 2452.76 | 97.35 |
| New Marston Meadows | 0.00 | 0 | 0.00 | 0 | 0.00 | 1417.33 | 1749.41 | 94.67 |
| Wytham Woods eastern hillside sample | 0.00 | 0 | 0.00 | 0 | 0.00 | 3027.89 | 3828.77 | 0.00 |
| Westgate shopping centre sample | 95.32 | 13 | 43.35 | 0 | 0.00 | 447.47 | 722.43 | 0.00 |
| Oxford railway station sample | 92.94 | 5 | 30.41 | 2 | 279.31 | 0.00 | 0.00 | 0.00 |
| Seacourt Park and Ride sample | 22.04 | 0 | 0.00 | 0 | 0.00 | 1230.75 | 1302.52 | 71.23 |
| Osney Mead industrial estate sample | 99.29 | 11 | 34.12 | 0 | 0.00 | 316.29 | 543.43 | 0.00 |
| Redbridge Park and Ride sample | 28.47 | 0 | 0.00 | 0 | 0.00 | unknown | unknown | 10.04 |

OpenMap Local mapped zeroes are source-and-scale observations, not claims that no real object exists. Railway tracks remain lines; their length is not converted to surface area. WorldCover and PHI remain independent evidence families and are not reconciled into the OpenMap measurements.

## Benchmark interpretation

[EA WWNP Floodplain Reconnection Potential](https://www.data.gov.uk/dataset/11873c69-d971-44ce-a648-872da9be847f/wwnp-floodplain-reconnection-potential) identifies possible reconnection, particularly currently poorly connected land near channels. It supplies binary geometry, not a high/low wetland opportunity class. A currently active floodplain can be physically wet and absent from this map. The benchmark is never fed into CRC scoring. Current land use, hydrology and consent still require site review.

Extract: 294 features; SHA-256 `9a1d6f7a1588b4242aa827d9a310b34d2f1df0afc738e7e5ec267d1127cb4f28`. Raw originals are retained; 7 invalid reference geometries require Shapely make_valid during intersection. Source creation 2017-09-01 and catalog revision 2024-05-31 are metadata dates, not parcel observation dates.

## Site evidence and remaining gaps

### Port Meadow with Wolvercote Common & Green

Low-gradient active floodplain; strong physical wetland characteristics are plausible. Existing valuable wetland/meadow does not establish restoration need or justify habitat conversion.

Expectation sources: [primary source 1](https://www.oxford.gov.uk/portmeadow).

OpenMap Local: parcel-object coverage full; rail-distance search coverage full; 0 building objects with 0.0000% unioned parcel overlap; 0 functional-site objects (none mapped); 0.000 m unioned railway track length within; nearest mapped track 6.855 m; nearest mapped station 967.064 m; 2 inspectable relationships.

WorldCover mapped built-up fraction: 0.07%. PHI mapped union: 98.90%. These can disagree because their source semantics and resolutions differ.

Available physical reasons: Mean terrain slope: 1.18°; Nearest mapped watercourse: 0.00 m.

Still missing applicable inputs: soil.drainage_class, hydrology.mapped_flood_extent_fraction, ecology.wetland_fraction, ecology.habitat_condition, human.infrastructure_fraction, ecology.irreplaceable_habitat_fraction.

Inspection / discrepancies: EA maps reconnection opportunity while CRC cannot rank restoration: Wetland physical potential, Current restoration need, Implementation feasibility. This is a missing-evidence discrepancy, not a low CRC prediction.

### Hook Meadow and The Trap Grounds

Thames floodplain meadow: low gradient and water adjacency expected; current habitat requires protection and restoration need remains unmeasured.

Expectation sources: [primary source 1](https://designatedsites.naturalengland.org.uk/SiteDetail.aspx?SiteCode=S1002183).

OpenMap Local: parcel-object coverage full; rail-distance search coverage full; 1 building objects with 0.0479% unioned parcel overlap; 0 functional-site objects (none mapped); 0.000 m unioned railway track length within; nearest mapped track 8.117 m; nearest mapped station 2197.962 m; 3 inspectable relationships.

WorldCover mapped built-up fraction: 0.32%. PHI mapped union: 96.55%. These can disagree because their source semantics and resolutions differ.

Available physical reasons: Mean terrain slope: 2.17°; Nearest mapped watercourse: 4.87 m.

Still missing applicable inputs: soil.drainage_class, hydrology.mapped_flood_extent_fraction, ecology.wetland_fraction, ecology.habitat_condition, human.infrastructure_fraction, ecology.irreplaceable_habitat_fraction.

Inspection / discrepancies: EA maps reconnection opportunity while CRC cannot rank restoration: Wetland physical potential, Current restoration need, Implementation feasibility. This is a missing-evidence discrepancy, not a low CRC prediction.

### Iffley Meadows

River Thames floodplain meadows: low gradient and flood context expected; established valuable meadow is not evidence of degradation.

Expectation sources: [primary source 1](https://www.bbowt.org.uk/nature-reserves/iffley-meadows).

OpenMap Local: parcel-object coverage full; rail-distance search coverage partial; 0 building objects with 0.0000% unioned parcel overlap; 0 functional-site objects (none mapped); 0.000 m unioned railway track length within; nearest mapped track unknown m; nearest mapped station unknown m; 0 inspectable relationships.

WorldCover mapped built-up fraction: 0.04%. PHI mapped union: 95.05%. These can disagree because their source semantics and resolutions differ.

Available physical reasons: Mean terrain slope: 1.32°; Nearest mapped watercourse: 5.39 m.

Still missing applicable inputs: soil.drainage_class, hydrology.mapped_flood_extent_fraction, ecology.wetland_fraction, ecology.habitat_condition, human.infrastructure_fraction, ecology.irreplaceable_habitat_fraction.

Inspection / discrepancies: EA maps reconnection opportunity while CRC cannot rank restoration: Wetland physical potential, Current restoration need, Implementation feasibility. This is a missing-evidence discrepancy, not a low CRC prediction.

### Pixey and Yarnton Meads

Protected Thames floodplain meadows: strong hydrological setting is plausible, with habitat safeguards and unknown restoration need.

Expectation sources: [primary source 1](https://sac.jncc.gov.uk/site/UK0012845), [primary source 2](https://www.oxford.gov.uk/portmeadow).

OpenMap Local: parcel-object coverage full; rail-distance search coverage full; 0 building objects with 0.0000% unioned parcel overlap; 0 functional-site objects (none mapped); 0.000 m unioned railway track length within; nearest mapped track 281.125 m; nearest mapped station 2118.687 m; 2 inspectable relationships.

WorldCover mapped built-up fraction: 0.02%. PHI mapped union: 98.89%. These can disagree because their source semantics and resolutions differ.

Available physical reasons: Mean terrain slope: 1.18°; Nearest mapped watercourse: 0.00 m.

Still missing applicable inputs: soil.drainage_class, hydrology.mapped_flood_extent_fraction, ecology.wetland_fraction, ecology.habitat_condition, human.infrastructure_fraction, ecology.irreplaceable_habitat_fraction.

Inspection / discrepancies: EA maps reconnection opportunity while CRC cannot rank restoration: Wetland physical potential, Current restoration need, Implementation feasibility. This is a missing-evidence discrepancy, not a low CRC prediction.

### Wolvercote Meadows

Oxford Meadows SAC floodplain grassland: low gradient and river context expected; ecological condition and intervention need require assessment.

Expectation sources: [primary source 1](https://sac.jncc.gov.uk/site/UK0012845).

OpenMap Local: parcel-object coverage full; rail-distance search coverage full; 0 building objects with 0.0000% unioned parcel overlap; 0 functional-site objects (none mapped); 0.000 m unioned railway track length within; nearest mapped track 476.543 m; nearest mapped station 2452.765 m; 2 inspectable relationships.

WorldCover mapped built-up fraction: 0.00%. PHI mapped union: 97.35%. These can disagree because their source semantics and resolutions differ.

Available physical reasons: Mean terrain slope: 1.88°; Nearest mapped watercourse: 0.00 m.

Still missing applicable inputs: soil.drainage_class, hydrology.mapped_flood_extent_fraction, ecology.wetland_fraction, ecology.habitat_condition, human.infrastructure_fraction, ecology.irreplaceable_habitat_fraction.

Inspection / discrepancies: EA maps reconnection opportunity while CRC cannot rank restoration: Wetland physical potential, Current restoration need, Implementation feasibility. This is a missing-evidence discrepancy, not a low CRC prediction.

### New Marston Meadows

Cherwell floodplain hay/grazing meadows: strong floodplain/water context expected; condition and restoration need unknown.

Expectation sources: [primary source 1](https://mycouncil.oxford.gov.uk/documents/s75799/Appendix%201%20Local%20Plan%20-%20Chapter%208%20-%20Dev%20sites%20AOF%20Infrastructure%20FINAL.pdf).

OpenMap Local: parcel-object coverage full; rail-distance search coverage full; 0 building objects with 0.0000% unioned parcel overlap; 0 functional-site objects (none mapped); 0.000 m unioned railway track length within; nearest mapped track 1417.334 m; nearest mapped station 1749.410 m; 2 inspectable relationships.

WorldCover mapped built-up fraction: 0.00%. PHI mapped union: 94.67%. These can disagree because their source semantics and resolutions differ.

Available physical reasons: Mean terrain slope: 1.50°; Nearest mapped watercourse: 0.00 m.

Still missing applicable inputs: soil.drainage_class, hydrology.mapped_flood_extent_fraction, ecology.wetland_fraction, ecology.habitat_condition, human.infrastructure_fraction, ecology.irreplaceable_habitat_fraction.

Inspection / discrepancies: EA maps reconnection opportunity while CRC cannot rank restoration: Wetland physical potential, Current restoration need, Implementation feasibility. This is a missing-evidence discrepancy, not a low CRC prediction.

### Wytham Woods eastern hillside sample

Wooded hillside: steeper terrain than floodplain examples and known woodland should constrain open-wetland creation; local springs/fens can occur and whole woodland is not uniformly dry.

Expectation sources: [primary source 1](https://maps.conted.ox.ac.uk/envsci/ecosurvey/mammals/wytham.php).

OpenMap Local: parcel-object coverage full; rail-distance search coverage full; 0 building objects with 0.0000% unioned parcel overlap; 0 functional-site objects (none mapped); 0.000 m unioned railway track length within; nearest mapped track 3027.892 m; nearest mapped station 3828.769 m; 3 inspectable relationships.

WorldCover mapped built-up fraction: 0.00%. PHI mapped union: 0.00%. These can disagree because their source semantics and resolutions differ.

Available physical reasons: Mean terrain slope: 6.60°; Nearest mapped watercourse: 1044.78 m.

Still missing applicable inputs: soil.drainage_class, hydrology.mapped_flood_extent_fraction, ecology.wetland_fraction, ecology.habitat_condition, human.infrastructure_fraction, ecology.irreplaceable_habitat_fraction.

Inspection / discrepancies: No qualitative discrepancy established; this is a desk inspection, not validation.

### Westgate shopping centre sample

Major developed retail fabric: high developed fraction expected; simple open-wetland restoration opportunity should be constrained. Physical floodplain context alone cannot override development.

Expectation sources: [primary source 1](https://www.westgateoxford.co.uk/en/plan-my-visit/getting-here).

OpenMap Local: parcel-object coverage full; rail-distance search coverage full; 13 building objects with 43.3473% unioned parcel overlap; 0 functional-site objects (none mapped); 0.000 m unioned railway track length within; nearest mapped track 447.468 m; nearest mapped station 722.430 m; 15 inspectable relationships.

WorldCover mapped built-up fraction: 95.32%. PHI mapped union: 0.00%. These can disagree because their source semantics and resolutions differ.

Available physical reasons: Mean terrain slope: 2.54°; Nearest mapped watercourse: 164.96 m.

Still missing applicable inputs: soil.drainage_class, hydrology.mapped_flood_extent_fraction, ecology.wetland_fraction, ecology.habitat_condition, human.infrastructure_fraction, ecology.irreplaceable_habitat_fraction.

Inspection / discrepancies: No EA reconnection overlap but CRC physical component is high on available evidence. Active floodplain and reconnection opportunity are different concepts; incomplete physical component is not an established disagreement.

### Oxford railway station sample

Active rail station and infrastructure: rail/development evidence expected and ordinary wetland creation should be constrained.

Expectation sources: [primary source 1](https://www.gwr.com/stations-and-destinations/stations/oxford).

OpenMap Local: parcel-object coverage full; rail-distance search coverage full; 5 building objects with 30.4075% unioned parcel overlap; 2 functional-site objects (Road Transport / Bus Station, Said Business School — Education / Higher or University Education); 279.310 m unioned railway track length within; nearest mapped track 0.000 m; nearest mapped station 0.000 m; 23 inspectable relationships.

WorldCover mapped built-up fraction: 92.94%. PHI mapped union: 0.00%. These can disagree because their source semantics and resolutions differ.

Available physical reasons: Mean terrain slope: 4.97°; Nearest mapped watercourse: 78.49 m.

Still missing applicable inputs: soil.drainage_class, hydrology.mapped_flood_extent_fraction, ecology.wetland_fraction, ecology.habitat_condition, human.infrastructure_fraction, ecology.irreplaceable_habitat_fraction.

Inspection / discrepancies: No EA reconnection overlap but CRC physical component is high on available evidence. Active floodplain and reconnection opportunity are different concepts; incomplete physical component is not an established disagreement.

### Seacourt Park and Ride sample

Operational car park in floodplain setting: water context may be strong while current development constrains conversion. Council reports its expansion also stores floodwater; low feasibility and wet physical setting can coexist.

Expectation sources: [primary source 1](https://www.oxford.gov.uk/seacourt), [primary source 2](https://www.oxford.gov.uk/building-projects/seacourt-park-ride-development).

OpenMap Local: parcel-object coverage full; rail-distance search coverage full; 0 building objects with 0.0000% unioned parcel overlap; 0 functional-site objects (none mapped); 0.000 m unioned railway track length within; nearest mapped track 1230.750 m; nearest mapped station 1302.517 m; 2 inspectable relationships.

WorldCover mapped built-up fraction: 22.04%. PHI mapped union: 71.23%. These can disagree because their source semantics and resolutions differ.

Available physical reasons: Mean terrain slope: 4.15°; Nearest mapped watercourse: 0.00 m.

Still missing applicable inputs: soil.drainage_class, hydrology.mapped_flood_extent_fraction, ecology.wetland_fraction, ecology.habitat_condition, human.infrastructure_fraction, ecology.irreplaceable_habitat_fraction.

Inspection / discrepancies: No EA reconnection overlap but CRC physical component is high on available evidence. Active floodplain and reconnection opportunity are different concepts; incomplete physical component is not an established disagreement. Mapped developed fraction is below half of this operational developed-site sample. Inspect source class definition, source age and sample geometry; do not assume land is freely restorable.

### Osney Mead industrial estate sample

Industrial/brownfield land in floodplain: developed evidence should constrain conversion even with strong water context; no inference about future redevelopment permissions.

Expectation sources: [primary source 1](https://www.oxford.gov.uk/directory-record/2754/osney-mead), [primary source 2](https://www.oxford.gov.uk/downloads/file/4010/spcw8-osney-mead---site-capacity-assessment).

OpenMap Local: parcel-object coverage full; rail-distance search coverage full; 11 building objects with 34.1152% unioned parcel overlap; 0 functional-site objects (none mapped); 0.000 m unioned railway track length within; nearest mapped track 316.287 m; nearest mapped station 543.428 m; 13 inspectable relationships.

WorldCover mapped built-up fraction: 99.29%. PHI mapped union: 0.00%. These can disagree because their source semantics and resolutions differ.

Available physical reasons: Mean terrain slope: 1.64°; Nearest mapped watercourse: 104.72 m.

Still missing applicable inputs: soil.drainage_class, hydrology.mapped_flood_extent_fraction, ecology.wetland_fraction, ecology.habitat_condition, human.infrastructure_fraction, ecology.irreplaceable_habitat_fraction.

Inspection / discrepancies: No EA reconnection overlap but CRC physical component is high on available evidence. Active floodplain and reconnection opportunity are different concepts; incomplete physical component is not an established disagreement.

### Redbridge Park and Ride sample

Operational car park: current hard development/infrastructure should constrain straightforward wetland creation despite low-lying setting.

Expectation sources: [primary source 1](https://www.oxford.gov.uk/redbridgeparkandride).

OpenMap Local: parcel-object coverage full; rail-distance search coverage partial; 0 building objects with 0.0000% unioned parcel overlap; 0 functional-site objects (none mapped); 0.000 m unioned railway track length within; nearest mapped track unknown m; nearest mapped station unknown m; 0 inspectable relationships.

WorldCover mapped built-up fraction: 28.47%. PHI mapped union: 10.04%. These can disagree because their source semantics and resolutions differ.

Available physical reasons: Mean terrain slope: 6.19°; Nearest mapped watercourse: 0.00 m.

Still missing applicable inputs: soil.drainage_class, hydrology.mapped_flood_extent_fraction, ecology.wetland_fraction, ecology.habitat_condition, human.infrastructure_fraction, ecology.irreplaceable_habitat_fraction.

Inspection / discrepancies: EA maps reconnection opportunity while CRC cannot rank restoration: Wetland physical potential, Current restoration need, Implementation feasibility. This is a missing-evidence discrepancy, not a low CRC prediction. Mapped developed fraction is below half of this operational developed-site sample. Inspect source class definition, source age and sample geometry; do not assume land is freely restorable.

## Reproduction and limits

Run `.venv/bin/python scripts/verify_real_parcels.py` with the same database and environment as the worker. The script reads shared overlay datasets but creates no workspace sites or assessment database rows. Normal immutable acquisition artifacts and full before/pre-PHI/pre-built/after outputs are retained under `data/`. `real-verification-results.json` retains model signatures, exact object and relationship records, selected observations, source lineage, discrepancies and replay results.

Every completed site passed deterministic replay, non-synthetic-input checks and raw/parent provenance resolution. Adding PHI and then OpenMap Local each left the complete legacy wetland result and bound environmental state exactly unchanged at every site. A PHI-era pre-built snapshot and a built-world-enriched snapshot were committed for every boundary; each old manifest was re-read after the new commit and remained byte-identical.

These checks verify computation, not ecological truth. The examples share geography and data sources, include existing valuable habitats, and do not form a randomized holdout. PHI is an inventory rather than a current field survey: mapped zero is not ecological absence, mapped habitat is not a condition assessment, and no known-wetland label establishes restoration need or feasibility. The main scientific gaps are recorded explicitly per site.
