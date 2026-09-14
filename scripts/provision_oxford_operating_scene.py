"""Provision the retained Oxford Station exemplar into an isolated QA database.

The command deliberately refuses repository-local or non-empty destinations. It
copies no evidence into source control: retained OpenMap records are read from the
repository, while live EA DSM/DTM responses and the SQLite database are written
only beneath the caller-supplied QA data directory.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RETAINED_ASSESSMENT = (
    REPOSITORY_ROOT
    / 'data'
    / 'verification'
    / 'england-real-openmap-local-2026-04'
    / 'oxford-station-after.json'
)
QA_SITE_ID = 'verification-oxford-station'
QA_ASSESSMENT_ID = 'c10d373d-444d-5d04-9f3b-25c36a8f0d45'
QA_SITE_NAME = 'Oxford Station — spatial intelligence QA'
QA_ORGANISATION = 'local-development'
EXPECTED_COUNTS = {
    'buildings': 5,
    'functional_sites': 2,
    'railway_tracks': 7,
    'railway_stations': 1,
}
MODEL_SPEC_KEYS = (
    'model_version',
    'adapter_version',
    'feature_version',
    'environment_version',
    'refresh_sources',
    'config',
    'signature',
)


def load_qa_assessment() -> dict[str, Any]:
    """Return a QA identity projection without mutating the retained record."""
    payload = deepcopy(json.loads(RETAINED_ASSESSMENT.read_text()))
    payload['site_name'] = QA_SITE_NAME
    # The legacy location identifier is part of every retained observation's
    # immutable boundary-support reference, so it is also the isolated QA Site id.
    return payload


def isolated_data_directory(value: str) -> Path:
    destination = Path(value).expanduser().resolve()
    repository = REPOSITORY_ROOT.resolve()
    if destination == repository or repository in destination.parents:
        raise ValueError('QA data directory must be outside the repository')
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('QA data directory must be new or empty')
    destination.mkdir(parents=True, exist_ok=True)
    return destination


def provision(destination: Path) -> dict[str, Any]:
    database_path = destination / 'oxford-operating-scene.db'
    os.environ['CRC_ENV'] = 'development'
    os.environ['CRC_DATA_DIR'] = str(destination)
    os.environ['DATABASE_URL'] = f'sqlite:///{database_path}'

    sys.path.insert(0, str(REPOSITORY_ROOT))
    from sqlalchemy import insert

    from backend import core
    from backend.building_heights import acquire_for_assessment
    from backend.infrastructure_map_scene import build_infrastructure_map_scene
    from backend.land_evidence_store import (
        get_land_evidence_snapshot,
        load_land_evidence_snapshot,
    )
    from backend.screening_context_store import prepare_screening_context

    core.init()
    payload = load_qa_assessment()
    built_finding = next(
        item for item in payload['findings'] if item['key'] == 'built_world'
    )
    job = {
        'id': QA_ASSESSMENT_ID,
        'site_id': QA_SITE_ID,
        'version': payload['boundary_version'],
        'geometry': payload['geometry'],
    }
    height_evidence = acquire_for_assessment(job, built_finding)
    available_heights = [
        item for item in height_evidence['results'] if item['state'] == 'available'
    ]
    if len(available_heights) != EXPECTED_COUNTS['buildings']:
        raise RuntimeError(
            'Oxford QA requires five verified height observations; the exact '
            'acquisition result was retained with explicit gaps in the isolated '
            'data directory.'
        )
    built_finding['building_heights'] = height_evidence
    model_spec = {
        key: deepcopy(payload['wetland_model'][key]) for key in MODEL_SPEC_KEYS
    }
    with core.engine.begin() as connection:
        connection.execute(
            insert(core.sites).values(
                id=QA_SITE_ID,
                org=QA_ORGANISATION,
                name=QA_SITE_NAME,
                notes=(
                    'Isolated engineering exemplar provisioned from the retained '
                    'Oxford Station verification record.'
                ),
                status='Investigate',
                version=payload['boundary_version'],
                geometry=payload['geometry'],
                created=payload['completed'],
            )
        )
        connection.execute(
            insert(core.assessments).values(
                id=QA_ASSESSMENT_ID,
                org=QA_ORGANISATION,
                site_id=QA_SITE_ID,
                version=payload['boundary_version'],
                geometry=payload['geometry'],
                site_name=QA_SITE_NAME,
                state='completed',
                attempts=1,
                lease=0,
                token='retained-oxford-qa',
                error=None,
                result=payload,
                created=payload['completed'],
                dataset_ids=[],
                dedupe='retained-oxford-operating-scene-v1',
                model_spec=model_spec,
            )
        )
    core.store_object(
        f'{QA_ORGANISATION}/boundaries/{QA_SITE_ID}/1.json',
        json.dumps(payload['geometry'], sort_keys=True, separators=(',', ':')),
        'application/geo+json',
    )

    run = prepare_screening_context(QA_ASSESSMENT_ID, org=QA_ORGANISATION)
    snapshot = get_land_evidence_snapshot(
        run.evidence_snapshot_id, org=QA_ORGANISATION
    )
    projection = load_land_evidence_snapshot(snapshot.id, org=QA_ORGANISATION)
    scene = build_infrastructure_map_scene(snapshot, projection)
    actual_counts = {item.id: item.feature_count for item in scene.layers}
    if actual_counts != EXPECTED_COUNTS:
        raise AssertionError(
            f'Oxford scene counts changed: {actual_counts!r} != {EXPECTED_COUNTS!r}'
        )
    relationship_count = sum(
        len(item.properties.relationships) for item in scene.features
    )
    if relationship_count != 23:
        raise AssertionError(f'Oxford scene expected 23 relationships, got {relationship_count}')

    return {
        'data_directory': str(destination),
        'database_url': os.environ['DATABASE_URL'],
        'site_id': QA_SITE_ID,
        'assessment_id': QA_ASSESSMENT_ID,
        'snapshot_id': snapshot.id,
        'screening_run_id': run.id,
        'registry_version': snapshot.registry_version,
        'feature_counts': actual_counts,
        'parcel_relationships': relationship_count,
        'height_backed_buildings': len(available_heights),
        'frontend_url': (
            'http://127.0.0.1:3000/?mode=site&entity=site&id=' + QA_SITE_ID
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--data-dir',
        required=True,
        help='New or empty directory outside the repository for the QA database and raw artifacts.',
    )
    parser.add_argument(
        '--live-ea-wcs',
        action='store_true',
        help='Acknowledge that official Environment Agency WCS bytes will be acquired.',
    )
    args = parser.parse_args()
    if not args.live_ea_wcs:
        parser.error('--live-ea-wcs is required; QA heights are never fabricated or defaulted')
    destination = isolated_data_directory(args.data_dir)
    print(json.dumps(provision(destination), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
