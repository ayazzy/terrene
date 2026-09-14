"""Oxford operating-scene provisioning boundaries and retained-data parity."""
import json

import pytest

from backend.earth import fingerprint
from scripts.provision_oxford_operating_scene import (
    EXPECTED_COUNTS,
    QA_SITE_NAME,
    REPOSITORY_ROOT,
    RETAINED_ASSESSMENT,
    isolated_data_directory,
    load_qa_assessment,
)


def test_qa_projection_preserves_the_retained_oxford_record():
    retained = json.loads(RETAINED_ASSESSMENT.read_text())
    retained_identity = fingerprint(retained)
    projected = load_qa_assessment()

    assert projected is not retained
    assert projected['site_name'] == QA_SITE_NAME
    assert (
        projected['environmental_state']['location_id']
        == retained['environmental_state']['location_id']
    )
    assert projected['geometry'] == retained['geometry']
    built = next(item['built_world'] for item in projected['findings']
                 if item['key'] == 'built_world')
    counts = {
        'buildings': sum(item['object_type'] == 'building' for item in built['objects']),
        'functional_sites': sum(
            item['object_type'] == 'functional_site' for item in built['objects']
        ),
        'railway_tracks': sum(
            item['object_type'] == 'railway_track' for item in built['objects']
        ),
        'railway_stations': sum(
            item['object_type'] == 'railway_station' for item in built['objects']
        ),
    }
    assert counts == EXPECTED_COUNTS
    assert len(built['relationships']) == 23
    assert fingerprint(json.loads(RETAINED_ASSESSMENT.read_text())) == retained_identity


def test_qa_destination_must_be_external_and_empty(tmp_path):
    with pytest.raises(ValueError, match='outside the repository'):
        isolated_data_directory(str(REPOSITORY_ROOT / 'data' / 'qa'))
    occupied = tmp_path / 'occupied'
    occupied.mkdir()
    (occupied / 'record').write_text('retained')
    with pytest.raises(ValueError, match='new or empty'):
        isolated_data_directory(str(occupied))
    available = tmp_path / 'isolated'
    assert isolated_data_directory(str(available)) == available.resolve()
