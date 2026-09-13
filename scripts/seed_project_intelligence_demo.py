"""Create the isolated synthetic Sprint 002 history in the configured local database."""
from hashlib import sha256
import os

from backend import core
from backend.project_evidence import (
    create_project_subject, list_project_subjects, persist_project_evidence,
)
from backend.project_intelligence_store import run_project_intelligence


ORG = os.getenv('TERRENE_DEMO_ORG', 'local-development')
NAME = 'Synthetic North Fen Energy Project'


def source(source_id, version, excerpt, recorded):
    return {
        'id': source_id, 'source_version': version,
        'publisher': 'Synthetic planning register',
        'title': f'Synthetic evidence bulletin {version}',
        'reference': f'https://example.invalid/project-intelligence/{version}',
        'published_at': recorded, 'recorded_at': recorded,
        'retained_excerpt': excerpt,
        'content_hash': sha256(excerpt.encode()).hexdigest(),
        'entry_method': 'human_submitted_structured',
    }


def claim(subject_id, claim_id, predicate, value, source_id, excerpt, passage,
          event_date, *, supersedes=None, phase=None):
    start = excerpt.index(passage)
    return {
        'id': claim_id, 'project_subject_id': subject_id, 'phase': phase,
        'predicate': predicate, 'value': value, 'source_record_id': source_id,
        'locator': {'start': start, 'end': start + len(passage),
                    'exact_passage': passage},
        'time': {
            'kind': 'future_target' if predicate == 'target_grid_connection_date'
            else 'reported_occurrence',
            'effective_or_event_date': event_date,
        },
        'supersedes_claim_id': supersedes,
    }


def bundle(subject_id, key, recorded, excerpt, claims):
    source_id = f'demo-source-{key}'
    return persist_project_evidence(subject_id, {
        'schema_version': 'project_evidence_v1',
        'sources': [source(source_id, f'demo-{key}-v1', excerpt, recorded)],
        'claims': [claim(subject_id, source_id=source_id, excerpt=excerpt, **item)
                   for item in claims],
    }, org=ORG)


def main():
    core.init()
    project = next(
        (item for item in list_project_subjects(org=ORG) if item.name == NAME),
        None,
    ) or create_project_subject({
        'name': NAME, 'project_type': 'energy_infrastructure',
    }, org=ORG)

    excerpt_a = (
        'Planning permission is approved. Construction is under construction. '
        'The reported grid connection target is 2031-09-15.'
    )
    first = bundle(project.id, 'a', '2030-02-02T11:00:00Z', excerpt_a, [
        dict(claim_id='demo-planning-a', predicate='planning_status',
             value='approved', passage='Planning permission is approved',
             event_date='2030-02-01', phase='planning'),
        dict(claim_id='demo-construction-a', predicate='construction_status',
             value='under_construction', passage='Construction is under construction',
             event_date='2030-02-01', phase='construction'),
        dict(claim_id='demo-target-a', predicate='target_grid_connection_date',
             value={'state': 'known', 'date': '2031-09-15'},
             passage='reported grid connection target is 2031-09-15',
             event_date='2031-09-15', phase='construction'),
    ])
    excerpt_b = (
        'Construction remains under construction. '
        'The reported grid connection target is 2032-09-15.'
    )
    second = bundle(project.id, 'b', '2030-03-02T11:00:00Z', excerpt_b, [
        dict(claim_id='demo-construction-b', predicate='construction_status',
             value='under_construction', passage='Construction remains under construction',
             event_date='2030-03-01', phase='construction'),
        dict(claim_id='demo-target-b', predicate='target_grid_connection_date',
             value={'state': 'known', 'date': '2032-09-15'},
             passage='reported grid connection target is 2032-09-15',
             event_date='2032-09-15', phase='construction'),
    ])
    excerpt_c = 'Correction: the 2031-09-15 target is corrected to 2032-09-15.'
    correction = bundle(project.id, 'c', '2030-04-02T11:00:00Z', excerpt_c, [
        dict(claim_id='demo-target-c', predicate='target_grid_connection_date',
             value={'state': 'known', 'date': '2032-09-15'},
             passage='2031-09-15 target is corrected to 2032-09-15',
             event_date='2032-09-15', supersedes='demo-target-a',
             phase='construction'),
    ])
    excerpt_d = 'A historic bulletin reported a grid connection target of 2029-12-31.'
    elapsed = bundle(project.id, 'd', '2030-05-02T11:00:00Z', excerpt_d, [
        dict(claim_id='demo-target-d', predicate='target_grid_connection_date',
             value={'state': 'known', 'date': '2029-12-31'},
             passage='grid connection target of 2029-12-31',
             event_date='2029-12-31', phase='construction'),
    ])

    runs = [
        run_project_intelligence(project.id, {'evidence_bundle_ids': [first.id]}, org=ORG),
        run_project_intelligence(project.id, {
            'evidence_bundle_ids': [first.id, second.id],
        }, org=ORG),
        run_project_intelligence(project.id, {
            'evidence_bundle_ids': [first.id, second.id, correction.id],
        }, org=ORG),
        run_project_intelligence(project.id, {'evidence_bundle_ids': [elapsed.id]}, org=ORG),
    ]
    print(f'Project Subject: {project.id}')
    for run in runs:
        print(run.id, run.result.reported_stage.value,
              run.result.grid_connection_target.evidence_state)


if __name__ == '__main__':
    main()
