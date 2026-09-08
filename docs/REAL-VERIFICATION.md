# Real Oxford parcel verification

Run: england-real-v1-final · 2026-09-08T14:50:45.174090+00:00

This is a purposive engineering inspection of real Oxford locations, not independent predictive validation. Site expectations were documented before results; no example labels become model inputs and no thresholds were fitted to these examples.

Six features use actual Natural England SSSI reference geometries. Six are explicitly bounded sample windows at real developed/woodland locations, not legal property boundaries. All are inside the retained Oxford flood-data corridor. The window coordinates and primary expectation sources are in `real-verification-sites.geojson`.

The historical Port Meadow assessment `18054630-584d-473d-8d04-653c4f2ca268` reported 3.3/100 combined data support and INSUFFICIENT_DATA. That support index is not the percentage of available inputs. The optional habitat-proximity input is excluded from the required denominator. The before/after counts below apply the identical after-applicable input list to the old overlay-only evidence and new real evidence. The before replay uses the current deterministic formula without new acquisition, rather than rewriting historical saved output.

| Site | Before required inputs | After required inputs | Overall | Physical component (coverage) | Slope ° | Water distance m | Developed % | EA reconnection overlap % |
|---|---:|---:|---|---|---:|---:|---:|---:|
| Port Meadow with Wolvercote Common & Green | 1/10 | 5/10 | INSUFFICIENT_DATA | VERY_HIGH (70%; partial) | 1.18 | 0.0 | 0.1 | 3.21 |
| Hook Meadow and The Trap Grounds | 1/10 | 5/10 | INSUFFICIENT_DATA | VERY_HIGH (70%; partial) | 2.17 | 4.9 | 0.3 | 0.22 |
| Iffley Meadows | 1/10 | 5/10 | INSUFFICIENT_DATA | VERY_HIGH (70%; partial) | 1.32 | 5.4 | 0.0 | 2.37 |
| Pixey and Yarnton Meads | 1/10 | 5/10 | INSUFFICIENT_DATA | VERY_HIGH (70%; partial) | 1.18 | 0.0 | 0.0 | 0.63 |
| Wolvercote Meadows | 1/10 | 5/10 | INSUFFICIENT_DATA | VERY_HIGH (70%; partial) | 1.88 | 0.0 | 0.0 | 2.93 |
| New Marston Meadows | 1/10 | 5/10 | INSUFFICIENT_DATA | VERY_HIGH (70%; partial) | 1.50 | 0.0 | 0.0 | 5.70 |
| Wytham Woods eastern hillside sample | 1/10 | 5/10 | INSUFFICIENT_DATA | LOW (70%; partial) | 6.60 | 1044.8 | 0.0 | 0.00 |
| Westgate shopping centre sample | 1/10 | 5/10 | INSUFFICIENT_DATA | MODERATE (70%; partial) | 2.54 | 165.0 | 95.3 | 0.00 |
| Oxford railway station sample | 1/10 | 5/10 | INSUFFICIENT_DATA | MODERATE (70%; partial) | 4.97 | 78.5 | 92.9 | 0.00 |
| Seacourt Park and Ride sample | 1/10 | 5/10 | INSUFFICIENT_DATA | HIGH (70%; partial) | 4.15 | 0.0 | 22.0 | 0.00 |
| Osney Mead industrial estate sample | 1/10 | 5/10 | INSUFFICIENT_DATA | HIGH (70%; partial) | 1.64 | 104.7 | 99.3 | 0.00 |
| Redbridge Park and Ride sample | 1/10 | 5/10 | INSUFFICIENT_DATA | MODERATE (70%; partial) | 6.19 | 0.0 | 28.5 | 0.15 |

Physical bands based on incomplete evidence are partial component descriptions; they do not unlock restoration rankings. Data quality is a heuristic about available source evidence. Model confidence remains UNVALIDATED.

## Benchmark interpretation

[EA WWNP Floodplain Reconnection Potential](https://www.data.gov.uk/dataset/11873c69-d971-44ce-a648-872da9be847f/wwnp-floodplain-reconnection-potential) identifies possible reconnection, particularly currently poorly connected land near channels. It supplies binary geometry, not a high/low wetland opportunity class. A currently active floodplain can be physically wet and absent from this map. The benchmark is never fed into CRC scoring. Current land use, hydrology and consent still require site review.

Extract: 294 features; SHA-256 `9a1d6f7a1588b4242aa827d9a310b34d2f1df0afc738e7e5ec267d1127cb4f28`. Raw originals are retained; 7 invalid reference geometries require Shapely make_valid during intersection. Source creation 2017-09-01 and catalog revision 2024-05-31 are metadata dates, not parcel observation dates.

## Site evidence and remaining gaps

### Port Meadow with Wolvercote Common & Green

Low-gradient active floodplain; strong physical wetland characteristics are plausible. Existing valuable wetland/meadow does not establish restoration need or justify habitat conversion.

Expectation sources: [primary source 1](https://www.oxford.gov.uk/portmeadow).

Available physical reasons: Mean terrain slope: 1.18°; Nearest mapped watercourse: 0.00 m; Mapped flood-zone overlap: 0.97 of parcel.

Still missing applicable inputs: soil.drainage_class, ecology.wetland_fraction, ecology.habitat_condition, human.infrastructure_fraction, ecology.irreplaceable_habitat_fraction.

Inspection / discrepancies: EA maps reconnection opportunity while CRC cannot rank restoration: Wetland physical potential, Current restoration need, Implementation feasibility. This is a missing-evidence discrepancy, not a low CRC prediction.

### Hook Meadow and The Trap Grounds

Thames floodplain meadow: low gradient and water adjacency expected; current habitat requires protection and restoration need remains unmeasured.

Expectation sources: [primary source 1](https://designatedsites.naturalengland.org.uk/SiteDetail.aspx?SiteCode=S1002183).

Available physical reasons: Mean terrain slope: 2.17°; Nearest mapped watercourse: 4.87 m; Mapped flood-zone overlap: 0.96 of parcel.

Still missing applicable inputs: soil.drainage_class, ecology.wetland_fraction, ecology.habitat_condition, human.infrastructure_fraction, ecology.irreplaceable_habitat_fraction.

Inspection / discrepancies: EA maps reconnection opportunity while CRC cannot rank restoration: Wetland physical potential, Current restoration need, Implementation feasibility. This is a missing-evidence discrepancy, not a low CRC prediction.

### Iffley Meadows

River Thames floodplain meadows: low gradient and flood context expected; established valuable meadow is not evidence of degradation.

Expectation sources: [primary source 1](https://www.bbowt.org.uk/nature-reserves/iffley-meadows).

Available physical reasons: Mean terrain slope: 1.32°; Nearest mapped watercourse: 5.39 m; Mapped flood-zone overlap: 1.00 of parcel.

Still missing applicable inputs: soil.drainage_class, ecology.wetland_fraction, ecology.habitat_condition, human.infrastructure_fraction, ecology.irreplaceable_habitat_fraction.

Inspection / discrepancies: EA maps reconnection opportunity while CRC cannot rank restoration: Wetland physical potential, Current restoration need, Implementation feasibility. This is a missing-evidence discrepancy, not a low CRC prediction.

### Pixey and Yarnton Meads

Protected Thames floodplain meadows: strong hydrological setting is plausible, with habitat safeguards and unknown restoration need.

Expectation sources: [primary source 1](https://sac.jncc.gov.uk/site/UK0012845), [primary source 2](https://www.oxford.gov.uk/portmeadow).

Available physical reasons: Mean terrain slope: 1.18°; Nearest mapped watercourse: 0.00 m; Mapped flood-zone overlap: 1.00 of parcel.

Still missing applicable inputs: soil.drainage_class, ecology.wetland_fraction, ecology.habitat_condition, human.infrastructure_fraction, ecology.irreplaceable_habitat_fraction.

Inspection / discrepancies: EA maps reconnection opportunity while CRC cannot rank restoration: Wetland physical potential, Current restoration need, Implementation feasibility. This is a missing-evidence discrepancy, not a low CRC prediction.

### Wolvercote Meadows

Oxford Meadows SAC floodplain grassland: low gradient and river context expected; ecological condition and intervention need require assessment.

Expectation sources: [primary source 1](https://sac.jncc.gov.uk/site/UK0012845).

Available physical reasons: Mean terrain slope: 1.88°; Nearest mapped watercourse: 0.00 m; Mapped flood-zone overlap: 1.00 of parcel.

Still missing applicable inputs: soil.drainage_class, ecology.wetland_fraction, ecology.habitat_condition, human.infrastructure_fraction, ecology.irreplaceable_habitat_fraction.

Inspection / discrepancies: EA maps reconnection opportunity while CRC cannot rank restoration: Wetland physical potential, Current restoration need, Implementation feasibility. This is a missing-evidence discrepancy, not a low CRC prediction.

### New Marston Meadows

Cherwell floodplain hay/grazing meadows: strong floodplain/water context expected; condition and restoration need unknown.

Expectation sources: [primary source 1](https://mycouncil.oxford.gov.uk/documents/s75799/Appendix%201%20Local%20Plan%20-%20Chapter%208%20-%20Dev%20sites%20AOF%20Infrastructure%20FINAL.pdf).

Available physical reasons: Mean terrain slope: 1.50°; Nearest mapped watercourse: 0.00 m; Mapped flood-zone overlap: 0.88 of parcel.

Still missing applicable inputs: soil.drainage_class, ecology.wetland_fraction, ecology.habitat_condition, human.infrastructure_fraction, ecology.irreplaceable_habitat_fraction.

Inspection / discrepancies: EA maps reconnection opportunity while CRC cannot rank restoration: Wetland physical potential, Current restoration need, Implementation feasibility. This is a missing-evidence discrepancy, not a low CRC prediction.

### Wytham Woods eastern hillside sample

Wooded hillside: steeper terrain than floodplain examples and known woodland should constrain open-wetland creation; local springs/fens can occur and whole woodland is not uniformly dry.

Expectation sources: [primary source 1](https://maps.conted.ox.ac.uk/envsci/ecosurvey/mammals/wytham.php).

Available physical reasons: Mean terrain slope: 6.60°; Nearest mapped watercourse: 1044.78 m; Mapped flood-zone overlap: 0.00 of parcel.

Still missing applicable inputs: soil.drainage_class, ecology.wetland_fraction, ecology.habitat_condition, human.infrastructure_fraction, ecology.irreplaceable_habitat_fraction.

Inspection / discrepancies: No qualitative discrepancy established; this is a desk inspection, not validation.

### Westgate shopping centre sample

Major developed retail fabric: high developed fraction expected; simple open-wetland restoration opportunity should be constrained. Physical floodplain context alone cannot override development.

Expectation sources: [primary source 1](https://www.westgateoxford.co.uk/en/plan-my-visit/getting-here).

Available physical reasons: Mean terrain slope: 2.54°; Nearest mapped watercourse: 164.96 m; Mapped flood-zone overlap: 0.16 of parcel.

Still missing applicable inputs: soil.drainage_class, ecology.wetland_fraction, ecology.habitat_condition, human.infrastructure_fraction, ecology.irreplaceable_habitat_fraction.

Inspection / discrepancies: No qualitative discrepancy established; this is a desk inspection, not validation.

### Oxford railway station sample

Active rail station and infrastructure: rail/development evidence expected and ordinary wetland creation should be constrained.

Expectation sources: [primary source 1](https://www.gwr.com/stations-and-destinations/stations/oxford).

Available physical reasons: Mean terrain slope: 4.97°; Nearest mapped watercourse: 78.49 m; Mapped flood-zone overlap: 0.09 of parcel.

Still missing applicable inputs: soil.drainage_class, ecology.wetland_fraction, ecology.habitat_condition, human.infrastructure_fraction, ecology.irreplaceable_habitat_fraction.

Inspection / discrepancies: No qualitative discrepancy established; this is a desk inspection, not validation.

### Seacourt Park and Ride sample

Operational car park in floodplain setting: water context may be strong while current development constrains conversion. Council reports its expansion also stores floodwater; low feasibility and wet physical setting can coexist.

Expectation sources: [primary source 1](https://www.oxford.gov.uk/seacourt), [primary source 2](https://www.oxford.gov.uk/building-projects/seacourt-park-ride-development).

Available physical reasons: Mean terrain slope: 4.15°; Nearest mapped watercourse: 0.00 m; Mapped flood-zone overlap: 1.00 of parcel.

Still missing applicable inputs: soil.drainage_class, ecology.wetland_fraction, ecology.habitat_condition, human.infrastructure_fraction, ecology.irreplaceable_habitat_fraction.

Inspection / discrepancies: No EA reconnection overlap but CRC physical component is high on available evidence. Active floodplain and reconnection opportunity are different concepts; incomplete physical component is not an established disagreement. Mapped developed fraction is below half of this operational developed-site sample. Inspect source class definition, source age and sample geometry; do not assume land is freely restorable.

### Osney Mead industrial estate sample

Industrial/brownfield land in floodplain: developed evidence should constrain conversion even with strong water context; no inference about future redevelopment permissions.

Expectation sources: [primary source 1](https://www.oxford.gov.uk/directory-record/2754/osney-mead), [primary source 2](https://www.oxford.gov.uk/downloads/file/4010/spcw8-osney-mead---site-capacity-assessment).

Available physical reasons: Mean terrain slope: 1.64°; Nearest mapped watercourse: 104.72 m; Mapped flood-zone overlap: 0.80 of parcel.

Still missing applicable inputs: soil.drainage_class, ecology.wetland_fraction, ecology.habitat_condition, human.infrastructure_fraction, ecology.irreplaceable_habitat_fraction.

Inspection / discrepancies: No EA reconnection overlap but CRC physical component is high on available evidence. Active floodplain and reconnection opportunity are different concepts; incomplete physical component is not an established disagreement.

### Redbridge Park and Ride sample

Operational car park: current hard development/infrastructure should constrain straightforward wetland creation despite low-lying setting.

Expectation sources: [primary source 1](https://www.oxford.gov.uk/redbridgeparkandride).

Available physical reasons: Mean terrain slope: 6.19°; Nearest mapped watercourse: 0.00 m; Mapped flood-zone overlap: 0.13 of parcel.

Still missing applicable inputs: soil.drainage_class, ecology.wetland_fraction, ecology.habitat_condition, human.infrastructure_fraction, ecology.irreplaceable_habitat_fraction.

Inspection / discrepancies: EA maps reconnection opportunity while CRC cannot rank restoration: Wetland physical potential, Current restoration need, Implementation feasibility. This is a missing-evidence discrepancy, not a low CRC prediction. Mapped developed fraction is below half of this operational developed-site sample. Inspect source class definition, source age and sample geometry; do not assume land is freely restorable.

## Reproduction and limits

Run `.venv/bin/python scripts/verify_real_parcels.py` with the same database and environment as the worker. The script reads shared overlay datasets but creates no workspace sites or assessment database rows. Normal immutable acquisition artifacts and full before/after outputs are retained under `data/`. `real-verification-results.json` retains model signatures, exact counts, selected observations, source lineage, discrepancies and replay results.

Every completed site passed deterministic replay, non-synthetic-input checks and raw/parent provenance resolution. These checks verify computation, not ecological truth. The examples share geography and data sources, include existing valuable habitats, and do not form a randomized holdout. No known-wetland label establishes current habitat condition or restoration need. The main scientific gaps are recorded explicitly per site.
