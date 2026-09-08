"""CRC Earth Schema 0.1: semantic observations, native assets and traceable state.

No database, provider imports or spatial resampling belong in this module.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = 'crc_earth_v0_1'
DOMAINS = ('terrain', 'soil', 'hydrology', 'climate', 'vegetation', 'ecology',
           'land_use', 'human', 'regulatory', 'economic')

# unit, lower bound, upper bound. Add a concept here before writing an adapter.
VARIABLES = {
    'terrain.elevation_m': ('m', -500, 9000),
    'terrain.slope_deg': ('degree', 0, 90),
    'terrain.aspect_deg': ('degree', 0, 360),
    'terrain.elevation_min_m': ('m', -500, 9000),
    'terrain.elevation_max_m': ('m', -500, 9000),
    'terrain.elevation_std_m': ('m', 0, None),
    'terrain.slope_p90_deg': ('degree', 0, 90),
    'terrain.slope_max_deg': ('degree', 0, 90),
    'soil.clay_fraction': ('fraction', 0, 1),
    'soil.permeability': ('normalized_index', 0, 1),
    'soil.drainage_class': ('category', None, None),
    'soil.retention_index': ('normalized_index', 0, 1),
    'hydrology.flow_accumulation': ('m2', 0, None),
    'hydrology.distance_to_water_m': ('m', 0, None),
    'hydrology.floodplain_probability': ('probability', 0, 1),
    'hydrology.mapped_flood_extent_fraction': ('fraction', 0, 1),
    'hydrology.groundwater_depth_m': ('m', None, None),
    'hydrology.surface_water_fraction': ('fraction', 0, 1),
    'hydrology.watercourse_intersection': ('category', None, None),
    'hydrology.within_100m_watercourse_fraction': ('fraction', 0, 1),
    'ecology.mapped_wetland_fraction': ('fraction', 0, 1),
    'climate.annual_precipitation_mm': ('mm/year', 0, None),
    'vegetation.ndvi': ('normalized_index', -1, 1),
    'ecology.habitat_type': ('category', None, None),
    'ecology.habitat_condition': ('normalized_index', 0, 1),
    'ecology.wetland_fraction': ('fraction', 0, 1),
    'ecology.irreplaceable_habitat_fraction': ('fraction', 0, 1),
    'ecology.distance_to_habitat_m': ('m', 0, None),
    'land_use.current_cover': ('category', None, None),
    'land_use.developed_fraction': ('fraction', 0, 1),
    'land_use.agricultural_quality': ('category', None, None),
    'human.infrastructure_fraction': ('fraction', 0, 1),
    'regulatory.protected_area_fraction': ('fraction', 0, 1),
    'economic.intervention_cost_per_ha': ('GBP/ha', 0, None),
    # CRC-generated indices. They are deliberately not called physical measurements.
    'hydrology.water_context_index': ('normalized_index', 0, 1),
    'ecology.restoration_need_index': ('normalized_index', 0, 1),
    'ecology.habitat_proximity_index': ('normalized_index', 0, 1),
    'human.unblocked_area_index': ('normalized_index', 0, 1),
}


class Record(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class SpatialReference(Record):
    geometry_or_cell_reference: str
    crs: str = 'EPSG:4326'
    spatial_resolution_m: float | None = Field(default=None, gt=0)
    support: Literal['parcel', 'cell', 'feature', 'asset'] = 'parcel'
    aggregation: str | None = None


class Asset(Record):
    """Native raster/vector reference; no compulsory grid or flattened pixels.

    stac_item_href can reference a STAC Item; this envelope is not itself STAC.
    """
    href: str
    media_type: str
    roles: list[str] = Field(default_factory=list)
    crs: str
    spatial_resolution_m: float | None = Field(default=None, gt=0)
    stac_item_href: str | None = None


class RawSource(Record):
    id: str
    source: str
    source_dataset: str
    source_version: str
    source_url: str
    retrieved_at: datetime
    timestamp: datetime | None = None
    storage_reference: str | None = None
    checksum: str | None = None
    assets: list[Asset] = Field(default_factory=list)
    raw_semantics: str
    synthetic: bool = False


class Observation(Record):
    id: str
    variable: str
    value: float | str | None
    unit: str
    source: str
    source_dataset: str
    source_version: str
    source_url: str | None = None
    timestamp: datetime | None
    retrieved_at: datetime
    spatial: SpatialReference
    method: str
    observed_or_derived: Literal['observed', 'derived']
    epistemic_status: Literal['observed', 'inferred', 'modelled', 'unknown']
    confidence: float = Field(ge=0, le=1)
    uncertainty: str
    raw_source_ids: list[str] = Field(default_factory=list)
    input_ids: list[str] = Field(default_factory=list)
    input_coverage: float = Field(default=1, ge=0, le=1)
    missing_input_variables: list[str] = Field(default_factory=list)
    missing_reason: str | None = None
    synthetic: bool = False

    @model_validator(mode='after')
    def canonical(self):
        if self.variable not in VARIABLES:
            raise ValueError('Register the canonical variable: ' + self.variable)
        unit, low, high = VARIABLES[self.variable]
        if unit != self.unit:
            raise ValueError(f'{self.variable} requires {unit}, received {self.unit}')
        if self.value is None:
            if not self.missing_reason or self.confidence != 0 or self.epistemic_status != 'unknown':
                raise ValueError('Unknown values require a reason, zero confidence and unknown status')
            self.input_coverage = 0
        elif unit == 'category':
            if not isinstance(self.value, str):
                raise ValueError('Category must be a string')
        elif isinstance(self.value, str) or not math.isfinite(self.value):
            raise ValueError('Numeric variables require a finite number')
        elif (low is not None and self.value < low) or (high is not None and self.value > high):
            raise ValueError('Value outside canonical bounds: ' + self.variable)
        return self


class EarthState(Record):
    schema_version: str = SCHEMA_VERSION
    location_id: str
    boundary_version: int
    geography: str
    as_of: datetime
    geometry: dict
    raw: list[RawSource] = Field(default_factory=list)
    # Keep all competing observations, grouped by semantic domain.
    normalized: dict[str, dict[str, list[Observation]]] = Field(default_factory=dict)
    selected: dict[str, str] = Field(default_factory=dict)
    selection_notes: dict[str, str] = Field(default_factory=dict)
    derived: dict[str, Observation] = Field(default_factory=dict)

    def get(self, variable: str) -> Observation | None:
        if variable in self.derived:
            return self.derived[variable]
        domain, name = variable.split('.', 1)
        return next((o for o in self.normalized.get(domain, {}).get(name, [])
                     if o.id == self.selected.get(variable)), None)

    def observations(self) -> list[Observation]:
        return [o for domain in self.normalized.values() for group in domain.values() for o in group] + list(self.derived.values())


def fingerprint(value) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def normalize_unit(value, source_unit: str, variable: str):
    """Only dimensionally justified conversions. Never turn zones into probabilities."""
    target = VARIABLES[variable][0]
    if value is None or source_unit == target:
        return value
    factors = {('%', 'fraction'): .01, ('%', 'probability'): .01,
               ('km', 'm'): 1000, ('cm', 'm'): .01, ('ha', 'm2'): 10000,
               ('m/year', 'mm/year'): 1000, ('radian', 'degree'): 180 / math.pi}
    if (source_unit, target) not in factors:
        raise ValueError(f'No justified conversion from {source_unit} to {target}')
    return value * factors[(source_unit, target)]


class Intervention(Record):
    type: str
    location_id: str
    area_ha: float = Field(gt=0)
    parameters: dict = Field(default_factory=dict)


class ScenarioRequest(Record):
    """Future interface only. Wetland v0.1 does not predict a future state."""
    baseline_state: EarthState
    intervention: Intervention | None = None
    horizon_years: int = Field(gt=0)
