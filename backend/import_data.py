"""Repeatable bounded authoritative reference imports. No synthetic fallback."""
import httpx,json,hashlib
from sqlalchemy import insert,text
from shapely import make_valid
from backend.core import *
from backend.flood import fetch_flood, COLLECTION_URL, LIMITATIONS as FLOOD_LIMITS, ATTRIBUTION as FLOOD_ATTR, FLOOD_BBOX
from backend.priority_habitats import (
    ATTRIBUTION as PHI_ATTRIBUTION,
    CAPTURE_END_DATE as PHI_CAPTURE_END_DATE,
    CATALOGUE_URL as PHI_CATALOGUE_URL,
    LICENCE as PHI_LICENCE,
    LIMITATIONS as PHI_LIMITATIONS,
    SERVICE_URL as PHI_SERVICE_URL,
    SOURCE_CREATION_DATE as PHI_SOURCE_CREATION_DATE,
    SOURCE_METADATA_REVISION_DATE as PHI_SOURCE_METADATA_REVISION_DATE,
    normalize_properties as normalize_phi_properties,
    validate_service_metadata as validate_phi_service_metadata,
)
from backend.openmap_local import (
    ATTRIBUTION as OML_ATTRIBUTION,
    COVERAGE_WGS84 as OML_COVERAGE,
    LICENCE as OML_LICENCE,
    LIMITATIONS as OML_LIMITATIONS,
    PRODUCT_URL as OML_PRODUCT_URL,
    SCHEMA_URL as OML_SCHEMA_URL,
    SITE_CLASSIFICATION_URL as OML_SITE_CLASSIFICATION_URL,
    SITE_THEME_URL as OML_SITE_THEME_URL,
    RAIL_STATION_CLASSIFICATION_URL as OML_RAIL_STATION_CLASSIFICATION_URL,
    RAIL_TRACK_CLASSIFICATION_URL as OML_RAIL_TRACK_CLASSIFICATION_URL,
    SOURCE_CRS as OML_SOURCE_CRS,
    SOURCE_RELEASE as OML_SOURCE_RELEASE,
    TECHNICAL_SPECIFICATION_URL as OML_TECHNICAL_SPECIFICATION_URL,
    TO_WGS84 as OML_TO_WGS84,
    acquire_archive as acquire_openmap_local,
    inspect_archive as inspect_openmap_local,
)
BASE='https://services.arcgis.com/JJzESW51TqeY9uat/arcgis/rest/services/'
SOURCES=[
 ('woodland','Ancient woodland · legacy inventory',BASE+'Ancient_Woodland_England/FeatureServer/0','Legacy inventory; revised completed-county data takes precedence. This observation is incomplete for revised counties and absence is not proof of no ancient woodland.'),
 ('woodland_revised','Ancient woodland · revised inventory',BASE+'Ancient_Woodland_Revised_England/FeatureServer/0','Only completed counties are included. An empty intersection does not establish county completion or absence of ancient woodland. Read alongside legacy inventory; never sum their overlaps.'),
 ('sssi','Sites of Special Scientific Interest',BASE+'SSSI_England/FeatureServer/0','Notified SSSIs only; excludes proposed sites and impact risk zones. A designation is neither automatic disqualification nor proof of restoration potential.'),
 ('priority_habitats','Priority Habitats Inventory (England)',PHI_SERVICE_URL,PHI_LIMITATIONS),
 ('built_world','OS OpenMap - Local built-world objects',OML_PRODUCT_URL,OML_LIMITATIONS)]
SOURCES.append(('flood','Flood Map for Planning · Zones 2 & 3 combined',COLLECTION_URL,FLOOD_LIMITS))
ATTR='© Natural England 2026. Contains Ordnance Survey data © Crown copyright and database right 2026. Open Government Licence v3. Woodland additional attribution is retained in the source metadata snapshot.'
def fetch(url):
    with httpx.Client(timeout=60,follow_redirects=True) as client:
        metadata=client.get(url,params={'f':'json'});metadata.raise_for_status();meta=metadata.json()
        if 'error' in meta:raise RuntimeError(str(meta['error']))
        params={'f':'json','where':'1=1','geometry':','.join(map(str,PILOT)),'geometryType':'esriGeometryEnvelope','inSR':4326,'spatialRel':'esriSpatialRelIntersects','returnIdsOnly':'true'}
        response=client.get(url+'/query',params=params);response.raise_for_status();ids=response.json()
        if 'error' in ids:raise RuntimeError(str(ids['error']))
        all_ids=ids.get('objectIds')
        if all_ids is None:raise RuntimeError('Source did not return an exhaustive object ID list')
        all_ids=sorted(all_ids)
        out=[]
        for start in range(0,len(all_ids),100):
            q=client.get(url+'/query',params={'f':'geojson','objectIds':','.join(map(str,all_ids[start:start+100])),'outFields':'*','outSR':4326,'returnGeometry':'true'});q.raise_for_status();data=q.json()
            if data.get('exceededTransferLimit') or 'features' not in data:raise RuntimeError('Incomplete feature response')
            out+=data['features']
        if len(out)!=len(all_ids):raise RuntimeError('Feature count mismatch; import rejected')
        out.sort(key=lambda feature:(feature.get('properties') or {}).get(meta.get('objectIdField','OBJECTID'),feature.get('id')))
        return meta,{'type':'FeatureCollection','features':out}

def normalize_reference(meta, features):
    repairs=[]
    for f in features:
        g=shape(f['geometry'])
        if g.is_empty:raise RuntimeError('Empty source geometry')
        if not box(-180,-90,180,90).covers(g):raise RuntimeError('Source geometry is not longitude/latitude')
        if not g.is_valid:
            fixed=make_valid(g)
            if fixed.geom_type=='GeometryCollection':fixed=unary_union([x for x in fixed.geoms if x.geom_type in ['Polygon','MultiPolygon']])
            if fixed.is_empty or fixed.geom_type not in ['Polygon','MultiPolygon']:raise RuntimeError('Source repair did not yield polygons')
            repairs.append({'properties':f['properties'],'reason':explain_validity(g),'method':'Shapely make_valid v1; polygonal components only','original_geometry':f['geometry']})
            f['geometry']=mapping(fixed)
    meta['crc_reference_repairs']=repairs

def run(only=None, openmap_archive=None):
    init()
    for key,name,url,limitations in SOURCES:
        if only and key not in only:continue
        publisher = ('Ordnance Survey' if key == 'built_world' else
                     'Natural England' if key=='priority_habitats' else
                     'Environment Agency' if key=='flood' else 'Natural England')
        retrieved=now();id=uid();m={'name':name,'publisher':publisher,'url':url,'bbox':FLOOD_BBOX if key=='flood' else PILOT,'limitations':limitations,'attribution':OML_ATTRIBUTION if key=='built_world' else (PHI_ATTRIBUTION if key=='priority_habitats' else (FLOOD_ATTR if key=='flood' else ATTR)),'license':'https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/','licence_text':OML_LICENCE if key=='built_world' else (PHI_LICENCE if key=='priority_habitats' else 'Open Government Licence v3.0'),'synthetic':False}
        failure_phase='acquisition'
        try:
            source_geometry_crs = 'EPSG:4326'
            if key == 'built_world':
                archive_path, catalogue = acquire_openmap_local(openmap_archive)
                failure_phase='processing'
                inspected = inspect_openmap_local(archive_path)
                raw = archive_path.read_bytes()
                data = {'features': inspected['features']}
                source = {'product': catalogue['product'], 'download': catalogue['download'],
                          'admitted_layer_schemas': inspected['schemas']}
                m.update(
                    bbox=list(OML_COVERAGE.bounds), coverage_geometry=mapping(OML_COVERAGE),
                    source_release=OML_SOURCE_RELEASE, source_crs=OML_SOURCE_CRS,
                    source_format='ESRI Shapefile', source_tile='SP',
                    source_schema=inspected['schemas'], layer_feature_counts=inspected['counts'],
                    technical_specification_url=OML_TECHNICAL_SPECIFICATION_URL,
                    schema_url=OML_SCHEMA_URL,
                    code_list_urls=[OML_SITE_CLASSIFICATION_URL, OML_SITE_THEME_URL,
                                    OML_RAIL_TRACK_CLASSIFICATION_URL,
                                    OML_RAIL_STATION_CLASSIFICATION_URL],
                    download_md5=catalogue['download']['md5'], download_bytes=len(raw),
                    import_method='Official OS Downloads API pinned SP shapefile archive; schema-validated bounded Oxford feature extraction / v1',
                    sha256=catalogue['sha256'],
                    raw_semantics='Original official OS SP tile ZIP retained byte-for-byte; admitted shapefile source coordinates remain EPSG:27700.',
                    raw_object_key=f'reference/{id}/source.zip',
                )
                source_geometry_crs = OML_SOURCE_CRS
            elif key=='flood':
                source,data=fetch_flood(FLOOD_BBOX)
                m.update(zone_counts=source['crc_zone_counts'],download_bytes=source['crc_download_bytes'],catalog_url=source['crc_catalog_url'],import_method='EA OGC Features bounded pagination / CRS84 / v1')
            else:source,data=fetch(url)
            if key=='priority_habitats':
                schema=validate_phi_service_metadata(source)
                normalized_properties=[normalize_phi_properties(feature.get('properties') or {}) for feature in data['features']]
                releases=sorted({properties['source_release'] for properties in normalized_properties})
                if len(releases)!=1:raise RuntimeError('PHI import contains no release or mixed publication versions')
                m.update(source_release=releases[0],
                         source_metadata_revision_date=PHI_SOURCE_METADATA_REVISION_DATE,
                         source_capture_end_date=PHI_CAPTURE_END_DATE,
                         source_creation_date=PHI_SOURCE_CREATION_DATE,
                         catalogue_url=PHI_CATALOGUE_URL,source_schema=schema,
                         import_method='Natural England ArcGIS exhaustive object-ID query and batches of 100 / outSR EPSG:4326 / v1')
            if key != 'built_world':
                # Serialize the original assembled source BEFORE any geometry repair.
                # Source attributes/classifications are retained without translation.
                raw=json.dumps(data)
                normalize_reference(source,data['features'])
                m.update(count=len(data['features']),source_last_edit=source.get('editingInfo'),copyright=source.get('copyrightText'),reference_repairs=len(source.get('crc_reference_repairs',[])))
                if m['reference_repairs']:m['limitations']+=' '+str(m['reference_repairs'])+' invalid source polygons were normalized using Shapely make_valid (polygonal components); original geometries and reasons retained in the metadata snapshot. User boundaries are never repaired.'
                m['sha256']=hashlib.sha256(raw.encode()).hexdigest()
                m['raw_semantics']='Assembled original provider features and attributes before geometry repair; paginated responses combined, not original HTTP bytes.'
                m['raw_object_key']=f'reference/{id}/source.json'
                store_object_immutable(m['raw_object_key'],raw)
                store_object_immutable(f'reference/{id}/normalized-geometry.json',json.dumps(data))
            else:
                m.update(count=len(data['features']), source_last_edit=None, copyright=OML_ATTRIBUTION,
                         reference_repairs=0)
                store_object_immutable(m['raw_object_key'], raw, 'application/zip')
            store_object_immutable(f'reference/{id}/metadata.json',json.dumps(source))
            failure_phase='persistence'
            with engine.begin() as c:
                c.execute(insert(datasets).values(id=id,key=key,state='available',retrieved=retrieved,metadata=m))
                for f in data['features']:
                    g=shape(f['geometry'])
                    indexed_geometry = transform(OML_TO_WGS84, g) if source_geometry_crs == OML_SOURCE_CRS else g
                    a,b,d,e=indexed_geometry.bounds;fid=uid()
                    c.execute(insert(features).values(id=fid,dataset_id=id,geometry=f['geometry'],properties=f.get('properties'),minx=a,miny=b,maxx=d,maxy=e))
                    if engine.dialect.name=='postgresql':c.execute(text('UPDATE features SET geom=ST_SetSRID(ST_GeomFromGeoJSON(:g),4326) WHERE id=:id'),{'g':json.dumps(mapping(indexed_geometry)),'id':fid})
            print(key,'available',m['count'])
        except Exception as e:
            m['error']=str(e)[:500]
            m['failure_type']=(
                'acquisition_failure' if failure_phase=='acquisition' else 'processing_failure'
            )
            with engine.begin() as c:c.execute(insert(datasets).values(id=id,key=key,state='unavailable',retrieved=retrieved,metadata=m))
            print(key,'unavailable',m['error'])

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Import bounded authoritative CRC reference datasets.')
    parser.add_argument('--only',nargs='+',choices=[s[0] for s in SOURCES])
    parser.add_argument('--openmap-archive', help='Verified local copy of the pinned official SP ZIP')
    args=parser.parse_args()
    run(args.only, openmap_archive=args.openmap_archive)
