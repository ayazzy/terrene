"""Actual captured source fixtures plus labelled synthetic geometry edge cases."""
import json
import sqlite3
import struct
from pathlib import Path
from copy import deepcopy
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box, mapping, LineString, shape
from shapely.ops import transform
from pyproj import Transformer
from backend.environment_sources import (landcover_statistics,watercourse_features,normalize_environment,
                                         capture_environment,capture_landcover,gpkg_wkb,CLASSES)
from backend.earth import EarthState
from backend.derived import compute_features,quality
from backend.wetland import model_spec,run_wetland
from test_nature import state,obs,DATE

FIXTURES=Path(__file__).parent/'fixtures'/'environment'
BACK=Transformer.from_crs(27700,4326,always_xy=True).transform

def make_gpkg(path,lines):
    # Tiny explicitly synthetic network, never a production fallback.
    with sqlite3.connect(path) as c:
        c.execute('create table gpkg_geometry_columns(table_name,column_name,geometry_type_name,srs_id)')
        c.execute("insert into gpkg_geometry_columns values ('watercourse_link','geometry','LINESTRING',27700)")
        c.execute('create table watercourse_link(fid integer primary key,geometry blob)')
        c.execute('create virtual table rtree_watercourse_link_geometry using rtree(id,minx,maxx,miny,maxy)')
        for i,line in enumerate(lines):
            blob=b'GP'+bytes([0,1])+struct.pack('<i',27700)+line.wkb
            c.execute('insert into watercourse_link values (?,?)',(i,blob))
            a,b,d,e=line.bounds
            c.execute('insert into rtree_watercourse_link_geometry values (?,?,?,?,?)',(i,a,d,b,e))
    return path


def test_distance_is_parcel_edge_to_full_line_in_metres(tmp_path):
    parcel=mapping(transform(BACK,box(450000,210000,450100,210100)))
    path=make_gpkg(tmp_path/'synthetic.gpkg',[LineString([(450150,209000),(450150,211000)])])
    result,reason=watercourse_features(parcel,path)
    assert result['hydrology.distance_to_water_m']==pytest.approx(50,abs=.01)
    assert result['hydrology.watercourse_intersection']=='no'
    assert result['hydrology.within_100m_watercourse_fraction']==pytest.approx(.5,abs=.001)
    assert reason is None


def test_intersection_and_no_nearby_line_have_distinct_semantics(tmp_path):
    parcel=mapping(transform(BACK,box(450000,210000,450100,210100)))
    path=make_gpkg(tmp_path/'synthetic.gpkg',[LineString([(450050,209000),(450050,211000)])])
    result,_=watercourse_features(parcel,path)
    assert result['hydrology.distance_to_water_m']==0
    assert result['hydrology.watercourse_intersection']=='yes'
    empty=make_gpkg(tmp_path/'empty.gpkg',[])
    result,reason=watercourse_features(parcel,empty)
    assert result['hydrology.distance_to_water_m'] is None
    assert result['hydrology.within_100m_watercourse_fraction']==0
    assert '5km' in reason


def test_actual_os_lines_intersect_actual_port_meadow(tmp_path):
    captured=json.loads((FIXTURES/'port_meadow_rivers.json').read_text())
    assert captured['source_archive_sha256']
    lines=[shape(f['geometry']) for f in captured['features']]
    path=make_gpkg(tmp_path/'real_subset.gpkg',lines)
    parcel=json.loads(Path('docs/port-meadow-reference.geojson').read_text())['geometry']
    result,_=watercourse_features(parcel,path)
    assert result['hydrology.distance_to_water_m']==0
    assert result['hydrology.within_100m_watercourse_fraction']==pytest.approx(.23374059,abs=.0001)


def test_landcover_class_semantics_and_nodata():
    affine=from_origin(-1.30,51.76,.0001,.0001)
    g=mapping(box(-1.30,51.7596,-1.2996,51.76))
    pixels=np.array([[30,30,30,30],[30,30,30,90],[30,30,50,80],[30,30,30,0]],dtype='uint8')
    stats,coverage=landcover_statistics(pixels,affine,g)
    assert coverage==15/16
    assert stats['land_use.current_cover']=='grassland'
    assert stats['ecology.mapped_wetland_fraction']==pytest.approx(1/15,abs=.00001)
    assert 'ecology.wetland_fraction' not in stats
    pixels[0,0]=99
    with pytest.raises(ValueError,match='Unrecognized'):landcover_statistics(pixels,affine,g)
    with pytest.raises(ValueError,match='full parcel'):landcover_statistics(pixels,affine,mapping(box(-1.31,51.75,-1.29,51.77)))


def test_real_worldcover_values_are_reproducible_without_network():
    manifest=json.loads((FIXTURES/'port_meadow_worldcover.json').read_text())
    from hashlib import sha256
    path=FIXTURES/'port_meadow_worldcover.tif'
    assert sha256(path.read_bytes()).hexdigest()==manifest['raster']['sha256']
    g=json.loads(Path('docs/port-meadow-reference.geojson').read_text())['geometry']
    with rasterio.open(path) as ds:statistics,coverage=landcover_statistics(ds.read(1),ds.transform,g)
    assert coverage==1
    assert statistics['land_use.current_cover']=='grassland'
    for variable in ('land_use.developed_fraction','ecology.mapped_wetland_fraction','hydrology.surface_water_fraction'):
        assert statistics[variable]==pytest.approx(manifest['statistics'][variable],abs=1e-10)


def test_acquisition_failures_stay_unknown(monkeypatch,tmp_path):
    monkeypatch.setattr('backend.environment_sources.fetch_rivers',lambda *args:(_ for _ in ()).throw(OSError('offline')))
    monkeypatch.setattr('backend.environment_sources.rasterio.open',lambda *args,**kwargs:(_ for _ in ()).throw(OSError('offline')))
    earth=state({})
    snapshot=capture_environment(earth.geometry,tmp_path)
    raw,candidates=normalize_environment(snapshot,earth)
    assert raw and all(o.value is None for _,o in candidates)
    assert all(o.missing_reason and o.confidence==0 for _,o in candidates)
    assert not any(o.synthetic for _,o in candidates)


def test_source_age_quality_is_pinned_not_wall_clock():
    earth=state({})
    old=obs('land_use.current_cover','grassland',timestamp='2021-01-01T00:00:00+00:00',confidence=.65,spatial=__import__('backend.earth',fromlist=['SpatialReference']).SpatialReference(geometry_or_cell_reference='fixture',spatial_resolution_m=10))
    assert quality(old,earth.as_of)==pytest.approx(.39)
    assert quality(old,old.timestamp)==pytest.approx(.65)
