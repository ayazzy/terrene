"""Additive schema migrations; v2 pins the model specification on each job."""
from backend.core import *
if __name__=='__main__':
    init()
    if engine.dialect.name=='postgresql':
        with engine.begin() as c:
            c.execute(text('CREATE TABLE IF NOT EXISTS crc_schema_migrations (version integer PRIMARY KEY, applied_at timestamptz DEFAULT now())'))
            for table in ['sites','assessments']:
                c.execute(text(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY'))
                # Browser roles get no direct table privileges: all mutations/downloads use authenticated API.
                for role in ['anon','authenticated']:
                    if c.execute(text('SELECT 1 FROM pg_roles WHERE rolname=:r'),{'r':role}).first():c.execute(text(f'REVOKE ALL ON TABLE {table} FROM {role}'))
            for table in ['datasets','features']:
                for role in ['anon','authenticated']:
                    if c.execute(text('SELECT 1 FROM pg_roles WHERE rolname=:r'),{'r':role}).first():c.execute(text(f'REVOKE ALL ON TABLE {table} FROM {role}'))
            c.execute(text('INSERT INTO crc_schema_migrations(version) VALUES (1) ON CONFLICT DO NOTHING'))
            c.execute(text('INSERT INTO crc_schema_migrations(version) VALUES (2) ON CONFLICT DO NOTHING'))
    print('CRC schema migrations 1–2 applied')
