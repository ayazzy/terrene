"""One-way local migration; refuses any non-empty target. Keep source as backup."""
from backend.core import *
from sqlalchemy import func,insert
if engine.dialect.name!='postgresql':raise SystemExit('Set DATABASE_URL to the target local Postgres database.')
init()
source=create_engine('sqlite:///data/crc.db')
with engine.begin() as c:
    if any(c.execute(select(func.count()).select_from(t)).scalar() for t in [sites,assessments,datasets,features]):raise SystemExit('Target must be empty; no data changed.')
    with source.connect() as s:
        for t in [datasets,features,sites,assessments]:
            rows=[dict(r) for r in s.execute(select(t)).mappings()]
            if rows:c.execute(insert(t),rows)
            print(t.name,len(rows))
    for t in ['sites','features']:c.execute(text(f'UPDATE {t} SET geom=ST_SetSRID(ST_GeomFromGeoJSON(geometry::text),4326)'))
print('Copied successfully; original SQLite retained.')
