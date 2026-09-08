"""Assessment-local snapshot replay and raw object persistence, with explicit fixtures."""
from copy import deepcopy
from pathlib import Path
from hashlib import sha256
import pytest
from backend.environment import enrich_state
from backend.earth import RawSource
from backend.derived import compute_features
from backend.wetland import run_wetland,model_spec
from test_nature import state,obs,DATE


def test_snapshot_replay_reuses_exact_raw_and_normalized_evidence(monkeypatch,tmp_path):
    monkeypatch.setattr('backend.core.ROOT',tmp_path)
    monkeypatch.delenv('R2_BUCKET',raising=False)
    monkeypatch.setenv('CRC_ENV','development')
    content=b'explicit synthetic source fixture'
    raw_path=tmp_path/'input.bin';raw_path.write_bytes(content)
    digest=sha256(content).hexdigest()
    raw=RawSource(id=digest,source='Synthetic test fixture',source_dataset='Synthetic evidence',
                  source_version='fixture',source_url='https://example.invalid/fixture',retrieved_at=DATE,
                  storage_reference=str(raw_path),checksum=digest,raw_semantics='Synthetic fixture, never a production fallback',synthetic=True)
    observation=obs('terrain.slope_deg',1,raw_source_ids=[digest])
    calls=[]
    monkeypatch.setattr('backend.terrain.fetch_terrain',lambda *a,**k:calls.append('terrain') or {})
    monkeypatch.setattr('backend.terrain.terrain_observations',lambda *a:([raw.model_copy(deep=True)],[(100,observation)]))
    monkeypatch.setattr('backend.environment_sources.capture_environment',lambda *a,**k:calls.append('environment') or {})
    monkeypatch.setattr('backend.environment_sources.normalize_environment',lambda *a:([],[]))
    job={'id':'snapshot-fixture'}
    first=enrich_state(state({}),job)
    assert calls==['terrain','environment']
    assert first.get('terrain.slope_deg').raw_source_ids==[digest]
    assert (tmp_path/'objects'/first.raw[0].storage_reference).read_bytes()==content
    second=enrich_state(state({}),job)
    assert calls==['terrain','environment']
    assert first.model_dump(mode='json')==second.model_dump(mode='json')
    spec=model_spec()
    assert run_wetland(compute_features(first),spec)==run_wetland(compute_features(second),spec)
    changed=state({});changed.geometry['coordinates'][0][0][0]-=.001
    with pytest.raises(ValueError,match='geometry'):enrich_state(changed,job)
