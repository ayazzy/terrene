"""The official benchmark is independent evidence, with incomplete extracts rejected."""
from copy import deepcopy
import json
from pathlib import Path
import httpx
import pytest
from shapely.geometry import box,mapping
from backend.benchmark import fetch_benchmark,benchmark_overlap,CRS84


def payload():
    return {'type':'FeatureCollection','numberMatched':1,'numberReturned':1,'features':[
        {'type':'Feature','id':'explicit-synthetic-benchmark','geometry':mapping(box(-1.30,51.75,-1.29,51.76)),'properties':{}}]}


def test_benchmark_overlap_is_not_an_opportunity_score(tmp_path):
    def response(request):return httpx.Response(200,json=payload(),headers={'content-crs':'<'+CRS84+'>'})
    with httpx.Client(transport=httpx.MockTransport(response)) as client:
        snapshot=fetch_benchmark(tmp_path,client=client)
    result=benchmark_overlap(mapping(box(-1.30,51.75,-1.29,51.76)),snapshot)
    assert result['overlap_fraction']==pytest.approx(1)
    assert result['status']=='mapped_overlap'
    assert 'score' not in result and 'band' not in result
    none=benchmark_overlap(mapping(box(-1.28,51.75,-1.27,51.76)),snapshot)
    assert none['status']=='no_mapped_overlap'
    assert 'Absence is not evidence' in none['meaning']
    outside=benchmark_overlap(mapping(box(-1.5,51.5,-1.4,51.6)),snapshot)
    assert outside['overlap_fraction'] is None


@pytest.mark.parametrize('failure',['count','next','crs','duplicate'])
def test_incomplete_benchmark_never_becomes_absence(tmp_path,failure):
    data=payload();headers={'content-crs':CRS84}
    if failure=='count':data['numberMatched']=2
    if failure=='next':data['links']=[{'rel':'next','href':'https://example.invalid/next'}]
    if failure=='crs':headers={}
    if failure=='duplicate':
        data['features']*=2;data['numberMatched']=data['numberReturned']=2
    with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(200,json=data,headers=headers))) as client:
        with pytest.raises(ValueError):fetch_benchmark(tmp_path,client=client)
