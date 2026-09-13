"""Additive schema migrations; v6 proposals, v7 Project Evidence subjects."""
from backend.core import *
if __name__=='__main__':
    init()
    if engine.dialect.name=='postgresql':
        with engine.begin() as c:
            c.execute(text('CREATE TABLE IF NOT EXISTS crc_schema_migrations (version integer PRIMARY KEY, applied_at timestamptz DEFAULT now())'))
            for table in [
                'sites', 'assessments', 'land_evidence_snapshots',
                'land_evidence_snapshot_origins', 'module_runs',
                'infrastructure_projects', 'design_alternatives',
                'design_revisions', 'project_subjects',
                'project_evidence_bundles', 'project_evidence_claims',
                'project_evidence_sources',
            ]:
                c.execute(text(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY'))
                # Browser roles get no direct table privileges: all mutations/downloads use authenticated API.
                for role in ['anon','authenticated']:
                    if c.execute(text('SELECT 1 FROM pg_roles WHERE rolname=:r'),{'r':role}).first():c.execute(text(f'REVOKE ALL ON TABLE {table} FROM {role}'))
            for table in ['datasets','features','land_evidence_snapshot_members','land_evidence_snapshot_links','project_evidence_bundle_members']:
                for role in ['anon','authenticated']:
                    if c.execute(text('SELECT 1 FROM pg_roles WHERE rolname=:r'),{'r':role}).first():c.execute(text(f'REVOKE ALL ON TABLE {table} FROM {role}'))
            c.execute(text('INSERT INTO crc_schema_migrations(version) VALUES (1) ON CONFLICT DO NOTHING'))
            c.execute(text('INSERT INTO crc_schema_migrations(version) VALUES (2) ON CONFLICT DO NOTHING'))
            c.execute(text('INSERT INTO crc_schema_migrations(version) VALUES (3) ON CONFLICT DO NOTHING'))
            c.execute(text('INSERT INTO crc_schema_migrations(version) VALUES (4) ON CONFLICT DO NOTHING'))
            c.execute(text('INSERT INTO crc_schema_migrations(version) VALUES (5) ON CONFLICT DO NOTHING'))
            c.execute(text('INSERT INTO crc_schema_migrations(version) VALUES (6) ON CONFLICT DO NOTHING'))
            c.execute(text('INSERT INTO crc_schema_migrations(version) VALUES (7) ON CONFLICT DO NOTHING'))
    print('CRC schema migrations 1–7 applied')
