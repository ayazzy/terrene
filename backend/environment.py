"""Acquire once per assessment, retain immutable inputs, then normalize to EarthState.

Provider IO stays outside the deterministic model. Saved jobs never re-download
on report export. A worker retry reuses its acquisition snapshot when available.
"""
from copy import deepcopy
from pathlib import Path
import json
import os

from backend.adapters import select_observations
from backend.earth import EarthState, fingerprint

ENVIRONMENT_VERSION = 'crc_england_real_inputs_v1'


def enrich_state(state: EarthState, job=None, refresh=False):
    from backend.core import ROOT, load_object, store_object
    from backend.terrain import fetch_terrain, terrain_observations
    from backend.environment_sources import capture_environment, normalize_environment

    cache = ROOT / 'environmental'
    cache.mkdir(parents=True, exist_ok=True)
    key = (f"environmental/assessments/{job['id']}/snapshot.json"
           if job and job.get('id') else None)
    saved = load_object(key) if key else None
    if saved is not None:
        snapshot = json.loads(saved)
        if snapshot['geometry_fingerprint'] != fingerprint(state.geometry) or snapshot['version'] != ENVIRONMENT_VERSION:
            raise ValueError('Environmental snapshot does not match the pinned geometry/processing version.')
        # Reuse exact normalized values and their original acquisition timestamps.
        retained = EarthState.model_validate(snapshot['environmental_state'])
        existing = [(100, o) for domain in state.normalized.values() for records in domain.values() for o in records]
        incoming = [(100, o) for domain in retained.normalized.values() for records in domain.values() for o in records]
        state.raw.extend(r for r in retained.raw if r.id not in {x.id for x in state.raw})
        select_observations(state, existing + incoming)
        return state

    imported = state.model_copy(deep=True)
    imported.raw = []
    imported.normalized = {}
    imported.selected = {}
    imported.selection_notes = {}
    imported.derived = {}
    candidates = []
    # Modules encode bounded acquisition failures as unknown observations.
    for capture, normalize in ((fetch_terrain, terrain_observations),
                               (capture_environment, normalize_environment)):
        snapshot = capture(state.geometry, cache_dir=cache, refresh=refresh)
        raw, observations = normalize(snapshot, imported)
        imported.raw.extend(raw)
        candidates.extend(observations)
    # Persist the original local source artifacts using the established private
    # object-storage adapter, including on hosted R2 workers.
    for raw in imported.raw:
        path = Path(raw.storage_reference) if raw.storage_reference else None
        if path and path.is_file():
            from hashlib import sha256
            content = path.read_bytes()
            checksum = sha256(content).hexdigest()
            if raw.checksum and checksum != raw.checksum:
                raise ValueError('Raw environmental source checksum mismatch.')
            raw.checksum = checksum
            destination = f'environmental/raw/{checksum}/{path.name}'
            store_object(destination, content, 'application/octet-stream')
            raw.storage_reference = destination
            for asset in raw.assets:
                if asset.href == str(path):
                    asset.href = 'private-object:' + destination
    select_observations(imported, candidates)
    if key:
        store_object(key, json.dumps({'version': ENVIRONMENT_VERSION,
                     'geometry_fingerprint': fingerprint(state.geometry),
                     'environmental_state': imported.model_dump(mode='json')}))
    existing = [(100, o) for domain in state.normalized.values() for records in domain.values() for o in records]
    state.raw.extend(imported.raw)
    select_observations(state, existing + candidates)
    return state
