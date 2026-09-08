"""England river and mapped land-cover adapters; unknown soil/condition stay unknown."""
from pathlib import Path
import math
import json
import sqlite3
import struct
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds, Window
from rasterio.transform import array_bounds
from pyproj import Transformer, Geod
from shapely.geometry import shape, mapping, box
from shapely.ops import transform, unary_union
from shapely import from_wkb
from backend.earth import RawSource, Observation, SpatialReference, Asset, VARIABLES, fingerprint
from backend.source_io import artifact, fetch_bytes, read_cache, save_cache, utcnow
from backend.open_rivers import fetch as fetch_rivers

ENVIRONMENT_SOURCE_VERSION = 'crc_os_worldcover_v1'
PROJECT = Transformer.from_crs(4326,27700,always_xy=True).transform
RIVER_URL = 'https://osdatahub.os.uk/downloads/open/OpenRivers'
LAND_URL = 'https://esa-worldcover.org/en/data-access'
CLASSES = {10:'woodland',20:'shrubland',30:'grassland',40:'arable',50:'developed',60:'bare_ground',70:'snow_ice',80:'water',90:'wetland',95:'mangroves',100:'moss_lichen'}
LAND_LIMITS = ('ESA WorldCover 2021 v200, annual satellite classification at nominal 10m, not present-day survey. '
               'Reference timestamp denotes the start of the 2021 annual observation period, not a point survey. '
               'Grassland does not distinguish improved, degraded or wet grassland; tree cover is not a condition or ancient-woodland assessment. '
               'Class 90 maps herbaceous wetlands only; omission does not establish absence of wetlands, wet woodland or seasonally wet grassland. '
               'Built-up pixels are a screening proxy, not building footprints or a complete infrastructure inventory.')
RIVER_LIMITS = ('OS Open Rivers is an authoritative generalized high-level network (mapping scale 1:15,000–1:30,000), '
                'not a complete inventory of small ditches or drains. Lines do not represent river width. '
                'Euclidean distance and line intersection do not establish hydraulic connection, available water or perennial flow. '
                'Publication/retrieval date is not the date of a field survey.')


def gpkg_wkb(content):
    if content[:2] != b'GP' or len(content)<8:
        raise ValueError('Invalid GeoPackage geometry header')
    flags=content[3]
    envelope=(flags>>1)&7
    sizes={0:0,1:32,2:48,3:48,4:64}
    if envelope not in sizes or flags & 16:
        raise ValueError('Empty or unsupported GeoPackage geometry')
    return from_wkb(content[8+sizes[envelope]:])


def watercourse_features(geometry, gpkg, radius=5000):
    parcel=transform(PROJECT,shape(geometry))
    west,south,east,north=parcel.buffer(radius).bounds
    with sqlite3.connect('file:'+str(gpkg)+'?mode=ro',uri=True) as c:
        tables=c.execute('select table_name,column_name,geometry_type_name,srs_id from gpkg_geometry_columns').fetchall()
        choices=[t for t in tables if t[2] in ('LINESTRING','MULTILINESTRING') and t[3]==27700]
        if len(choices)!=1:raise ValueError('Unexpected OS watercourse geometry schema')
        table,column,_,_=choices[0]
        # Identifiers originate from the downloaded SQLite schema, not user input.
        quote=lambda x:'"'+x.replace('"','""')+'"'
        info=c.execute('pragma table_info('+quote(table)+')').fetchall()
        primary=[row[1] for row in info if row[5]]
        if len(primary)!=1:raise ValueError('No unambiguous watercourse primary key')
        rtree='rtree_'+table+'_'+column
        query=f'SELECT {quote(column)} FROM {quote(table)} WHERE {quote(primary[0])} IN (SELECT id FROM {quote(rtree)} WHERE minx<=? AND maxx>=? AND miny<=? AND maxy>=?)'
        lines=[gpkg_wkb(row[0]) for row in c.execute(query,(east,west,north,south))]
    if not lines:
        return {'hydrology.distance_to_water_m':None,'hydrology.watercourse_intersection':'no',
                'hydrology.within_100m_watercourse_fraction':0},'No mapped watercourse within complete 5km search; exact nearest distance unknown.'
    network=unary_union(lines)
    distance=parcel.distance(network)
    # The exhaustive rtree envelope includes every line within radius of parcel.
    # A closest line further away cannot be established with this bounded query.
    return {'hydrology.distance_to_water_m':distance if distance<=radius else None,
            'hydrology.watercourse_intersection':'yes' if parcel.intersects(network) else 'no',
            'hydrology.within_100m_watercourse_fraction':min(1,parcel.intersection(network.buffer(100)).area/parcel.area)},None if distance<=radius else 'Nearest returned line is outside complete search radius.'


def capture_landcover(geometry, cache_dir, refresh=False):
    cache_dir=Path(cache_dir)/'landcover'
    key=fingerprint([ENVIRONMENT_SOURCE_VERSION,geometry])
    cache_file=cache_dir/(key+'.json')
    cached=read_cache(cache_file,refresh)
    if cached:return cached
    result={'status':'unavailable','retrieved_at':utcnow(),'artifacts':[],'statistics':{}}
    try:
        g=shape(geometry)
        west,south,east,north=g.bounds
        x=math.floor(west/3)*3;y=math.floor(south/3)*3
        if east>x+3 or north>y+3:raise ValueError('Parcel crosses WorldCover tile boundary; multi-tile processing not connected')
        tile=('N' if y>=0 else 'S')+f'{abs(y):02d}'+('E' if x>=0 else 'W')+f'{abs(x):03d}'
        url=f'https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif'
        # GDAL reads source COG ranges only; no resampling or overview selection.
        with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif',GDAL_HTTP_TIMEOUT='45',GDAL_HTTP_MAX_RETRY='1'):
            with rasterio.open(url) as dataset:
                if dataset.crs!=rasterio.crs.CRS.from_epsg(4326) or dataset.count!=1 or dataset.dtypes[0]!='uint8':
                    raise ValueError('Unexpected WorldCover raster schema')
                if not box(*dataset.bounds).covers(g):
                    raise ValueError('WorldCover source raster does not cover the full parcel')
                window=from_bounds(west,south,east,north,dataset.transform)
                xoff,yoff=math.floor(window.col_off),math.floor(window.row_off)
                window=Window(xoff,yoff,math.ceil(window.col_off+window.width)-xoff,math.ceil(window.row_off+window.height)-yoff)
                if window.width*window.height>10_000_000:raise ValueError('WorldCover parcel exceeds raster budget')
                pixels=dataset.read(1,window=window)
                affine=dataset.window_transform(window)
                profile=dataset.profile.copy()
                profile.update(width=pixels.shape[1],height=pixels.shape[0],transform=affine,driver='GTiff',compress='deflate',nodata=0)
                # A lossless subset retains exact native source classifications;
                # it is not claimed to be the untouched complete remote COG.
                with rasterio.io.MemoryFile() as mem:
                    with mem.open(**profile) as subset:subset.write(pixels,1)
                    raw=artifact(cache_dir,mem.read(),'.tif')
        result['artifacts'].append(raw)
        stats,coverage=landcover_statistics(pixels,affine,geometry)
        result.update(status='available',statistics=stats,coverage=coverage,source_url=url,
                      raster=raw,transform=list(affine),retrieved_at=utcnow())
    except (ValueError,OSError,RuntimeError,rasterio.errors.RasterioError) as error:
        result['missing_reason']=f'Real WorldCover unavailable: {type(error).__name__}: {str(error)[:300]}'
    return save_cache(cache_file,result)


def landcover_statistics(pixels, affine, geometry):
    if affine.b != 0 or affine.d != 0 or affine.a <= 0 or affine.e >= 0:
        raise ValueError('Expected north-up WorldCover grid')
    if not box(*array_bounds(*pixels.shape, affine)).covers(shape(geometry)):
        raise ValueError('Land-cover raster does not cover the full parcel')
    mask=geometry_mask([geometry],out_shape=pixels.shape,transform=affine,invert=True,all_touched=False)
    total=int(mask.sum())
    if total<4:raise ValueError('Fewer than four land-cover pixel centres inside parcel')
    codes=set(int(v) for v in np.unique(pixels[mask]))
    if codes-set(CLASSES)-{0}:raise ValueError('Unrecognized WorldCover class; refusing an invented mapping')
    valid=mask & (pixels!=0)
    coverage=int(valid.sum())/total
    if not valid.any():return {},0
    # Geodesic cell areas per latitude row avoid treating longitude degrees as metres.
    geod=Geod(ellps='WGS84')
    weights=np.empty((pixels.shape[0],1))
    for row in range(pixels.shape[0]):
        x,y=affine @ (0,row)
        area,_=geod.polygon_area_perimeter([x,x+affine.a,x+affine.a,x],[y,y,y+affine.e,y+affine.e])
        weights[row,0]=abs(area)
    denominator=float(np.sum(weights*valid))
    fractions={code:float(np.sum(weights*(valid & (pixels==code)))/denominator) for code in CLASSES}
    dominant=max(fractions,key=lambda code:(fractions[code],-code))
    return {'land_use.current_cover':CLASSES[dominant],
            'land_use.developed_fraction':fractions[50],
            'ecology.mapped_wetland_fraction':fractions[90],
            'hydrology.surface_water_fraction':fractions[80],
            'class_fractions':{CLASSES[code]:value for code,value in fractions.items()}},coverage


def capture_environment(geometry,cache_dir,refresh=False):
    root=Path(cache_dir)
    results={'version':ENVIRONMENT_SOURCE_VERSION,'geometry_fingerprint':fingerprint(geometry)}
    try:
        source=fetch_rivers(root/'rivers',refresh)
        statistics,reason=watercourse_features(geometry,source['gpkg'])
        results['rivers']=source|{'statistics':statistics,'missing_reason':reason}
    except (ValueError,OSError,RuntimeError,sqlite3.Error,__import__('httpx').HTTPError) as error:
        results['rivers']={'status':'unavailable','artifacts':[],'retrieved_at':utcnow(),'statistics':{},
                           'missing_reason':f'Real OS watercourse data unavailable: {type(error).__name__}: {str(error)[:300]}'}
    results['landcover']=capture_landcover(geometry,root,refresh)
    return results


def normalize_environment(snapshot,state):
    raws,candidates=[],[]
    specs=[('rivers','Ordnance Survey','OS Open Rivers',RIVER_URL,None,None,RIVER_LIMITS,
            ['hydrology.distance_to_water_m','hydrology.watercourse_intersection','hydrology.within_100m_watercourse_fraction']),
           ('landcover','European Space Agency','ESA WorldCover 2021 v200',LAND_URL,'2021-01-01T00:00:00+00:00',10,LAND_LIMITS,
            ['land_use.current_cover','land_use.developed_fraction','ecology.mapped_wetland_fraction','hydrology.surface_water_fraction'])]
    for key,publisher,name,url,timestamp,resolution,limitations,variables in specs:
        data=snapshot[key]
        group=[]
        # GeoPackage and its original archive are both retained. The bounded
        # lossless land-cover subset retains original class values and source URL.
        for record in data['artifacts']:
            rid=record['sha256']
            suffix=Path(record['path']).suffix
            media_type={'.tif':'image/tiff','.gpkg':'application/geopackage+sqlite3',
                        '.zip':'application/zip','.json':'application/json'}[suffix]
            group.append(RawSource(id=rid,source=publisher,source_dataset=name,source_version=rid,source_url=url,
                retrieved_at=data['retrieved_at'],timestamp=timestamp,storage_reference=record['path'],checksum=rid,
                assets=[Asset(href=data.get('source_url',record['path']),media_type=media_type,
                              crs='EPSG:4326' if key=='landcover' else 'EPSG:27700',spatial_resolution_m=resolution,roles=['data'])],
                raw_semantics=('Lossless native COG window, no resampling; subset SHA-256, original remote tile retained as asset URL. ' if key=='landcover' else 'Original official OS download artifact; archive/GeoPackage/metadata. ')+limitations))
        if not group:
            rid=fingerprint([key,data])
            group=[RawSource(id=rid,source=publisher,source_dataset=name+' acquisition attempt',source_version=rid,source_url=url,
                             retrieved_at=data['retrieved_at'],raw_semantics=data.get('missing_reason','No source data'))]
        raws.extend(group)
        for variable in variables:
            value=data.get('statistics',{}).get(variable)
            method=(ENVIRONMENT_SOURCE_VERSION+'; EPSG:27700 parcel-to-complete-line minimum distance; exhaustive 5km RTree envelope; 100m round buffer intersection / parcel area.' if key=='rivers' else
                    ENVIRONMENT_SOURCE_VERSION+'; WorldCover class mapping '+str(CLASSES)+'; native cell centres within parcel, geodesic row-area weights, valid classes only. No management/condition inference.')
            if key=='landcover':method+=' Full class fractions: '+json.dumps(data.get('statistics',{}).get('class_fractions',{}),sort_keys=True)
            candidates.append((100,Observation(id=fingerprint([ENVIRONMENT_SOURCE_VERSION,state.location_id,state.boundary_version,variable,[r.id for r in group],value]),
                variable=variable,value=value,unit=VARIABLES[variable][0],source=publisher,source_dataset=name,source_version=group[0].source_version,
                source_url=url,timestamp=timestamp,retrieved_at=data['retrieved_at'],
                spatial=SpatialReference(geometry_or_cell_reference=f'{state.location_id}/boundary/{state.boundary_version}',
                                         crs='EPSG:27700' if key=='rivers' else 'EPSG:4326',spatial_resolution_m=resolution,
                                         aggregation='Parcel minimum / buffer overlap' if key=='rivers' else 'Native classified-cell geodesic area fractions'),
                method=method,observed_or_derived='derived',epistemic_status='inferred' if value is not None else 'unknown',
                confidence=(.8 if key=='rivers' else .65) if value is not None else 0,
                input_coverage=data.get('coverage',1) if value is not None else 0,uncertainty=limitations,
                raw_source_ids=[r.id for r in group],missing_reason=None if value is not None else data.get('missing_reason','No valid mapped data'))))
    # Explicitly expose priority gaps rather than letting users confuse proxies
    # above with measured soil drainage, wetland condition or infrastructure.
    for variable,reason in {
        'soil.drainage_class':'No licensed, spatially appropriate soil drainage dataset connected for this parcel.',
        'ecology.wetland_fraction':'WorldCover herbaceous-wetland class is incomplete for wet grassland and wet woodland; true wetland extent remains unknown.',
        'ecology.habitat_condition':'No current ecological condition survey connected. Land-cover class cannot establish healthy or degraded wetland.',
        'human.infrastructure_fraction':'No complete mapped road, rail and infrastructure footprint dataset connected. Built-up pixels are retained separately.'}.items():
        candidates.append((10,Observation(id=fingerprint([ENVIRONMENT_SOURCE_VERSION,state.location_id,state.boundary_version,variable]),
            variable=variable,value=None,unit=VARIABLES[variable][0],source='CRC',source_dataset='Unconnected priority evidence',source_version=ENVIRONMENT_SOURCE_VERSION,
            timestamp=None,retrieved_at=state.as_of,spatial=SpatialReference(geometry_or_cell_reference=f'{state.location_id}/boundary/{state.boundary_version}'),
            method='No inference or imputation',observed_or_derived='derived',epistemic_status='unknown',confidence=0,
            uncertainty=reason,missing_reason=reason)))
    return raws,candidates
