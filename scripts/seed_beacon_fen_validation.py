"""Commit the curated Beacon Fen validation evidence and baseline run.

This script performs no network acquisition. It publishes one bounded,
human-structured official consent assertion and deliberately leaves
construction and grid timing unresolved when the source semantics do not fit
Project Evidence v1.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from backend import core
from backend.project_evidence import (
    ProjectEvidenceSubmission,
    create_project_subject,
    get_project_evidence,
    list_project_subjects,
    persist_project_evidence,
)
from backend.project_intelligence_store import (
    get_project_intelligence_run,
    run_project_intelligence,
)


PACKET_PATH = REPOSITORY_ROOT / 'docs' / 'sprints' / '003-beacon-fen-evidence.json'
DEFAULT_ORG = 'local-development'
EXPECTED_PROJECT = {
    'name': 'Beacon Fen Energy Park',
    'project_type': 'energy_infrastructure',
    'site_id': None,
}
EXPECTED_SOURCE_ID = 'pins-beacon-fen-decision-announcement'
EXPECTED_CLAIM_ID = 'beacon-fen-dco-consent-2026-08-21'
EXPECTED_EXCLUDED_FIELDS = {
    'construction_start_year',
    'operation_year',
    'grid_connection_by_year',
    'grid_connection_agreement',
}
EXPECTED_UNRESOLVED = {
    'missing_construction_status',
    'missing_grid_target',
}


def load_validation_packet(path: Path = PACKET_PATH) -> dict[str, Any]:
    packet = json.loads(path.read_text(encoding='utf-8'))
    if packet.get('packet_version') != 'beacon_fen_validation_v1':
        raise ValueError('Unsupported Beacon Fen validation packet')
    if packet.get('capture_method') != 'human_submitted_structured':
        raise ValueError('Beacon Fen evidence must remain human submitted')
    if packet.get('project_subject') != EXPECTED_PROJECT:
        raise ValueError('Beacon Fen Project Subject identity changed')
    metadata_notes = packet.get('source_metadata_notes', [])
    if (
        len(metadata_notes) != 1
        or metadata_notes[0].get('source_id') != EXPECTED_SOURCE_ID
        or metadata_notes[0].get('field') != 'published_at'
        or metadata_notes[0].get('stored_value') is not None
    ):
        raise ValueError('The validation packet must explain omitted source metadata')
    submission = packet.get('submission', {})
    sources = submission.get('sources', [])
    claims = submission.get('claims', [])
    if (
        len(sources) != 1
        or sources[0].get('id') != EXPECTED_SOURCE_ID
        or len(claims) != 1
        or claims[0].get('id') != EXPECTED_CLAIM_ID
    ):
        raise ValueError('Beacon Fen baseline must retain one certified source and claim')
    digest = sha256(sources[0]['retained_excerpt'].encode('utf-8')).hexdigest()
    if digest != sources[0]['content_hash']:
        raise ValueError('Retained Beacon Fen source excerpt hash mismatch')
    excluded = packet.get('excluded_assertions', [])
    if {item.get('reported_field') for item in excluded} != EXPECTED_EXCLUDED_FIELDS:
        raise ValueError('The validation packet must retain excluded assertions')
    return packet


def _project_subject(packet: dict[str, Any], *, org: str):
    expected = packet['project_subject']
    named = [
        item for item in list_project_subjects(org=org)
        if item.name == expected['name']
    ]
    exact = [
        item for item in named
        if item.project_type == expected['project_type']
        and item.site_id == expected['site_id']
    ]
    if len(exact) == 1 and len(named) == 1:
        return exact[0]
    if named:
        raise RuntimeError(
            'Beacon Fen Project Subject already exists with ambiguous or conflicting identity'
        )
    return create_project_subject(expected, org=org)


def _submission(packet: dict[str, Any], project_subject_id: str):
    submission = deepcopy(packet['submission'])
    for claim in submission['claims']:
        if claim['project_subject_id'] != 'PROJECT_SUBJECT_ID':
            raise ValueError('Beacon Fen template claim identity is not replaceable')
        claim['project_subject_id'] = project_subject_id
    return ProjectEvidenceSubmission.model_validate(submission)


def _verify_expected_result(run) -> None:
    result = run.result
    unresolved = {item.code for item in result.unresolved_questions}
    if (
        result.reported_stage.value != 'consented'
        or result.reported_stage.evidence_state != 'supported'
        or result.planning_status.values != ['approved']
        or result.planning_status.evidence_state != 'supported'
        or result.construction_status.evidence_state != 'insufficient_evidence'
        or result.construction_status.values
        or result.grid_connection_target.evidence_state != 'insufficient_evidence'
        or result.grid_connection_target.targets
        or unresolved != EXPECTED_UNRESOLVED
    ):
        raise RuntimeError(
            'Beacon Fen baseline no longer preserves the certified evidence semantics'
        )


def seed_beacon_fen_validation(*, org: str = DEFAULT_ORG) -> dict[str, Any]:
    core.init()
    packet = load_validation_packet()
    project = _project_subject(packet, org=org)
    if project.site_id is not None:
        raise RuntimeError('Beacon Fen validation must not fabricate a Site relationship')
    bundle = persist_project_evidence(
        project.id,
        _submission(packet, project.id),
        org=org,
    )
    run = run_project_intelligence(
        project.id,
        {'evidence_bundle_ids': [bundle.id]},
        org=org,
    )
    committed_bundle = get_project_evidence(project.id, bundle.id, org=org)
    committed_run = get_project_intelligence_run(run.id, org=org)
    if committed_bundle != bundle or committed_run != run:
        raise RuntimeError('Beacon Fen evidence or intelligence readback changed')
    _verify_expected_result(run)
    return {
        'project_subject_id': project.id,
        'project_subject_content_hash': project.content_hash,
        'site_id': project.site_id,
        'evidence_bundle_id': bundle.id,
        'evidence_bundle_content_hash': bundle.content_hash,
        'evidence_binding_id': run.evidence_binding_id,
        'evidence_binding_content_hash': run.evidence_binding_content_hash,
        'intelligence_run_id': run.id,
        'intelligence_run_content_hash': run.content_hash,
        'reported_stage': run.result.reported_stage.value,
        'reported_stage_evidence_state': run.result.reported_stage.evidence_state,
        'planning_status': run.result.planning_status.model_dump(mode='json'),
        'construction_status': run.result.construction_status.model_dump(mode='json'),
        'grid_connection_target': run.result.grid_connection_target.model_dump(mode='json'),
        'unresolved_question_codes': sorted(
            item.code for item in run.result.unresolved_questions
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Commit the curated Beacon Fen validation evidence and baseline run.',
    )
    parser.add_argument(
        '--org',
        default=os.getenv('TERRENE_VALIDATION_ORG', DEFAULT_ORG),
        help='organization that owns the isolated validation records',
    )
    args = parser.parse_args()
    print(json.dumps(seed_beacon_fen_validation(org=args.org), indent=2))


if __name__ == '__main__':
    main()
