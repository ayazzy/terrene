"""Opt-in bridge from saved assessments to immutable land evidence snapshots."""
import argparse
import json

from backend.core import init
from backend.land_evidence_store import create_snapshot_from_legacy_assessment


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Project and persist selected saved assessments without changing them.',
    )
    parser.add_argument('--org', required=True, help='Owning organisation ID')
    parser.add_argument('assessment_ids', nargs='+', help='Saved assessment IDs to project')
    args = parser.parse_args()
    init()
    for assessment_id in args.assessment_ids:
        snapshot = create_snapshot_from_legacy_assessment(assessment_id, org=args.org)
        print(json.dumps({
            'assessment_id': assessment_id,
            'snapshot_id': snapshot.id,
            'content_hash': snapshot.content_hash,
            'created': snapshot.created.isoformat(),
        }, sort_keys=True))


if __name__ == '__main__':
    main()
