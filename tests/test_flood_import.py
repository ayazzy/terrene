"""Synthetic wire responses only: no live services or production database writes."""
import copy
from urllib.parse import urlencode
import httpx
import pytest
from backend import flood

BBOX = [-1.65, 51.5, -0.85, 52.05]
CANONICAL = 'https://environment.data.gov.uk/geoservices/datasets/04532375-a198-476e-985e-0579a0a11b47/ogc/features/v1/collections/' + flood.COLLECTION + '/items'

def feature(id, zone):
    return {'type':'Feature','id':id,'properties':{'flood_zone':zone,'origin':'synthetic test'},'geometry':{'type':'Polygon','coordinates':[[[-1.3,51.7],[-1.2,51.7],[-1.2,51.8],[-1.3,51.7]]]}}

def pages():
    next_url=CANONICAL+'?'+urlencode({'f':'json','bbox':','.join(map(str,BBOX)),'crs':flood.CRS84,'limit':250,'startIndex':1})
    return [
        {'type':'FeatureCollection','features':[feature('a','FZ2')],'numberMatched':2,'numberReturned':1,'links':[{'rel':'next','href':next_url}]},
        {'type':'FeatureCollection','features':[feature('b','FZ3')],'numberMatched':2,'numberReturned':1,'links':[]}
    ]

def client_for(data, crs=flood.CRS84):
    requests=[]
    def handler(request):
        requests.append(request)
        if request.url.path.endswith('/'+flood.COLLECTION):
            return httpx.Response(200,json={'id':flood.COLLECTION,'links':[{'rel':'items','type':'application/json','href':CANONICAL}]})
        index=1 if request.url.params.get('startIndex') else 0
        assert request.url.params['bbox']==','.join(map(str,BBOX))
        return httpx.Response(200,json=data[index],headers={'Content-Crs':'<'+crs+'>'})
    return httpx.Client(transport=httpx.MockTransport(handler)),requests

def test_complete_flood_pagination_retains_both_zones_and_provenance():
    client,requests=client_for(pages())
    with client:metadata,result=flood.fetch_flood(BBOX,client)
    assert len(requests)==3
    assert len(result['features'])==2
    assert metadata['crc_zone_counts']=={'FZ2':1,'FZ3':1}
    assert metadata['crc_output_crs']==flood.CRS84
    assert len(metadata['crc_pages'])==2
    assert metadata['crc_download_bytes']>0

@pytest.mark.parametrize('fault',['early_end','duplicate','changed_count','wrong_returned','wrong_zone','changed_bbox','foreign_host','wrong_crs'])
def test_incomplete_or_changed_flood_response_is_rejected(fault):
    data=copy.deepcopy(pages());crs=flood.CRS84
    if fault=='early_end':data[0]['links']=[]
    elif fault=='duplicate':data[1]['features'][0]['id']='a'
    elif fault=='changed_count':data[1]['numberMatched']=3
    elif fault=='wrong_returned':data[0]['numberReturned']=2
    elif fault=='wrong_zone':data[1]['features'][0]['properties']['flood_zone']='unknown'
    elif fault=='changed_bbox':data[0]['links'][0]['href']=data[0]['links'][0]['href'].replace('bbox=', 'other=')
    elif fault=='foreign_host':data[0]['links'][0]['href']=data[0]['links'][0]['href'].replace('environment.data.gov.uk','example.invalid')
    elif fault=='wrong_crs':crs='http://www.opengis.net/def/crs/EPSG/0/27700'
    client,requests=client_for(data,crs)
    with client,pytest.raises(ValueError):flood.fetch_flood(BBOX,client)
    assert all(r.url.host=='environment.data.gov.uk' for r in requests)

def test_bounded_flood_download(monkeypatch):
    monkeypatch.setattr(flood,'MAX_BYTES',10)
    client,_=client_for(pages())
    with client,pytest.raises(ValueError,match='download limit'):flood.fetch_flood(BBOX,client)
