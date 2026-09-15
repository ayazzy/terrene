# Independent historical weather acquisition

Implemented 15 September 2026. This adds regional historical weather context to
Terrene Earth without a Site, assessment or model run.

## Source and suitability

`nasa.power_merra2_daily` / `nasa_power_daily_point_v1` retrieves NASA POWER's
AG-community daily meteorology from the MERRA-2 assimilation/reanalysis model.
This is modelled evidence informed by observations, not station measurements.
Source grids are nominally 0.5 degrees latitude by 0.625 degrees longitude. The
service is global, including all UK nations, but those coarse cells cannot resolve
individual farms or local rainfall/extremes. A queried point is not a measured
weather station, a parcel average or an identified native cell centre.

NASA POWER provides public access without an API key and permits commercial
applications with acknowledgement. This avoids coupling this first adapter to a
non-commercial free API tier. Higher-resolution HadUK-Grid or another regional
source needs separate access, source identity and scientific semantics; it is not
substituted or blended here.

Primary references:

- [NASA daily API and time conventions](https://power.larc.nasa.gov/docs/services/api/temporal/daily/)
- [NASA resolution documentation](https://power.larc.nasa.gov/docs/tutorials/service-data-request/api/)
- [NASA sources, units and limitations](https://power.larc.nasa.gov/docs/faqs/data/)
- [NASA commercial-use and acknowledgement guidance](https://forum.earthdata.nasa.gov/viewtopic.php?t=82)
- [Met Office HadUK-Grid](https://www.metoffice.gov.uk/research/climate/maps-and-data/data/haduk-grid/haduk-grid)

## Contract and evidence semantics

`geographic_weather_request_v1` requires an explicit WGS84 Point, inclusive
calendar start/end dates, UTC, registered source/adapter and idempotency key.
It deliberately has no polygon or administrative coverage-profile field. A
point response does not establish spatial completeness for surrounding land.
Requests begin no earlier than 1981 and contain at most 366 days. Capture refuses
periods ending fewer than 120 days before the current UTC date, and responses
whose declared sources differ from `MERRA2, POWER`. The age guard is an operational
policy, not a guarantee that NASA will never revise historical data.

The fixed v1 variable set is:

| Variable | Meaning | Native unit |
| --- | --- | --- |
| T2M | Daily mean air temperature at 2 m | C |
| T2M_MIN | Daily minimum air temperature at 2 m | C |
| T2M_MAX | Daily maximum air temperature at 2 m | C |
| PRECTOTCORR | Daily bias-corrected precipitation rate | mm/day |
| WS10M | Daily mean wind speed at 10 m | m/s |
| RH2M | Daily mean relative humidity at 2 m | % |

Values remain in the returned AG-community units. Precipitation is not relabelled
as a period total. Daily UTC dates are distinct from capture time, API version
and an unknown immutable publisher release. The provider's returned coordinates
and grid-averaged elevation are preserved separately from the requested point;
no site altitude or native-cell identifier is fabricated. Coordinate readback
allows up to 0.00051 degrees of provider rounding per axis.

Every expected variable/day has an explicit state: present, absent date, provider
null or provider fill. Missing values normalize to null with their original reason;
real zero remains present. Missing an entire declared variable is a schema failure.
An empty declared daily series can be captured successfully with `no_valid_days`.
Availability counts are not model suitability or predictive confidence.

## Retention and validation

Existing organization-scoped requests, attempts, leases, immutable object hashes
and integrity reads are reused. No schema migration or dependency was added;
legacy geographic/satellite request defaults and hashes remain unchanged.

Two bounded requests must agree on all normalized evidence and source metadata.
Only provider runtime timing fields are excluded from the semantic comparison;
the full original responses remain retained as binary bytes. Normalization rejects
wrong models, locations, UTC periods, units, unexpected dates, duplicate JSON keys,
nonfinite/invalid values, provider warnings and inconsistent temperature ranges.
Broad physical bounds reject implausible values without replacing or clamping them.

The artifacts are `provider_response_before`, `provider_response_after`,
`source_metadata`, `series` and `result`. Successful reads replay both original
responses and verify all normalized artifacts. Exact retries use no network;
a refresh uses a new idempotency key. Failed attempts remain inspectable.

Limits are 1 MB per response, 2 MB total, a 120-second network deadline and
45 seconds per request. The fixed public endpoint uses the existing bounded HTTP
client and does not follow redirects. No customer endpoint, map layer, climate
projection, calibrated impact model, wetland binding or station adapter is added.

## Operator commands

Use private/isolated `CRC_DATA_DIR` storage. Example request JSON:

```json
{
  "contract_version": "geographic_weather_request_v1",
  "source_id": "nasa.power_merra2_daily",
  "adapter_version": "nasa_power_daily_point_v1",
  "point": {"type": "Point", "coordinates": [-1.255, 51.745]},
  "start_date": "2024-02-01",
  "end_date": "2024-02-29",
  "time_standard": "UTC",
  "idempotency_key": "oxford-weather-feb2024-1"
}
```

```sh
python -m backend.acquisition sources --adapter-version nasa_power_daily_point_v1
python -m backend.acquisition acquire --org ORG --request weather-request.json
python -m backend.acquisition read --org ORG --id ACQUISITION_ID
python -m scripts.verify_geographic_acquisition --org ORG --id ACQUISITION_ID
```

The existing internal artifact reader exposes integrity-checked daily series.
The generic verifier dispatches to `verify_weather_acquisition`; its Python
`verify_weather(..., live=False)` mode is fully offline. Live mode separately
requests the first, middle and last dates and compares all six variables and
source metadata. These are fresh same-provider consistency checks, not independent
station validation.

## Verification and historical impact

The 37 new weather tests cover leap days, UTC/calendar validation, source identity,
units, missingness versus zero, physical bounds, changing responses, byte limits,
recent-period refusal, retries/history, tenant isolation, corrupt storage, CLI
operation and detection of different live values. All **221 affected independent
acquisition tests pass on both SQLite and PostgreSQL/PostGIS**. Python compilation
and diff checks pass. Existing dependency warnings remain; no frontend/build/browser
or deployment checks apply because those surfaces are unchanged.

Real captures for Oxford, Edinburgh, Cardiff and Belfast each contain 29 days
across six variables for February 2024: **696 present variable-day values**. All
72 fresh single-day variable comparisons pass. Fresh-process readback, provider-free
retries and original-response replay match, with no additional database rows.
These four examples do not certify complete UK geographic/temporal coverage.

Twelve earlier vector, DTM, DSM and satellite captures remain unchanged. The
isolated weather database has four acquisitions and four attempts, with zero
Sites, assessments, datasets, features, Evidence Snapshots or ModuleRuns. No
historical assessment, source identity or scientific interpretation was mutated.
Original source responses and databases stay outside Git; see the small
[acceptance record](verification/historical-weather-2026-09-15.json).

## Recommended next task

Expose acquired evidence through an authenticated, read-only catalogue searchable
by location and date, so these independent captures can be discovered by the
platform. Map presentation can consume that contract in a later task. Higher-resolution
weather and validated climate/impact modelling remain necessary for farm-scale
assessment products.
