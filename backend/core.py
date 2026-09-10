"""Shared database, geometry and immutable evidence model."""
import os, json, uuid, time
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import (
    create_engine, MetaData, Table, Column, String, Integer, Float, JSON, Text,
    Index, UniqueConstraint, select, text, inspect,
)
from shapely.geometry import shape, mapping, box
from shapely.ops import transform, unary_union
from shapely.validation import explain_validity
from pyproj import Transformer

ROOT = Path(os.getenv('CRC_DATA_DIR','data')); ROOT.mkdir(exist_ok=True,parents=True)
DATABASE_URL=os.getenv('DATABASE_URL',f'sqlite:///{ROOT}/crc.db')
engine=create_engine(DATABASE_URL, connect_args={'check_same_thread':False,'timeout':30} if DATABASE_URL.startswith('sqlite') else {},pool_pre_ping=True)
meta=MetaData()
sites=Table('sites',meta,Column('id',String,primary_key=True),Column('org',String,index=True,nullable=False),Column('name',String),Column('notes',Text),Column('status',String),Column('version',Integer),Column('geometry',JSON),Column('created',String))
assessments=Table('assessments',meta,Column('id',String,primary_key=True),Column('org',String,index=True),Column('site_id',String,index=True),Column('version',Integer),Column('geometry',JSON),Column('site_name',String),Column('state',String),Column('attempts',Integer),Column('lease',Float),Column('token',String),Column('error',Text),Column('result',JSON),Column('created',String),Column('dataset_ids',JSON),Column('dedupe',String,unique=True),Column('model_spec',JSON))
datasets=Table('datasets',meta,Column('id',String,primary_key=True),Column('key',String,index=True),Column('state',String),Column('retrieved',String),Column('metadata',JSON))
features=Table('features',meta,Column('id',String,primary_key=True),Column('dataset_id',String,index=True),Column('geometry',JSON),Column('properties',JSON),Column('minx',Float),Column('miny',Float),Column('maxx',Float),Column('maxy',Float))
Index('feature_bounds',features.c.dataset_id,features.c.minx,features.c.maxx,features.c.miny,features.c.maxy)
land_evidence_snapshots=Table(
    'land_evidence_snapshots',meta,
    Column('id',String,primary_key=True),Column('org',String,index=True,nullable=False),
    Column('site_id',String,index=True,nullable=False),Column('boundary_version',Integer,nullable=False),
    Column('boundary_geometry_fingerprint',String,nullable=False),
    Column('schema_version',String,nullable=False),Column('registry_version',String,nullable=False),
    Column('content_hash',String,nullable=False),Column('manifest_sha256',String,nullable=False),
    Column('manifest_key',Text,nullable=False),Column('created',String,nullable=False),
    UniqueConstraint('org','site_id','boundary_version','schema_version','content_hash',
                     name='uq_land_evidence_snapshot_content'),
)
land_evidence_snapshot_members=Table(
    'land_evidence_snapshot_members',meta,
    Column('snapshot_id',String,primary_key=True),Column('kind',String,primary_key=True),
    Column('member_id',String,primary_key=True),Column('position',Integer,nullable=False),
    Column('definition_id',String),Column('legacy_variable',String),
)
land_evidence_snapshot_links=Table(
    'land_evidence_snapshot_links',meta,
    Column('snapshot_id',String,primary_key=True),Column('owner_kind',String,primary_key=True),
    Column('owner_id',String,primary_key=True),Column('relationship',String,primary_key=True),
    Column('reference_id',String,primary_key=True),Column('position',Integer,nullable=False),
)
land_evidence_snapshot_origins=Table(
    'land_evidence_snapshot_origins',meta,
    Column('snapshot_id',String,primary_key=True),Column('assessment_id',String,primary_key=True),
    Column('org',String,index=True,nullable=False),Column('assessment_fingerprint',String,nullable=False),
    Column('created',String,nullable=False),
)
module_runs=Table(
    'module_runs',meta,
    Column('id',String,primary_key=True),Column('org',String,index=True,nullable=False),
    Column('site_id',String,index=True,nullable=False),Column('boundary_version',Integer,nullable=False),
    Column('evidence_snapshot_id',String,index=True,nullable=False),
    Column('evidence_content_hash',String,nullable=False),
    Column('module_id',String,nullable=False),Column('module_version',String,nullable=False),
    Column('input_binding_version',String,nullable=False),
    Column('model_signature',String,nullable=False),Column('model_spec',JSON,nullable=False),
    Column('result',JSON,nullable=False),Column('content_hash',String,nullable=False),
    Column('created',String,nullable=False),Column('completed',String,nullable=False),
    UniqueConstraint(
        'org','evidence_snapshot_id','module_id','module_version',
        'input_binding_version','model_signature',name='uq_module_run_execution',
    ),
)
Index('land_evidence_snapshot_boundary',land_evidence_snapshots.c.org,
      land_evidence_snapshots.c.site_id,land_evidence_snapshots.c.boundary_version)
Index('land_evidence_member_lookup',land_evidence_snapshot_members.c.kind,
      land_evidence_snapshot_members.c.member_id)
Index('land_evidence_link_reference',land_evidence_snapshot_links.c.relationship,
      land_evidence_snapshot_links.c.reference_id)
Index('module_run_site',module_runs.c.org,module_runs.c.site_id,
      module_runs.c.boundary_version)
forward=Transformer.from_crs(4326,27700,always_xy=True).transform
backward=Transformer.from_crs(27700,4326,always_xy=True).transform
PILOT=[-1.65,51.5,-0.85,52.05]
LIMIT='Desk screening only. Boundaries and inventories have positional and temporal uncertainty. No habitat condition, BNG units, legal clearance or restoration suitability is established. Confirm through fieldwork and qualified advice.'
def now(): return datetime.now(timezone.utc).isoformat()
def uid(): return str(uuid.uuid4())
def init():
    meta.create_all(engine)
    # Additive migration: saved V0 evidence remains unchanged and readable.
    if 'model_spec' not in {col['name'] for col in inspect(engine).get_columns('assessments')}:
        with engine.begin() as c:
            c.execute(text('ALTER TABLE assessments ADD COLUMN ' + ('IF NOT EXISTS ' if engine.dialect.name=='postgresql' else '') + 'model_spec JSON'))
    if 'properties' not in {col['name'] for col in inspect(engine).get_columns('features')}:
        with engine.begin() as c:
            c.execute(text('ALTER TABLE features ADD COLUMN ' + ('IF NOT EXISTS ' if engine.dialect.name=='postgresql' else '') + 'properties JSON'))
    if engine.dialect.name=='postgresql':
        with engine.begin() as c:
            c.execute(text('CREATE EXTENSION IF NOT EXISTS postgis'))
            c.execute(text('ALTER TABLE features ADD COLUMN IF NOT EXISTS geom geometry(Geometry,4326)'))
            c.execute(text('CREATE INDEX IF NOT EXISTS features_geom_gist ON features USING gist(geom)'))
            c.execute(text('ALTER TABLE sites ADD COLUMN IF NOT EXISTS geom geometry(Geometry,4326)'))
            c.execute(text('CREATE INDEX IF NOT EXISTS sites_geom_gist ON sites USING gist(geom)'))

def boundary(value):
    if value.get('crs'): raise ValueError('Remove the CRS member and supply WGS84 longitude/latitude GeoJSON.')
    if value.get('type')=='FeatureCollection':
        if len(value.get('features',[]))!=1: raise ValueError('Upload exactly one Polygon or MultiPolygon feature.')
        value=value['features'][0]
    if value.get('type')=='Feature': value=value.get('geometry') or {}
    if value.get('type') not in ['Polygon','MultiPolygon']: raise ValueError('Boundary must be a Polygon or MultiPolygon.')
    if len(json.dumps(value))>500000: raise ValueError('Boundary is too detailed; maximum 500 KB.')
    # Reject unclosed rings before Shapely can close them implicitly.
    polygons=[value['coordinates']] if value['type']=='Polygon' else value['coordinates']
    for polygon in polygons:
        for ring in polygon:
            if len(ring)<4 or ring[0]!=ring[-1]: raise ValueError('Every boundary ring must be explicitly closed with at least four positions.')
            for p in ring:
                if len(p)!=2 or not all(isinstance(v,(int,float)) for v in p): raise ValueError('Use two-dimensional longitude/latitude coordinates.')
    g=shape(value)
    if g.is_empty or not g.is_valid: raise ValueError('Invalid boundary: '+explain_validity(g))
    if not box(-6.5,49.8,2,56).covers(g): raise ValueError('Boundary must use longitude/latitude in England. This pilot only has Oxfordshire-area data.')
    area=transform(forward,g).area/10000
    if area<=0 or area>100000: raise ValueError('Site must have positive area and be smaller than 100,000 hectares.')
    return mapping(g)

def latest(c):
    rows=c.execute(select(datasets).order_by(datasets.c.retrieved.desc())).mappings().all()
    out={}
    for r in rows:
        if r['key'] not in out: out[r['key']]=dict(r)
    return list(out.values())

def store_object(key,content,content_type='application/json'):
    if os.getenv('R2_BUCKET'):
        import boto3
        boto3.client('s3',endpoint_url=os.environ['R2_ENDPOINT'],aws_access_key_id=os.environ['R2_ACCESS_KEY_ID'],aws_secret_access_key=os.environ['R2_SECRET_ACCESS_KEY'],region_name='auto').put_object(Bucket=os.environ['R2_BUCKET'],Key=key,Body=content,ContentType=content_type)
    else:
        if os.getenv('CRC_ENV')!='development': raise RuntimeError('Hosted mode requires R2 storage.')
        p=ROOT/'objects'/key;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(content if isinstance(content,bytes) else content.encode())

class ImmutableObjectConflict(RuntimeError):
    """An immutable object key already contains different bytes."""

def store_object_immutable(key,content,content_type='application/json'):
    """Create an object once, or prove that the existing bytes are identical.

    Returns ``True`` when this call created the object and ``False`` when the
    exact content was already present. Hosted storage uses a conditional put;
    local development uses exclusive file creation.
    """
    payload=content if isinstance(content,bytes) else content.encode()
    existing=load_object(key)
    if existing is not None:
        if existing!=payload:raise ImmutableObjectConflict('Immutable object already exists with different content: '+key)
        return False
    if os.getenv('R2_BUCKET'):
        import boto3
        from botocore.exceptions import ClientError
        client=boto3.client('s3',endpoint_url=os.environ['R2_ENDPOINT'],aws_access_key_id=os.environ['R2_ACCESS_KEY_ID'],aws_secret_access_key=os.environ['R2_SECRET_ACCESS_KEY'],region_name='auto')
        try:
            client.put_object(Bucket=os.environ['R2_BUCKET'],Key=key,Body=payload,
                              ContentType=content_type,IfNoneMatch='*')
        except ClientError as error:
            if error.response.get('Error',{}).get('Code') not in ('PreconditionFailed','412'):
                raise
            existing=load_object(key)
            if existing!=payload:raise ImmutableObjectConflict('Immutable object already exists with different content: '+key)
            return False
        return True
    if os.getenv('CRC_ENV')!='development':raise RuntimeError('Hosted mode requires R2 storage.')
    p=ROOT/'objects'/key;p.parent.mkdir(parents=True,exist_ok=True)
    try:
        with p.open('xb') as handle:handle.write(payload)
        return True
    except FileExistsError:
        if p.read_bytes()!=payload:raise ImmutableObjectConflict('Immutable object already exists with different content: '+key)
        return False

def load_object(key):
    """Read a server-generated private evidence key; absence is explicit."""
    if os.getenv('R2_BUCKET'):
        import boto3
        from botocore.exceptions import ClientError
        client=boto3.client('s3',endpoint_url=os.environ['R2_ENDPOINT'],aws_access_key_id=os.environ['R2_ACCESS_KEY_ID'],aws_secret_access_key=os.environ['R2_SECRET_ACCESS_KEY'],region_name='auto')
        try:return client.get_object(Bucket=os.environ['R2_BUCKET'],Key=key)['Body'].read()
        except ClientError as error:
            if error.response.get('Error',{}).get('Code') in ('NoSuchKey','404'):return None
            raise
    path=ROOT/'objects'/key
    return path.read_bytes() if path.is_file() else None

def analyze(job):
    g=shape(job['geometry']); projected=transform(forward,g); area=projected.area/10000
    findings=[]
    with engine.connect() as c:
        for dsid in job['dataset_ids']:
            d=dict(c.execute(select(datasets).where(datasets.c.id==dsid)).mappings().one());m=d['metadata']
            covered=d['state']=='available' and box(*m['bbox']).covers(g)
            coverage='covered' if covered else 'unknown'
            coverage_fraction=None
            if d['key']=='built_world' and d['state']=='available':
                from backend.openmap_local import coverage_for_parcel
                coverage,coverage_fraction=coverage_for_parcel(job['geometry'])
                covered=coverage=='covered'
            if d['key']=='priority_habitats' and d['state']=='available' and not covered:
                acquired=box(*m['bbox'])
                if acquired.intersects(g):
                    examined=transform(forward,g.intersection(acquired)).area
                    if 0 < examined < projected.area:
                        coverage='partial';coverage_fraction=examined/projected.area
            f={'key':d['key'],'dataset':m['name'],'publisher':m.get('publisher',m['name']),'source_url':m['url'],'retrieved':d['retrieved'],'dataset_version':d['id'],'source_release':m.get('source_release',d['id']),'source_metadata_revision_date':m.get('source_metadata_revision_date'),'source_capture_end_date':m.get('source_capture_end_date'),'source_service_data_last_edit':(m.get('source_schema') or {}).get('service_data_last_edit'),'boundary_version':job['version'],'method':'union-intersection / EPSG:27700 / v1','rule_version':'crc-openmap-local-built-world-v1' if d['key']=='built_world' else ('crc-priority-habitats-v1' if d['key']=='priority_habitats' else ('crc-flood-1' if d['key']=='flood' else 'crc-screening-1')),'coverage':coverage,'coverage_fraction':1 if covered else coverage_fraction,'limitations':m['limitations'],'attribution':m.get('attribution',''),'licence':m.get('licence_text',m.get('license','')),'measured':None,'units':'ha','import_bbox':m['bbox'],'import_method':m.get('import_method','ArcGIS feature ID pagination / v1'),'geometry':None,'category':'missing','interpretation':'Obtain authoritative coverage before making a review decision.'}
            f.update(synthetic=m.get('synthetic',False), observed_at=m.get('observed_at'),
                     spatial_resolution_m=m.get('spatial_resolution_m'), raw_sha256=m.get('sha256'),
                     source_failure_type=m.get('failure_type'), source_error=m.get('error'),
                     raw_storage_reference=m.get('raw_object_key',f'reference/{d["id"]}/source.json') if d['state']=='available' else None,
                     raw_semantics=m.get('raw_semantics','Legacy assembled snapshot with original source attributes; any pre-repair geometries are retained in metadata.json.'))
            if covered:
                xmin,ymin,xmax,ymax=g.bounds
                if d['key']=='built_world':
                    from backend.openmap_local import SEARCH_RADIUS_M, TO_BNG, TO_WGS84, summarize_relationships
                    parcel_bng=transform(TO_BNG,g)
                    rail_search_wgs=transform(TO_WGS84,parcel_bng.buffer(SEARCH_RADIUS_M))
                    rxmin,rymin,rxmax,rymax=rail_search_wgs.bounds
                    object_type=features.c.properties['object_type'].as_string()
                    polygon_rows=[dict(row) for row in c.execute(select(
                        features.c.id,features.c.geometry,features.c.properties
                    ).where(
                        features.c.dataset_id==dsid,
                        object_type.in_(['building','functional_site']),
                        features.c.minx<=xmax,features.c.maxx>=xmin,
                        features.c.miny<=ymax,features.c.maxy>=ymin,
                    )).mappings()]
                    rail_rows=[dict(row) for row in c.execute(select(
                        features.c.id,features.c.geometry,features.c.properties
                    ).where(
                        features.c.dataset_id==dsid,
                        object_type.in_(['railway_track','railway_station']),
                        features.c.minx<=rxmax,features.c.maxx>=rxmin,
                        features.c.miny<=rymax,features.c.maxy>=rymin,
                    )).mappings()]
                    summary=summarize_relationships(job['geometry'],polygon_rows+rail_rows)
                    if summary['source_release']!=m.get('source_release'):
                        raise ValueError('OpenMap Local feature release does not match imported dataset release')
                    f['built_world']=summary
                    building=next(item for item in summary['observations']
                                  if item['definition_id']=='built.building.mapped_overlap_fraction')
                    f['fraction']=building['value']
                    f.update(measured=building['numerator']/10000,percent=building['value']*100,
                             category='observation',method=summary['processing_version'],
                             interpretation=('Mapped OpenMap Local built-world objects and their exact parcel relationships are retained as source-backed Earth evidence. No feasibility or operational conclusion is inferred.'))
                elif d['key']=='priority_habitats':
                    if engine.dialect.name=='postgresql':
                        rows=[dict(row) for row in c.execute(text('SELECT id,geometry,properties FROM features WHERE dataset_id=:d AND ST_Intersects(geom,ST_SetSRID(ST_GeomFromGeoJSON(:g),4326))'),{'d':dsid,'g':json.dumps(mapping(g))}).mappings()]
                    else:
                        rows=[dict(row) for row in c.execute(select(features.c.id,features.c.geometry,features.c.properties).where(features.c.dataset_id==dsid,features.c.minx<=xmax,features.c.maxx>=xmin,features.c.miny<=ymax,features.c.maxy>=ymin)).mappings()]
                    from backend.priority_habitats import summarize_intersections
                    summary=summarize_intersections(job['geometry'],rows,forward,backward)
                    if summary['source_release'] and summary['source_release']!=m.get('source_release'):
                        raise ValueError('PHI feature release does not match the imported dataset release')
                    summary['source_release']=m.get('source_release')
                    summary['source_metadata_revision_date']=m.get('source_metadata_revision_date')
                    summary['source_capture_end_date']=m.get('source_capture_end_date')
                    summary['source_service_data_last_edit']=(m.get('source_schema') or {}).get('service_data_last_edit')
                    f['priority_habitats']=summary
                    any_habitat=summary['any_main_priority_habitat']
                    overlap=any_habitat['mapped_intersection_area_ha']
                    f['fraction']=any_habitat['overlap_fraction']
                    f.update(measured=round(overlap,4),percent=round(f['fraction']*100,2),
                             category='observation',geometry=summary.pop('union_geometry'),
                             method='per-HabCode union and all-main-priority spatial union / EPSG:27700 / v1',
                             interpretation=('This PHI release maps one or more main priority habitat classes within the parcel. This does not establish condition, restoration need or feasibility.' if overlap>0 else 'No mapped main priority habitat overlap was found in the fully examined PHI extract. This is mapped zero, not ecological absence.'))
                else:
                    if engine.dialect.name=='postgresql':
                        rows=c.execute(text('SELECT geometry FROM features WHERE dataset_id=:d AND ST_Intersects(geom,ST_SetSRID(ST_GeomFromGeoJSON(:g),4326))'),{'d':dsid,'g':json.dumps(mapping(g))})
                    else:
                        rows=c.execute(select(features.c.geometry).where(features.c.dataset_id==dsid,features.c.minx<=xmax,features.c.maxx>=xmin,features.c.miny<=ymax,features.c.maxy>=ymin))
                    geoms=[transform(forward,shape(r[0] if isinstance(r[0],dict) else json.loads(r[0]))) for r in rows]
                    hit=projected.intersection(unary_union(geoms)) if geoms else None
                    overlap=hit.area/10000 if hit is not None else 0
                    # Preserve precision for models; display rounding is a separate concern.
                    f['fraction']=max(0,min(1,overlap/area))
                    f.update(measured=round(overlap,4),percent=round(overlap/area*100,2),category='constraint' if overlap>0 else 'observation',geometry=mapping(transform(backward,hit)) if hit is not None and not hit.is_empty else None,interpretation=('Ask an ecologist how the mapped feature affects potential restoration and required consents.' if overlap>0 else 'No overlap with this imported layer. This does not establish absence of other constraints.'))
                    if d['key']=='flood':
                        f['interpretation']=('Ask a flood-risk specialist what the mapped flood-zone overlap means for site management and whether hydrological investigation is needed. This is not evidence of wetland suitability.' if overlap>0 else 'No overlap with the imported Flood Zones 2 and 3. This does not establish absence of flood risk, including from unmapped sources.')
            else:
                f['limitations']+=' '+m.get('error','Partial or outside imported coverage, or dataset unavailable.')
                if d['key']=='priority_habitats' and coverage=='partial':
                    f['interpretation']='Only part of the parcel is inside the acquired PHI extract; no parcel-wide mapped-zero or overlap observation is asserted.'
                if d['key']=='built_world' and coverage=='partial':
                    f['interpretation']='Only part of the parcel is inside the acquired OpenMap Local extract; no parcel-wide mapped-zero or overlap observation is asserted.'
            findings.append(f)
    next_steps=['Commission a baseline habitat and condition survey.','Confirm ownership, management history and consent requirements.','Check local nature recovery priorities and connectivity with an ecologist.']
    if any(f['key']=='flood' and f['measured'] is not None and f['measured']>0 for f in findings):
        next_steps.append('Ask a flood-risk specialist whether the mapped flood-zone overlap warrants site-specific hydrological investigation.')
    from backend.nature import assess_nature
    nature=assess_nature(job,findings)
    return {'area_ha':round(area,4),'area_method':'EPSG:27700 planar area / v1','findings':findings,'limitations':LIMIT,'completed':now(),'boundary_version':job['version'],'site_name':job['site_name'],'geometry':job['geometry'],'next_steps':next_steps,'completeness':sum(f['coverage']=='covered' for f in findings),'dataset_count':len(findings),**nature}
