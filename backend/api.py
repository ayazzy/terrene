import os,json,html,hashlib
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Header, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select,insert,update
from sqlalchemy.exc import IntegrityError
from backend.core import *
from backend.wetland import model_spec
from backend.nature import model_report

@asynccontextmanager
async def lifespan(app):
    if os.getenv('CRC_ENV')!='development' and (engine.dialect.name!='postgresql' or not os.getenv('SUPABASE_URL') or not os.getenv('R2_BUCKET')): raise RuntimeError('Hosted mode requires Postgres, Supabase Auth and R2. Local bypass requires CRC_ENV=development.')
    init(); yield
app=FastAPI(title='CRC screening API',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=os.getenv('CRC_ORIGINS','http://localhost:3000,http://127.0.0.1:3000').split(','),allow_methods=['GET','POST','PATCH'],allow_headers=['Authorization','Content-Type'])
def organization(authorization:str|None=Header(default=None)):
    if os.getenv('CRC_ENV')=='development':return 'local-development'
    if not authorization or not authorization.startswith('Bearer '):raise HTTPException(401,'Sign in required')
    try:
        import jwt
        url=os.environ['SUPABASE_URL'].rstrip('/')
        token=authorization[7:];key=jwt.PyJWKClient(url+'/auth/v1/.well-known/jwks.json').get_signing_key_from_jwt(token).key
        claims=jwt.decode(token,key,algorithms=['ES256','RS256'],audience='authenticated',issuer=url+'/auth/v1',options={'require':['exp','sub','aud','iss']})
        org=claims.get('app_metadata',{}).get('org_id')
        if not isinstance(org,str) or not org:raise ValueError('No organization membership')
        return org
    except Exception:raise HTTPException(401,'Invalid session or missing organization membership')
def owned(c,table,id,org):
    row=c.execute(select(table).where(table.c.id==id,table.c.org==org)).mappings().first()
    if not row:raise HTTPException(404,'Record not found')
    return dict(row)
class SiteInput(BaseModel):
    name:str=Field(min_length=1,max_length=160)
    notes:str=Field(default='',max_length=5000)
    geometry:dict
class EditInput(BaseModel):
    name:str|None=Field(default=None,min_length=1,max_length=160)
    notes:str|None=Field(default=None,max_length=5000)
    status:str|None=None
    geometry:dict|None=None
    expected_version:int

def checked(g):
    try:return boundary(g)
    except Exception as e:raise HTTPException(422,str(e))
@app.get('/api/health')
def health():return {'ok':True,'mode':'development' if os.getenv('CRC_ENV')=='development' else 'hosted'}
@app.get('/api/sites')
def list_sites(org=Depends(organization)):
    with engine.connect() as c:
        rows=[dict(r) for r in c.execute(select(sites).where(sites.c.org==org).order_by(sites.c.created.desc())).mappings()]
        for r in rows:
            a=c.execute(select(assessments).where(assessments.c.org==org,assessments.c.site_id==r['id']).order_by(assessments.c.created.desc())).mappings().first();r['assessment']=dict(a) if a else None
        return rows
@app.post('/api/sites')
def create_site(data:SiteInput,org=Depends(organization)):
    g=checked(data.geometry);id=uid();name=data.name.strip()
    if not name:raise HTTPException(422,'Enter a site name')
    store_object(f'{org}/boundaries/{id}/1.json',json.dumps(data.geometry))
    row={'id':id,'org':org,'name':name,'notes':data.notes,'status':'Unreviewed','version':1,'geometry':g,'created':now()}
    with engine.begin() as c:
        c.execute(insert(sites).values(**row))
        if engine.dialect.name=='postgresql':c.execute(text('UPDATE sites SET geom=ST_SetSRID(ST_GeomFromGeoJSON(:g),4326) WHERE id=:id'),{'g':json.dumps(g),'id':id})
    return row
@app.patch('/api/sites/{id}')
def edit_site(id:str,data:EditInput,org=Depends(organization)):
    changes=data.model_dump(exclude_none=True);expected=changes.pop('expected_version')
    if 'name' in changes:
        changes['name']=changes['name'].strip()
        if not changes['name']:raise HTTPException(422,'Enter a site name')
    if 'status' in changes and changes['status'] not in ['Unreviewed','Investigate','Hold','Archived']:raise HTTPException(422,'Invalid review status')
    if 'geometry' in changes:changes['geometry']=checked(changes['geometry']);changes['version']=expected+1
    with engine.begin() as c:
        old=owned(c,sites,id,org)
        if old['version']!=expected:raise HTTPException(409,'Boundary changed. Refresh before editing.')
        result=c.execute(update(sites).where(sites.c.id==id,sites.c.org==org,sites.c.version==expected).values(**changes))
        if result.rowcount!=1:raise HTTPException(409,'Boundary changed. Refresh before editing.')
        if 'geometry' in changes:store_object(f'{org}/boundaries/{id}/{expected+1}.json',json.dumps(changes['geometry']))
        if 'geometry' in changes and engine.dialect.name=='postgresql':c.execute(text('UPDATE sites SET geom=ST_SetSRID(ST_GeomFromGeoJSON(:g),4326) WHERE id=:id'),{'g':json.dumps(changes['geometry']),'id':id})
        return owned(c,sites,id,org)
@app.get('/api/datasets')
def catalog(org=Depends(organization)):
    with engine.connect() as c:return latest(c)
@app.post('/api/sites/{id}/assessments')
def submit(id:str,refresh_environment:bool=False,org=Depends(organization)):
    with engine.begin() as c:
        s=owned(c,sites,id,org);ds=sorted(d['id'] for d in latest(c))
        if not ds:raise HTTPException(409,'No dataset imports registered. Run the import pipeline first.')
        spec=model_spec(refresh_sources=True) if refresh_environment else model_spec()
        dedupe=hashlib.sha256(json.dumps([org,id,s['version'],ds,spec['signature']] + ([uid()] if refresh_environment else [])).encode()).hexdigest()
        prior=c.execute(select(assessments).where(assessments.c.dedupe==dedupe)).mappings().first()
        if prior:return dict(prior)
        row={'id':uid(),'org':org,'site_id':id,'site_name':s['name'],'version':s['version'],'geometry':s['geometry'],'state':'queued','attempts':0,'lease':0,'token':uid(),'created':now(),'dataset_ids':ds,'dedupe':dedupe,'error':None,'result':None,'model_spec':spec}
        try:
            with c.begin_nested():c.execute(insert(assessments).values(**row))
        except IntegrityError:return dict(c.execute(select(assessments).where(assessments.c.dedupe==dedupe)).mappings().one())
        return row
@app.get('/api/sites/{id}/assessments')
def history(id:str,org=Depends(organization)):
    with engine.connect() as c:
        owned(c,sites,id,org)
        return [dict(r) for r in c.execute(select(assessments).where(assessments.c.site_id==id,assessments.c.org==org).order_by(assessments.c.created.desc())).mappings()]
@app.get('/api/assessments/{id}')
def assessment(id:str,org=Depends(organization)):
    with engine.connect() as c:return owned(c,assessments,id,org)
@app.get('/api/assessments/{id}/report',response_class=HTMLResponse)
def report(id:str,org=Depends(organization)):
    with engine.connect() as c:
        a=owned(c,assessments,id,org);s=owned(c,sites,a['site_id'],org)
    r=a['result']
    if not r:raise HTTPException(409,'Assessment is not ready')
    esc=lambda v:html.escape(str(v))
    body=f'<h1>CRC · Screening report</h1><h2>{esc(a["site_name"])}</h2><p>Assessment {esc(id)} · {esc(a["state"])}<br>Boundary v{a["version"]} · completed {esc(r["completed"])}</p><p>Current review decision at export: <b>{esc(s["status"])}</b> (user decision). Current boundary v{s["version"]}.</p><p>Area: {r["area_ha"]} ha · {esc(r["area_method"])}</p>'
    if s['version']!=a['version']:body+='<p><b>Historical assessment: this is not the current boundary.</b></p>'
    body+=model_report(r)
    for f in r['findings']:
        body+=f'<section><h3>{esc(f["dataset"])}</h3><p>{"Unknown" if f["measured"] is None else str(f["measured"])+" ha overlap"} · coverage {esc(f["coverage"])}</p><p>{esc(f["interpretation"])}</p><p>Source: <a href="{esc(f["source_url"])}">{esc(f["source_url"])}</a><br>Retrieved {esc(f["retrieved"])} · dataset version {esc(f["dataset_version"])}<br>Boundary v{f["boundary_version"]} · {esc(f["method"])} · {esc(f["rule_version"])}</p><p>{esc(f["limitations"])}</p><small>{esc(f["attribution"])}</small></section>'
        if f.get('import_bbox'):body+='<p>Imported extent (west, south, east, north): '+esc(', '.join(map(str,f['import_bbox'])))+' degrees. Import: '+esc(f.get('import_method','Not recorded'))+'</p>'
    body+='<h3>Next steps</h3><ul>'+''.join('<li>'+esc(x)+'</li>' for x in r['next_steps'])+'</ul><h3>Limitations</h3><p>'+esc(r['limitations'])+'</p>'
    document='<!doctype html><html lang="en"><meta charset="utf-8"><title>CRC screening report</title><style>body{font:15px/1.6 system-ui;max-width:850px;margin:40px auto;color:#183b36}h1{border-bottom:3px solid #166853}section{break-inside:avoid;border-top:1px solid #ccd5d2;padding-top:10px}a{overflow-wrap:anywhere}small{font-size:12px}@media print{body{margin:0}@page{margin:18mm}}</style>'+body+'</html>'
    store_object(f'{org}/reports/{id}/{uid()}.html',document,'text/html')
    return HTMLResponse(document,headers={'Content-Disposition':f'attachment; filename="crc-{id}.html"'})

class LoginInput(BaseModel):
    email:str=Field(min_length=3,max_length=254)
    password:str=Field(min_length=1,max_length=200)
@app.post('/api/auth/sign-in')
def sign_in(data:LoginInput):
    import httpx
    url=os.getenv('SUPABASE_URL','').rstrip('/');key=os.getenv('SUPABASE_ANON_KEY','')
    if not url or not key:raise HTTPException(503,'Supabase sign-in is not configured.')
    try:
        r=httpx.post(url+'/auth/v1/token?grant_type=password',headers={'apikey':key},json={'email':data.email,'password':data.password},timeout=20)
        if r.status_code!=200:raise HTTPException(401,'Sign-in failed. Check your credentials.')
        data=r.json();return {'access_token':data['access_token'],'expires_in':data['expires_in']}
    except httpx.HTTPError:raise HTTPException(503,'Sign-in service is unavailable.')

@app.get('/api/sites/{id}/boundary/{version}')
def download_boundary(id:str,version:int,org=Depends(organization)):
    from fastapi.responses import Response
    with engine.connect() as c:
        s=owned(c,sites,id,org)
        if version<1 or version>s['version']:raise HTTPException(404,'Boundary version not found')
    key=f'{org}/boundaries/{id}/{version}.json'
    if os.getenv('R2_BUCKET'):
        import boto3
        content=boto3.client('s3',endpoint_url=os.environ['R2_ENDPOINT'],aws_access_key_id=os.environ['R2_ACCESS_KEY_ID'],aws_secret_access_key=os.environ['R2_SECRET_ACCESS_KEY'],region_name='auto').get_object(Bucket=os.environ['R2_BUCKET'],Key=key)['Body'].read()
    else:
        p=ROOT/'objects'/key
        if not p.is_file():raise HTTPException(404,'Boundary upload not found')
        content=p.read_bytes()
    return Response(content,media_type='application/geo+json',headers={'Content-Disposition':f'attachment; filename="boundary-v{version}.geojson"'})

# Explicit, additive review-context action. Ordinary reads never publish evidence.
from backend.land_evidence import LandEvidenceValidationError
from backend.land_evidence_store import LandEvidenceSnapshotError, LandEvidenceSnapshotNotFound
from backend.module_runs import ModuleRunError, ModuleRunNotFound, ModuleRunRecord
from backend.screening_context_store import (
    ScreeningUnavailable, get_screening_run, prepare_screening_context,
    read_assessment_context,
)
from backend.screening_context_report import screening_context_report
from backend.screening_context_map import (
    ScreeningMapFeatureCollection, build_screening_map_features,
)
from backend.project_evidence import (
    ProjectSubjectCreate, ProjectEvidenceBundleRead, ProjectEvidenceBundleRecord,
    ProjectEvidenceConflict, ProjectEvidenceNotFound,
    ProjectEvidenceSubmission, ProjectEvidenceValidationError,
    ProjectSubjectNotFound, ProjectSubjectRecord,
    create_project_subject, get_project_subject, get_project_evidence,
    list_project_evidence, list_project_subjects, persist_project_evidence,
)
from backend.design_proposals import (
    AlternativeInput, AlternativeRecord, ProjectInput,
    ProjectRecord as DesignProjectRecord,
    ProposalConflict, ProposalIntegrityError, ProposalNotFound,
    RevisionInput, RevisionRecord, create_alternative,
    create_project as create_design_project,
    create_revision, get_alternative, get_project as get_design_project,
    get_revision, list_alternatives, list_projects as list_design_projects,
    list_revisions,
)
from backend.project_evidence_binding import ProjectEvidenceBindingError
from backend.project_intelligence_store import (
    ProjectIntelligenceConflict, ProjectIntelligenceNotFound,
    ProjectIntelligenceRunRecord, ProjectIntelligenceRunRequest,
    ProjectIntelligenceRunSummary, get_project_intelligence_run,
    list_project_intelligence_runs, run_project_intelligence,
)


def screening_operation(operation):
    try:
        return operation()
    except (ModuleRunNotFound, LandEvidenceSnapshotNotFound):
        raise HTTPException(404, 'Record not found')
    except ScreeningUnavailable as error:
        raise HTTPException(409, str(error))
    except (LandEvidenceValidationError, ValueError):
        raise HTTPException(409, 'Saved evidence is unsupported or invalid for Screening Context v1. Historical records have been preserved.')
    except (ModuleRunError, LandEvidenceSnapshotError, ImmutableObjectConflict):
        # Never send an internal object key, storage error or credential to clients.
        raise HTTPException(500, 'Screening context integrity check failed. Stored evidence or run content is missing or contradictory; history has not been overwritten.')


@app.post('/api/assessments/{id}/screening-context', response_model=ModuleRunRecord)
def prepare_context(id: str, org=Depends(organization)):
    return screening_operation(lambda: prepare_screening_context(id, org=org))


@app.get('/api/assessments/{id}/screening-context', response_model=ModuleRunRecord | None)
def read_context(id: str, org=Depends(organization)):
    return screening_operation(lambda: read_assessment_context(id, org=org))


@app.get('/api/screening-context-runs/{id}', response_model=ModuleRunRecord)
def read_context_run(id: str, org=Depends(organization)):
    return screening_operation(lambda: get_screening_run(id, org=org))


@app.get(
    '/api/screening-context-runs/{id}/map-features',
    response_model=ScreeningMapFeatureCollection,
)
def read_context_map_features(id: str, response: Response, org=Depends(organization)):
    response.headers['Cache-Control'] = 'no-store'
    return screening_operation(lambda: build_screening_map_features(
        get_screening_run(id, org=org)
    ))


@app.get('/api/assessments/{id}/screening-context/report', response_class=HTMLResponse)
def context_report(id: str, org=Depends(organization)):
    run = screening_operation(lambda: read_assessment_context(id, org=org))
    if run is None:
        raise HTTPException(409, 'Prepare screening context before exporting it.')
    with engine.connect() as connection:
        assessment_row = owned(connection, assessments, id, org)
        site = owned(connection, sites, assessment_row['site_id'], org)
    return HTMLResponse(screening_context_report(
        run, assessment_id=id, site_name=assessment_row['site_name'],
        review_status=site['status'], current_version=site['version'],
    ), headers={'Content-Disposition': 'attachment; filename="terrene-screening-context.html"',
                'Cache-Control': 'no-store'})


# Project Evidence stores attributed source claims only. No route in this
# surface edits a Project Subject, fetches a source URL, or creates Reasoning output.
def project_evidence_operation(operation):
    try:
        return operation()
    except (ProjectSubjectNotFound, ProjectEvidenceNotFound):
        raise HTTPException(404, 'Record not found')
    except ProjectEvidenceValidationError as error:
        raise HTTPException(422, str(error))
    except ValidationError:
        raise HTTPException(422, 'Project Evidence references or locators are invalid.')
    except ProjectEvidenceConflict:
        # Avoid exposing private object keys or cross-record integrity details.
        raise HTTPException(409, 'Project Evidence conflicts with committed immutable history.')
    except (LandEvidenceSnapshotError, ImmutableObjectConflict):
        raise HTTPException(500, 'Project Evidence integrity check failed; history has not been overwritten.')


@app.post('/api/project-subjects', response_model=ProjectSubjectRecord)
def create_evidence_project_subject(
    data: ProjectSubjectCreate, org=Depends(organization),
):
    return project_evidence_operation(
        lambda: create_project_subject(data, org=org)
    )


@app.get('/api/project-subjects', response_model=list[ProjectSubjectRecord])
def read_project_subjects(org=Depends(organization)):
    return project_evidence_operation(lambda: list_project_subjects(org=org))


@app.get('/api/project-subjects/{id}', response_model=ProjectSubjectRecord)
def read_project_subject(id: str, org=Depends(organization)):
    return project_evidence_operation(
        lambda: get_project_subject(id, org=org)
    )


@app.post(
    '/api/project-subjects/{id}/evidence-bundles',
    response_model=ProjectEvidenceBundleRead,
)
def submit_project_evidence(
    id: str, data: ProjectEvidenceSubmission, org=Depends(organization),
):
    return project_evidence_operation(
        lambda: persist_project_evidence(id, data, org=org)
    )


@app.get(
    '/api/project-subjects/{id}/evidence-bundles',
    response_model=list[ProjectEvidenceBundleRecord],
)
def read_project_evidence_list(id: str, org=Depends(organization)):
    return project_evidence_operation(
        lambda: list_project_evidence(id, org=org)
    )


@app.get(
    '/api/project-subjects/{id}/evidence-bundles/{bundle_id}',
    response_model=ProjectEvidenceBundleRead,
)
def read_project_evidence_bundle(
    id: str, bundle_id: str, org=Depends(organization),
):
    return project_evidence_operation(
        lambda: get_project_evidence(id, bundle_id, org=org)
    )


def project_intelligence_operation(operation):
    try:
        return operation()
    except (ProjectSubjectNotFound, ProjectEvidenceNotFound,
            ProjectIntelligenceNotFound):
        raise HTTPException(404, 'Record not found')
    except (ProjectEvidenceBindingError, ProjectEvidenceValidationError,
            ValidationError, ValueError) as error:
        raise HTTPException(422, str(error))
    except (ProjectEvidenceConflict, ProjectIntelligenceConflict,
            LandEvidenceSnapshotError, ImmutableObjectConflict):
        raise HTTPException(
            409,
            'Project Intelligence integrity check failed; immutable history was not changed.',
        )


@app.post(
    '/api/project-subjects/{id}/intelligence-runs',
    response_model=ProjectIntelligenceRunRecord,
)
def create_project_intelligence_run(
    id: str, data: ProjectIntelligenceRunRequest,
    org=Depends(organization),
):
    return project_intelligence_operation(
        lambda: run_project_intelligence(id, data, org=org)
    )


@app.get(
    '/api/project-subjects/{id}/intelligence-runs',
    response_model=list[ProjectIntelligenceRunSummary],
)
def read_project_intelligence_runs(id: str, org=Depends(organization)):
    return project_intelligence_operation(
        lambda: list_project_intelligence_runs(id, org=org)
    )


@app.get(
    '/api/project-intelligence-runs/{id}',
    response_model=ProjectIntelligenceRunRecord,
)
def read_project_intelligence_run(id: str, org=Depends(organization)):
    return project_intelligence_operation(
        lambda: get_project_intelligence_run(id, org=org)
    )
def proposal_operation(operation):
    try:
        return operation()
    except ProposalNotFound:
        raise HTTPException(404, 'Record not found')
    except ProposalConflict as error:
        raise HTTPException(409, str(error))
    except ProposalIntegrityError:
        raise HTTPException(
            409,
            'Pinned evidence or boundary integrity check failed; no proposed design was changed.',
        )
    except ValueError as error:
        raise HTTPException(422, str(error))


@app.post('/api/projects', response_model=DesignProjectRecord)
def create_infrastructure_project(data: ProjectInput, org=Depends(organization)):
    return proposal_operation(lambda: create_design_project(data, org=org))


@app.get('/api/projects', response_model=list[DesignProjectRecord])
def read_infrastructure_projects(site_id: str | None = None,
                                 org=Depends(organization)):
    return proposal_operation(
        lambda: list_design_projects(org=org, site_id=site_id)
    )


@app.get('/api/projects/{id}', response_model=DesignProjectRecord)
def read_infrastructure_project(id: str, org=Depends(organization)):
    return proposal_operation(lambda: get_design_project(id, org=org))


@app.post('/api/projects/{id}/alternatives', response_model=AlternativeRecord)
def create_design_alternative(id: str, data: AlternativeInput,
                              org=Depends(organization)):
    return proposal_operation(lambda: create_alternative(id, data, org=org))


@app.get('/api/projects/{id}/alternatives', response_model=list[AlternativeRecord])
def read_design_alternatives(id: str, org=Depends(organization)):
    return proposal_operation(lambda: list_alternatives(id, org=org))


@app.get('/api/alternatives/{id}', response_model=AlternativeRecord)
def read_design_alternative(id: str, org=Depends(organization)):
    return proposal_operation(lambda: get_alternative(id, org=org))


@app.post('/api/alternatives/{id}/revisions', response_model=RevisionRecord)
def create_design_revision(id: str, data: RevisionInput,
                           org=Depends(organization)):
    return proposal_operation(lambda: create_revision(id, data, org=org))


@app.get('/api/alternatives/{id}/revisions', response_model=list[RevisionRecord])
def read_design_revisions(id: str, org=Depends(organization)):
    return proposal_operation(lambda: list_revisions(id, org=org))


@app.get('/api/design-revisions/{id}', response_model=RevisionRecord)
def read_design_revision(id: str, org=Depends(organization)):
    return proposal_operation(lambda: get_revision(id, org=org))
