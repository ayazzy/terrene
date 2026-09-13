"""One-way local migration; refuses any non-empty target. Keep source as backup."""
from backend.core import *
from sqlalchemy import func,insert
from hashlib import sha256
if engine.dialect.name!='postgresql':raise SystemExit('Set DATABASE_URL to the target local Postgres database.')
init()
source=create_engine('sqlite:///data/crc.db')
source_tables=set(inspect(source).get_table_names())
copied=[datasets,features,sites,assessments,land_evidence_snapshots,
        land_evidence_snapshot_members,land_evidence_snapshot_links,
        land_evidence_snapshot_origins,module_runs,project_subjects,
        project_evidence_bundles,project_evidence_bundle_members,
        project_evidence_sources,project_evidence_claims,
        project_intelligence_runs,
        infrastructure_projects,design_alternatives,design_revisions]
with engine.connect() as c:
    if any(c.execute(select(func.count()).select_from(t)).scalar() for t in copied):raise SystemExit('Target must be empty; no data changed.')
if 'land_evidence_snapshots' in source_tables:
    with source.connect() as s:
        snapshot_rows=[dict(r) for r in s.execute(select(land_evidence_snapshots)).mappings()]
    object_root=(Path('data')/'objects').resolve()
    for snapshot in snapshot_rows:
        path=(object_root/snapshot['manifest_key']).resolve()
        if not path.is_relative_to(object_root) or not path.is_file():
            raise SystemExit('Land evidence manifest is missing; no database rows copied: '+snapshot['manifest_key'])
        content=path.read_bytes()
        if sha256(content).hexdigest()!=snapshot['manifest_sha256']:
            raise SystemExit('Land evidence manifest checksum failed; no database rows copied: '+snapshot['manifest_key'])
        store_object_immutable(snapshot['manifest_key'],content)
if 'project_evidence_bundles' in source_tables:
    with source.connect() as s:
        project_evidence_rows=[dict(r) for r in s.execute(select(project_evidence_bundles)).mappings()]
    object_root=(Path('data')/'objects').resolve()
    for bundle in project_evidence_rows:
        path=(object_root/bundle['manifest_key']).resolve()
        if not path.is_relative_to(object_root) or not path.is_file():
            raise SystemExit('Project Evidence manifest is missing; no database rows copied: '+bundle['manifest_key'])
        content=path.read_bytes()
        if sha256(content).hexdigest()!=bundle['manifest_sha256']:
            raise SystemExit('Project Evidence manifest checksum failed; no database rows copied: '+bundle['manifest_key'])
        store_object_immutable(bundle['manifest_key'],content)
with engine.begin() as c:
    # Recheck transactionally after object verification in case another writer
    # populated the target concurrently. Content-addressed orphan objects are safe.
    if any(c.execute(select(func.count()).select_from(t)).scalar() for t in copied):raise SystemExit('Target must be empty; no data changed.')
    with source.connect() as s:
        for t in copied:
            if t.name not in source_tables:
                print(t.name,0)
                continue
            source_column_names={column['name'] for column in inspect(source).get_columns(t.name)}
            source_columns=[column for column in t.c if column.name in source_column_names]
            rows=[dict(r) for r in s.execute(select(*source_columns)).mappings()]
            for row in rows:
                for column in t.c:
                    if column.name not in row:row[column.name]=None
            if rows:c.execute(insert(t),rows)
            print(t.name,len(rows))
    for t in ['sites','features']:c.execute(text(f'UPDATE {t} SET geom=ST_SetSRID(ST_GeomFromGeoJSON(geometry::text),4326)'))
print('Copied successfully; original SQLite retained.')
