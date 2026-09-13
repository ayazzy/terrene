"""Small tracked assessment fixture for fresh-clone contract verification."""
from copy import deepcopy

from backend.earth import RawSource
from backend.wetland import run_wetland
from test_nature import FAVOURABLE, state


def synthetic_assessment():
    earth = state(FAVOURABLE | {'terrain.elevation_m': 100})
    earth.raw = [RawSource(
        id='synthetic-source', source='SYNTHETIC TEST SURVEY',
        source_dataset='Synthetic fixture',
        source_version='fixture-1',
        source_url='https://example.invalid/terrene-synthetic-assessment',
        retrieved_at='2026-09-01T00:00:00+00:00',
        timestamp='2026-09-01T00:00:00+00:00',
        raw_semantics='Generated deterministic values; no real place or measurement.',
        synthetic=True,
    )]
    return {
        'id': 'synthetic-assessment-result-v1',
        'site_name': 'Synthetic contract parcel',
        'geometry': deepcopy(earth.geometry),
        'completed': '2026-09-01T00:01:00+00:00',
        'state': 'completed',
        'environmental_state': earth.model_dump(mode='json'),
        'wetland_model': run_wetland(earth),
        'findings': [],
    }
