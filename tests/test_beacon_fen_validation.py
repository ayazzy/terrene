"""Real-source semantic verification for the Beacon Fen validation packet."""
from hashlib import sha256
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, func, select

from backend import api, core
from scripts.seed_beacon_fen_validation import (
    EXPECTED_EXCLUDED_FIELDS,
    EXPECTED_PROJECT,
    EXPECTED_UNRESOLVED,
    load_validation_packet,
    seed_beacon_fen_validation,
)


@pytest.fixture
def beacon_fen_database(tmp_path, monkeypatch):
    database_url = os.getenv('CRC_TEST_DATABASE_URL')
    database = create_engine(
        database_url or 'sqlite:///' + str(tmp_path / 'beacon-fen.db'),
        connect_args=(
            {} if database_url
            else {'check_same_thread': False, 'timeout': 30}
        ),
        pool_pre_ping=True,
    )
    monkeypatch.setattr(core, 'engine', database)
    monkeypatch.setattr(api, 'engine', database)
    monkeypatch.setattr(core, 'ROOT', tmp_path)
    monkeypatch.setenv('CRC_ENV', 'development')
    monkeypatch.delenv('R2_BUCKET', raising=False)
    core.init()
    tables = (
        core.project_intelligence_runs,
        core.project_evidence_bundle_members,
        core.project_evidence_sources,
        core.project_evidence_claims,
        core.project_evidence_bundles,
        core.project_subjects,
    )
    if database_url:
        with database.begin() as connection:
            for table in tables:
                connection.execute(delete(table))
    yield database
    api.app.dependency_overrides.clear()
    if database_url:
        with database.begin() as connection:
            for table in tables:
                connection.execute(delete(table))
    database.dispose()


def _count(database, table) -> int:
    with database.connect() as connection:
        return connection.execute(select(func.count()).select_from(table)).scalar_one()


def test_curated_packet_retains_exact_official_consent_and_exclusions():
    packet = load_validation_packet()
    source = packet['submission']['sources'][0]
    claim = packet['submission']['claims'][0]
    locator = claim['locator']
    assert packet['project_subject'] == EXPECTED_PROJECT
    assert source['publisher'] == 'Planning Inspectorate'
    assert source['published_at'] is None
    assert packet['source_metadata_notes'] == [{
        'source_id': source['id'],
        'field': 'published_at',
        'reported_value': '2026-08-21',
        'stored_value': None,
        'reason': (
            'The official page reports a date but no clock time; SourceRecord v1 '
            'requires a timezone-aware datetime, so no time is fabricated.'
        ),
    }]
    assert sha256(source['retained_excerpt'].encode()).hexdigest() == source['content_hash']
    assert source['retained_excerpt'][locator['start']:locator['end']] == locator['exact_passage']
    assert claim['predicate'] == 'planning_status'
    assert claim['value'] == 'approved'
    assert claim['time'] == {
        'kind': 'reported_occurrence',
        'effective_or_event_date': '2026-08-21',
    }
    assert {
        item['reported_field'] for item in packet['excluded_assertions']
    } == EXPECTED_EXCLUDED_FIELDS


def test_seed_is_idempotent_and_baseline_stays_truthfully_partial(
    beacon_fen_database,
):
    first = seed_beacon_fen_validation(org='beacon-fen-verification')
    second = seed_beacon_fen_validation(org='beacon-fen-verification')
    assert second == first
    assert first['site_id'] is None
    assert first['reported_stage'] == 'consented'
    assert first['reported_stage_evidence_state'] == 'supported'
    assert first['planning_status']['values'] == ['approved']
    assert first['construction_status']['evidence_state'] == 'insufficient_evidence'
    assert first['construction_status']['values'] == []
    assert first['grid_connection_target']['evidence_state'] == 'insufficient_evidence'
    assert first['grid_connection_target']['targets'] == []
    assert set(first['unresolved_question_codes']) == EXPECTED_UNRESOLVED
    assert _count(beacon_fen_database, core.project_subjects) == 1
    assert _count(beacon_fen_database, core.project_evidence_bundles) == 1
    assert _count(beacon_fen_database, core.project_intelligence_runs) == 1


def test_baseline_is_readable_through_tenant_scoped_public_api(
    beacon_fen_database,
):
    seeded = seed_beacon_fen_validation(org='beacon-fen-verification')
    api.app.dependency_overrides[api.organization] = lambda: 'beacon-fen-verification'
    with TestClient(api.app) as client:
        projects = client.get('/api/project-subjects')
        bundle = client.get(
            f'/api/project-subjects/{seeded["project_subject_id"]}'
            f'/evidence-bundles/{seeded["evidence_bundle_id"]}'
        )
        run = client.get(
            f'/api/project-intelligence-runs/{seeded["intelligence_run_id"]}'
        )
        assert projects.status_code == bundle.status_code == run.status_code == 200
        assert projects.json()[0]['name'] == 'Beacon Fen Energy Park'
        assert bundle.json()['evidence']['claims'][0]['value'] == 'approved'
        assert run.json()['result']['reported_stage'] == {
            'value': 'consented',
            'evidence_state': 'supported',
            'references': run.json()['result']['reported_stage']['references'],
        }
        before = {
            table.name: _count(beacon_fen_database, table)
            for table in (
                core.project_subjects,
                core.project_evidence_bundles,
                core.project_intelligence_runs,
            )
        }
        client.get('/api/project-subjects')
        client.get(f'/api/project-intelligence-runs/{seeded["intelligence_run_id"]}')
        assert before == {
            table.name: _count(beacon_fen_database, table)
            for table in (
                core.project_subjects,
                core.project_evidence_bundles,
                core.project_intelligence_runs,
            )
        }

        api.app.dependency_overrides[api.organization] = lambda: 'another-org'
        assert client.get(
            f'/api/project-intelligence-runs/{seeded["intelligence_run_id"]}'
        ).status_code == 404
