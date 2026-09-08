"""Repeatable bounded authoritative ArcGIS import. No synthetic fallback."""
import httpx,json,hashlib
from sqlalchemy import insert,text
from shapely import make_valid
from backend.core import *
from backend.flood import fetch_flood, COLLECTION_URL, LIMITATIONS as FLOOD_LIMITS, ATTRIBUTION as FLOOD_ATTR, FLOOD_BBOX
BASE='https://services.arcgis.com/JJzESW51TqeY9uat/arcgis/rest/services/'
SOURCES=[
 ('woodland','Ancient woodland · legacy inventory',BASE+'Ancient_Woodland_England/FeatureServer/0','Legacy inventory; revised completed-county data takes precedence. This observation is incomplete for revised counties and absence is not proof of no ancient woodland.'),
 ('woodland_revised','Ancient woodland · revised inventory',BASE+'Ancient_Woodland_Revised_England/FeatureServer/0','Only completed counties are included. An empty intersection does not establish county completion or absence of ancient woodland. Read alongside legacy inventory; never sum their overlaps.'),
 ('sssi','Sites of Special Scientific Interest',BASE+'SSSI_England/FeatureServer/0','Notified SSSIs only; excludes proposed sites and impact risk zones. A designation is neither automatic disqualification nor proof of restoration potential.')]
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
        out=[]
        for start in range(0,len(all_ids),100):
            q=client.get(url+'/query',params={'f':'geojson','objectIds':','.join(map(str,all_ids[start:start+100])),'outFields':'*','outSR':4326,'returnGeometry':'true'});q.raise_for_status();data=q.json()
            if data.get('exceededTransferLimit') or 'features' not in data:raise RuntimeError('Incomplete feature response')
            out+=data['features']
        if len(out)!=len(all_ids):raise RuntimeError('Feature count mismatch; import rejected')
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

def run(only=None):
    init()
    for key,name,url,limitations in SOURCES:
        if only and key not in only:continue
        retrieved=now();id=uid();m={'name':name,'url':url,'bbox':FLOOD_BBOX if key=='flood' else PILOT,'limitations':limitations,'attribution':FLOOD_ATTR if key=='flood' else ATTR,'license':'https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/','synthetic':False}
        try:
            if key=='flood':
                source,data=fetch_flood(FLOOD_BBOX)
                m.update(zone_counts=source['crc_zone_counts'],download_bytes=source['crc_download_bytes'],catalog_url=source['crc_catalog_url'],import_method='EA OGC Features bounded pagination / CRS84 / v1')
            else:source,data=fetch(url)
            # Serialize the original assembled source BEFORE any geometry repair.
            # Source attributes/classifications are retained without translation.
            raw=json.dumps(data)
            normalize_reference(source,data['features'])
            m.update(count=len(data['features']),source_last_edit=source.get('editingInfo'),copyright=source.get('copyrightText'),reference_repairs=len(source.get('crc_reference_repairs',[])))
            if m['reference_repairs']:m['limitations']+=' '+str(m['reference_repairs'])+' invalid source polygons were normalized using Shapely make_valid (polygonal components); original geometries and reasons retained in the metadata snapshot. User boundaries are never repaired.'
            m['sha256']=hashlib.sha256(raw.encode()).hexdigest()
            m['raw_semantics']='Assembled original provider features and attributes before geometry repair; paginated responses combined, not original HTTP bytes.'
            store_object(f'reference/{id}/source.json',raw);store_object(f'reference/{id}/metadata.json',json.dumps(source))
            store_object(f'reference/{id}/normalized-geometry.json',json.dumps(data))
            with engine.begin() as c:
                c.execute(insert(datasets).values(id=id,key=key,state='available',retrieved=retrieved,metadata=m))
                for f in data['features']:
                    g=shape(f['geometry']);a,b,d,e=g.bounds;fid=uid()
                    c.execute(insert(features).values(id=fid,dataset_id=id,geometry=f['geometry'],minx=a,miny=b,maxx=d,maxy=e))
                    if engine.dialect.name=='postgresql':c.execute(text('UPDATE features SET geom=ST_SetSRID(ST_GeomFromGeoJSON(:g),4326) WHERE id=:id'),{'g':json.dumps(f['geometry']),'id':fid})
            print(key,'available',m['count'])
        except Exception as e:
            m['error']=str(e)[:500]
            with engine.begin() as c:c.execute(insert(datasets).values(id=id,key=key,state='unavailable',retrieved=retrieved,metadata=m))
            print(key,'unavailable',m['error'])

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Import bounded authoritative CRC reference datasets.')
    parser.add_argument('--only',nargs='+',choices=[s[0] for s in SOURCES])
    run(parser.parse_args().only)
