"""Verify the retained Oxford Station height summary against live official WCS bytes."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.building_heights import (  # noqa: E402
    PROCESSING_VERSION,
    fetch_building_height_evidence,
    process_raster_pair,
)


ROOT = Path(__file__).resolve().parents[1]
ASSESSMENT = (
    ROOT / 'data' / 'verification' / 'england-real-openmap-local-2026-04' /
    'oxford-station-after.json'
)
EXPECTED = (
    ROOT / 'docs' / 'sprints' / '005-oxford-station-building-heights.json'
)


def main() -> None:
    assessment = json.loads(ASSESSMENT.read_text())
    expected = json.loads(EXPECTED.read_text())
    finding = next(item for item in assessment['findings'] if item['key'] == 'built_world')
    buildings = [item for item in finding['built_world']['objects']
                 if item['object_type'] == 'building']
    with tempfile.TemporaryDirectory(prefix='terrene-oxford-heights-') as directory:
        actual = fetch_building_height_evidence(buildings, directory)
        if actual['status'] != 'available':
            # This verification command is allowed one immediate repeat for a
            # transient public-service failure. Assessment acquisition itself
            # remains a single immutable attempt with an explicit gap.
            actual = fetch_building_height_evidence(buildings, directory)
        if actual['processing_version'] != PROCESSING_VERSION or actual['status'] != 'available':
            raise AssertionError(actual.get('missing_reason') or 'Live paired acquisition failed')
        artifact_identity = [
            {
                'role': item['role'], 'sha256': item['sha256'],
                'request_url': item['request']['url'],
            }
            for item in actual['artifacts']
        ]
        assert actual['requested_bounds_27700'] == expected['requested_bounds_27700']
        assert actual['survey_metadata'] == expected['survey_metadata']
        assert artifact_identity == expected['artifacts']
        assert actual['results'] == expected['results']
        by_role = {item['role']: item for item in actual['artifacts']}
        replay = process_raster_pair(
            by_role['dtm_raster']['path'], by_role['dsm_raster']['path'], buildings,
        )
        assert replay == actual['results']
    print(json.dumps({
        'site': expected['site'], 'buildings': len(buildings),
        'processing_version': PROCESSING_VERSION,
        'raw_hashes': {item['role']: item['sha256'] for item in artifact_identity},
        'p90_height_m': {
            item['source_object_key']: item['p90_height_m']
            for item in actual['results'] if item['state'] == 'available'
        },
        'deterministic_replay': 'passed',
    }, indent=2))


if __name__ == '__main__':
    main()
