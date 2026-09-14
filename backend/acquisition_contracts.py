"""Versioned geographic requests; independent of Sites and analytical models."""
from hashlib import sha256
from dataclasses import dataclass
import json
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pyproj import Geod
from shapely.geometry import shape, mapping
from shapely.geometry.polygon import orient

SOURCE_ID = 'natural_england.sssi'
ADAPTER_VERSION = 'sssi_arcgis_v1'
FULL_EXTENT_ADAPTER_VERSION = 'sssi_arcgis_v2'
SCOTLAND_SOURCE_ID = 'naturescot.sssi'
SCOTLAND_ADAPTER_VERSION = 'naturescot_sssi_arcgis_v1'
DTM_SOURCE_ID = 'environment_agency.lidar_dtm_1m'
DTM_ADAPTER_VERSION = 'ea_lidar_dtm_wcs_v1'
SOURCE_ADAPTERS = {
    SOURCE_ID: (ADAPTER_VERSION, FULL_EXTENT_ADAPTER_VERSION),
    SCOTLAND_SOURCE_ID: (SCOTLAND_ADAPTER_VERSION,),
    DTM_SOURCE_ID: (DTM_ADAPTER_VERSION,),
}
MAX_AREA_HA = 100_000
MAX_COORDINATES = 10_000
MAX_REQUEST_BYTES = 500_000


class AcquisitionError(RuntimeError):
    """Only stable, non-sensitive codes cross the service boundary."""
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class BinaryArtifact:
    """Original decoded HTTP bytes; never serialize rasters or XML as JSON."""
    content: bytes
    media_type: Literal['image/tiff', 'application/xml']


def encode(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value: bytes) -> str:
    return sha256(value).hexdigest()


def validate_area(value: dict) -> dict:
    """Global WGS84 geometry contract, including all UK nations and islands.

    A coordinate envelope is never evidence of administrative/source coverage.
    Geodesic area avoids assuming a national projected CRS for UK-wide requests.
    """
    try:
        if len(encode(value)) > MAX_REQUEST_BYTES:
            raise ValueError('area_payload_limit')
        if set(value) != {'type', 'coordinates'} or value['type'] not in ('Polygon', 'MultiPolygon'):
            raise ValueError('area_requires_wgs84_polygon')
        polygons = [value['coordinates']] if value['type'] == 'Polygon' else value['coordinates']
        count = 0
        if not polygons:
            raise ValueError('empty_area')
        for polygon in polygons:
            if not polygon:
                raise ValueError('empty_polygon')
            for ring in polygon:
                if len(ring) < 4 or ring[0] != ring[-1]:
                    raise ValueError('unclosed_ring')
                for point in ring:
                    count += 1
                    if (len(point) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in point)
                            or not -180 <= point[0] <= 180 or not -90 <= point[1] <= 90):
                        raise ValueError('invalid_wgs84_position')
        if count > MAX_COORDINATES:
            raise ValueError('coordinate_limit')
        geometry = shape(value)
        if geometry.is_empty or not geometry.is_valid:
            raise ValueError('invalid_area_topology')
        # A small geodesic polygon crossing the date line is ambiguous in planar GeoJSON.
        if geometry.bounds[2] - geometry.bounds[0] > 180:
            raise ValueError('antimeridian_unsupported')
        parts = [geometry] if geometry.geom_type == 'Polygon' else geometry.geoms
        geod = Geod(ellps='WGS84')
        area = sum(abs(geod.geometry_area_perimeter(orient(p, sign=1))[0]) for p in parts) / 10_000
        if not 0 < area <= MAX_AREA_HA:
            raise ValueError('area_limit')
        # Normalize ordering/orientation only; never repair or round user coordinates.
        return json.loads(encode(mapping(geometry.normalize())))
    except (TypeError, KeyError, IndexError) as exc:
        raise ValueError('malformed_area') from exc


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)


class TemporalSelection(Contract):
    mode: Literal['current_publication', 'interval']
    start: str | None = None
    end: str | None = None

    @model_validator(mode='after')
    def explicit_time(self):
        if self.mode == 'current_publication' and (self.start is not None or self.end is not None):
            raise ValueError('current_publication_has_no_interval')
        if self.mode == 'interval' and (not self.start or not self.end):
            raise ValueError('interval_requires_start_and_end')
        return self


class AcquisitionRequest(Contract):
    contract_version: Literal['geographic_acquisition_request_v1']
    source_id: Literal['natural_england.sssi', 'naturescot.sssi', 'environment_agency.lidar_dtm_1m']
    adapter_version: Literal['sssi_arcgis_v1', 'sssi_arcgis_v2', 'naturescot_sssi_arcgis_v1', 'ea_lidar_dtm_wcs_v1']
    coverage_profile_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    area: dict
    temporal: TemporalSelection
    idempotency_key: str = Field(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9_.:-]+$')

    @model_validator(mode='after')
    def valid_geometry(self):
        if self.adapter_version not in SOURCE_ADAPTERS[self.source_id]:
            raise ValueError('source_adapter_mismatch')
        if len(encode(self.model_dump())) > MAX_REQUEST_BYTES:
            raise ValueError('request_payload_limit')
        object.__setattr__(self, 'area', validate_area(self.area))
        return self

    @property
    def geometry_fingerprint(self) -> str:
        return digest(encode(self.area))
