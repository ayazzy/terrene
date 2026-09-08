"""Fetch the official OS Open Rivers GeoPackage once, with source manifest."""
from pathlib import Path
from backend.source_io import fetch_bytes,artifact,save_cache,read_cache
import json,zipfile
URL='https://api.os.uk/downloads/v1/products/OpenRivers/downloads'
def fetch(cache_dir=Path('data/environmental/rivers'),refresh=False):
 cache_dir=Path(cache_dir)
 cached=read_cache(cache_dir/'source.json',refresh)
 if cached and Path(cached['gpkg']).is_file():return cached
 body,headers=fetch_bytes(URL,max_bytes=2_000_000)
 manifest=json.loads(body)
 candidates=[x for x in manifest if x['format']=='GeoPackage' and x['area']=='GB']
 if len(candidates)!=1:raise ValueError('No unambiguous official OS GeoPackage download')
 item=candidates[0]
 if item['size']>100_000_000:raise ValueError('Open Rivers archive exceeds download budget')
 content,download=fetch_bytes(item['url'],max_bytes=100_000_000)
 if len(content)!=item['size']:raise ValueError('Incomplete OS download')
 from hashlib import md5
 if md5(content).hexdigest()!=item['md5']:raise ValueError('OS checksum mismatch')
 archive=artifact(cache_dir,content,'.zip')
 meta=artifact(cache_dir,body,'.json')
 with zipfile.ZipFile(archive['path']) as z:
  names=[n for n in z.namelist() if n.lower().endswith('.gpkg')]
  if len(names)!=1 or z.getinfo(names[0]).file_size>700_000_000:raise ValueError('Unexpected OS GeoPackage archive')
  gpkg=artifact(cache_dir,z.read(names[0]),'.gpkg')
 result={'status':'available','artifacts':[archive,meta,gpkg],'gpkg':gpkg['path'],'archive':archive,'metadata':meta,
         'retrieved_at':download['retrieved_at'],'request':download,'provider_download':item}
 save_cache(cache_dir/'source.json',result)
 return result
if __name__=='__main__':
 result=fetch()
 import sqlite3
 with sqlite3.connect(result['gpkg']) as c:
  print(c.execute('select * from gpkg_geometry_columns').fetchall())
  print(c.execute('select * from gpkg_contents').fetchall())
 print(result['gpkg'])
