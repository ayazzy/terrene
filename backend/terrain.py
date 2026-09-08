"""EA native 1m DTM acquisition and parcel Horn-slope processing. No fabricated DEM."""
import math
from pathlib import Path
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from pyproj import Transformer
from shapely.geometry import shape, mapping
from shapely.ops import transform
from backend.earth import RawSource, Observation, SpatialReference, Asset, VARIABLES, fingerprint
from backend.source_io import artifact, fetch_bytes, read_cache, save_cache, utcnow

TERRAIN_VERSION = 'crc_ea_dtm_horn_v1'
SERVICE = 'https://environment.data.gov.uk/spatialdata/lidar-composite-digital-terrain-model-dtm-1m/wcs'
COVERAGE = '13787b9a-26a4-4775-8523-806d13af58fc__Lidar_Composite_Elevation_DTM_1m'
CATALOG = 'https://www.data.gov.uk/dataset/01b3ee39-da3f-47b6-83da-dc98e73a461f/lidar-composite-digital-terrain-model-dtm-1m'
PROJECT = Transformer.from_crs(4326, 27700, always_xy=True).transform
STATS = ['terrain.elevation_m','terrain.elevation_min_m','terrain.elevation_max_m',
         'terrain.elevation_std_m','terrain.slope_deg','terrain.slope_p90_deg','terrain.slope_max_deg']
STATISTIC_NAMES = {
    'terrain.elevation_m': 'arithmetic mean elevation',
    'terrain.elevation_min_m': 'minimum elevation',
    'terrain.elevation_max_m': 'maximum elevation',
    'terrain.elevation_std_m': 'population standard deviation of elevation',
    'terrain.slope_deg': 'arithmetic mean slope',
    'terrain.slope_p90_deg': '90th percentile slope with linear interpolation',
    'terrain.slope_max_deg': 'maximum slope',
}
MAX_CELLS = 25_000_000
LIMITATIONS = ('EA composite DTM: metres above Ordnance Datum Newlyn, native 1m grid; original surveys span multiple years. '
               'Local survey date unknown. Not a contemporary surface survey. Bare-earth filtering, water surfaces, bridges, '
               'ditches, embankments and vertical noise affect slope. No groundwater, water supply or hydraulic connectivity inferred. '
               'The WCS DescribeCoverage radiance unit tag is erroneous; elevation units come from the authoritative EA catalogue. '
               'Source confidence is a provisional data-quality judgement, not validated predictive accuracy or a probability of correctness.')


def horn_slope(z, resolution_x, resolution_y):
    if resolution_x <= 0 or resolution_y <= 0:
        raise ValueError('Horizontal grid spacing must be positive metres')
    z = np.asarray(z, dtype=float)
    out = np.full(z.shape, np.nan)
    if min(z.shape) < 3:
        return out
    a,b,c = z[:-2,:-2],z[:-2,1:-1],z[:-2,2:]
    d,e,f = z[1:-1,:-2],z[1:-1,1:-1],z[1:-1,2:]
    g,h,i = z[2:,:-2],z[2:,1:-1],z[2:,2:]
    dx = ((c+2*f+i)-(a+2*d+g))/(8*resolution_x)
    dy = ((g+2*h+i)-(a+2*b+c))/(8*resolution_y)
    valid = np.isfinite(a+b+c+d+e+f+g+h+i)
    out[1:-1,1:-1] = np.where(valid, np.degrees(np.arctan(np.hypot(dx,dy))), np.nan)
    return out


def process_dem(path, geometry):
    parcel = transform(PROJECT, shape(geometry))
    if parcel.geom_type not in ('Polygon', 'MultiPolygon') or parcel.is_empty or not parcel.is_valid:
        raise ValueError('Terrain processing requires a valid, nonempty parcel polygon')
    with rasterio.open(path) as dataset:
        if dataset.crs != rasterio.crs.CRS.from_epsg(27700) or dataset.count != 1:
            raise ValueError('DEM must be a single-band EPSG:27700 elevation grid')
        affine = dataset.transform
        if affine.b != 0 or affine.d != 0 or affine.a <= 0 or affine.e >= 0:
            raise ValueError('Expected north-up rectilinear DEM')
        rx, ry = dataset.res
        if not (math.isclose(rx,1,abs_tol=1e-8) and math.isclose(ry,1,abs_tol=1e-8)):
            raise ValueError('EA source returned resampled data instead of its native 1m grid')
        if dataset.width*dataset.height > MAX_CELLS:
            raise ValueError('DEM exceeds parcel processing budget')
        west, south, east, north = parcel.bounds
        raster_bounds = dataset.bounds
        # Otherwise a clipped/off-target WCS response silently changes the coverage
        # denominator to only the piece inside the raster and can claim 100% coverage.
        # Require one native cell beyond every parcel side for the full Horn stencil.
        tolerance = 1e-7
        if (raster_bounds.left > west - rx + tolerance or
                raster_bounds.bottom > south - ry + tolerance or
                raster_bounds.right < east + rx - tolerance or
                raster_bounds.top < north + ry - tolerance):
            raise ValueError('DEM does not cover the full parcel and one-cell slope halo')
        z = dataset.read(1, masked=True).astype('float64').filled(np.nan)
        z[~np.isfinite(z)] = np.nan
        if np.any(np.isfinite(z) & ((z < -500) | (z > 9000))):
            raise ValueError('DEM values outside elevation bounds; check nodata and vertical units')
        inside = geometry_mask([mapping(parcel)], out_shape=z.shape, transform=affine, invert=True, all_touched=False)
        total = int(inside.sum())
        if total < 4:
            raise ValueError('Fewer than four native DEM cell centres inside parcel')
        slope = horn_slope(z, rx, ry)
        elevation_values = z[inside & np.isfinite(z)]
        slope_values = slope[inside & np.isfinite(slope)]
        stats = dict.fromkeys(STATS)
        if elevation_values.size:
            stats.update({'terrain.elevation_m':float(elevation_values.mean()),
                          'terrain.elevation_min_m':float(elevation_values.min()),
                          'terrain.elevation_max_m':float(elevation_values.max()),
                          'terrain.elevation_std_m':float(elevation_values.std())})
        if slope_values.size:
            stats.update({'terrain.slope_deg':float(slope_values.mean()),
                          'terrain.slope_p90_deg':float(np.percentile(slope_values,90)),
                          'terrain.slope_max_deg':float(slope_values.max())})
        return {'statistics':stats, 'elevation_coverage':len(elevation_values)/total,
                'slope_coverage':len(slope_values)/total, 'parcel_cells':total,
                'resolution_m':rx, 'transform':list(affine), 'shape':list(z.shape)}


def fetch_terrain(geometry, cache_dir, refresh=False):
    cache_dir = Path(cache_dir)/'terrain'
    cache_key = fingerprint([TERRAIN_VERSION,geometry])
    cache_file = cache_dir/(cache_key+'.json')
    cached = read_cache(cache_file, refresh)
    if cached:
        return cached
    result = {'version':TERRAIN_VERSION,'retrieved_at':utcnow(),'status':'unavailable',
              'geometry_fingerprint':fingerprint(geometry),'artifacts':[], 'statistics':dict.fromkeys(STATS)}
    try:
        bounds = transform(PROJECT, shape(geometry)).bounds
        west,south,east,north = (math.floor(bounds[0])-3,math.floor(bounds[1])-3,
                                math.ceil(bounds[2])+3,math.ceil(bounds[3])+3)
        if (east-west)*(north-south) > MAX_CELLS:
            raise ValueError('Parcel bounding box exceeds 25 million native DEM cells; split the assessment area')
        meta, mh = fetch_bytes(SERVICE, {'service':'WCS','version':'2.0.1','request':'DescribeCoverage','coverageId':COVERAGE},max_bytes=2_000_000)
        if b'Elevation' not in meta or b'<gml:offsetVector' not in meta:
            raise ValueError('Unexpected EA elevation coverage metadata')
        metadata = artifact(cache_dir, meta, '.xml')
        result['artifacts'].append(metadata)
        params = [('service','WCS'),('version','2.0.1'),('request','GetCoverage'),('coverageId',COVERAGE),
                  ('format','image/tiff'),('subset',f'E({west},{east})'),('subset',f'N({south},{north})')]
        content, headers = fetch_bytes(SERVICE, params, max_bytes=128*1024*1024)
        if content[:4] not in (b'II*\x00', b'MM\x00*', b'II+\x00', b'MM\x00+'):
            raise ValueError('EA did not return a GeoTIFF elevation coverage')
        dem = artifact(cache_dir, content, '.tif')
        result['artifacts'].append(dem)
        result.update(process_dem(dem['path'], geometry))
        result.update(status='available',dem=dem,metadata=metadata,request=headers,
                      retrieved_at=headers['retrieved_at'],requested_bounds_27700=[west,south,east,north])
    except (ValueError, OSError, RuntimeError, rasterio.errors.RasterioError, __import__('httpx').HTTPError) as error:
        result['missing_reason'] = f'Real EA DTM unavailable: {type(error).__name__}: {str(error)[:350]}'
    return save_cache(cache_file,result)


def terrain_observations(snapshot, state):
    raw = []
    for record in snapshot['artifacts']:
        is_dem = record['path'].endswith('.tif')
        raw.append(RawSource(id=record['sha256'],source='Environment Agency',
            source_dataset='LIDAR Composite Digital Terrain Model (DTM) - 1m' if is_dem else 'EA DTM WCS coverage definition',
            source_version=record['sha256'],source_url=CATALOG,retrieved_at=snapshot['retrieved_at'],timestamp=None,
            storage_reference=record['path'],checksum=record['sha256'],
            assets=[Asset(href=snapshot.get('request',{}).get('url',SERVICE),media_type='image/tiff',roles=['elevation'],crs='EPSG:27700',spatial_resolution_m=1)] if is_dem else [],
            raw_semantics='Original bounded WCS response bytes; not hillshade. '+LIMITATIONS))
    if not raw:
        rid=fingerprint(['ea-dtm-failure',snapshot])
        raw=[RawSource(id=rid,source='Environment Agency',source_dataset='EA DTM acquisition attempt',source_version=rid,
                       source_url=CATALOG,retrieved_at=snapshot['retrieved_at'],raw_semantics=snapshot.get('missing_reason','No data'))]
    candidates=[]
    for variable in STATS:
        value=snapshot.get('statistics',{}).get(variable)
        slope='slope' in variable
        coverage=snapshot.get('slope_coverage' if slope else 'elevation_coverage',0)
        method=(TERRAIN_VERSION+'; '+('Horn 3x3: dz/dx=((c+2f+i)-(a+2d+g))/(8 dx); dz/dy=((g+2h+i)-(a+2b+c))/(8 dy); slope=atan(hypot(dz/dx,dz/dy)) in degrees. ' if slope else 'Elevation cell-centre statistics in metres above ODN. ')+
                'Pixel centres within exact parcel including holes; 3m requested external halo, '
                'complete one-cell slope halo verified, no gap filling; statistic: '+STATISTIC_NAMES[variable]+'.')
        candidates.append((100,Observation(id=fingerprint([TERRAIN_VERSION,state.location_id,state.boundary_version,variable,[r.id for r in raw],value]),
            variable=variable,value=value,unit=VARIABLES[variable][0],source='Environment Agency',source_dataset='EA LIDAR Composite DTM 1m',
            source_version=snapshot.get('dem',{}).get('sha256',raw[0].id),source_url=CATALOG,timestamp=None,retrieved_at=snapshot['retrieved_at'],
            spatial=SpatialReference(geometry_or_cell_reference=f'{state.location_id}/boundary/{state.boundary_version}',crs='EPSG:27700',spatial_resolution_m=1,
                                     aggregation='Equal-area native cell centres within parcel; valid cells only'),
            method=method,observed_or_derived='derived',epistemic_status='inferred' if value is not None else 'unknown',
            confidence=.85 if value is not None else 0,input_coverage=coverage,
            uncertainty=LIMITATIONS+f' Valid-cell coverage: {coverage:.6%}.',raw_source_ids=[r.id for r in raw],
            missing_reason=None if value is not None else snapshot.get('missing_reason','No valid DEM neighbourhoods inside parcel'))))
    return raw,candidates
