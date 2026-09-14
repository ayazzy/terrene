"""Independently compare a retained acquisition with a LIVE ArcGIS polygon query.

Run as ``python -m scripts.verify_geographic_acquisition --org ORG --id ID``.
Outputs only a small verification record. No fixtures/fallback, evidence mutation,
provider geometry download, or private object locations. A changed provider release
requires a new capture, never rewriting the previous result.
"""
import argparse
import json

from backend import core
from backend.acquisition import read_acquisition
from backend.acquisition_contracts import AcquisitionError
from backend.acquisition_sources import BoundedClient, SSSI_URL


def verify(org, acquisition_id):
    summary = read_acquisition(org, acquisition_id)
    if summary['state'] != 'succeeded':
        raise AcquisitionError('successful_capture_required')
    area = summary['request']['area']
    polygons = [area['coordinates']] if area['type'] == 'Polygon' else area['coordinates']
    geometry = {'rings': [ring for polygon in polygons for ring in polygon],
                'spatialReference': {'wkid':4326}}
    reader = BoundedClient()
    try:
        before = reader.get(SSSI_URL, {'f':'json'})
        response = reader.get(SSSI_URL+'/query', {
            'f':'json', 'where':'1=1', 'geometry':json.dumps(geometry),
            'geometryType':'esriGeometryPolygon', 'inSR':'4326',
            'spatialRel':'esriSpatialRelIntersects', 'returnIdsOnly':'true',
        })
        after = reader.get(SSSI_URL, {'f':'json'})
        if (before.get('editingInfo') != after.get('editingInfo')
                or after.get('editingInfo') != summary['result']['publisher_editing_info']):
            raise AcquisitionError('provider_changed_since_capture')
        ids = response.get('objectIds')
        if (not isinstance(ids,list) or response.get('exceededTransferLimit')
                or response.get('objectIdFieldName') != 'OBJECTID'
                or any(type(i) is not int for i in ids) or len(set(ids)) != len(ids)
                or sorted(ids) != sorted(summary['result']['selected_object_ids'])):
            raise AcquisitionError('independent_selection_mismatch')
        return {'verification_version':'geographic_acquisition_live_verification_v1',
                'verified_at':core.now(), 'acquisition_id':acquisition_id,
                'request':summary['request'], 'manifest_sha256':summary['manifest_sha256'],
                'artifact_checksums':summary['artifact_checksums'],
                'capture_started':summary['started'], 'capture_completed':summary['completed'],
                'feature_count':summary['result']['feature_count'],
                'native_feature_ids':summary['result']['native_feature_ids'],
                'independent_object_ids':sorted(ids), 'independent_selection_match':True,
                'publisher_editing_info':after.get('editingInfo'),
                'independent_method':'New live ArcGIS polygon-intersection ID query; adapter uses envelope candidates plus local polygon selection.',
                'independent_responses':reader.responses,
                'limits':'Current service comparison, not ecological/scientific validation; no atomic provider snapshot.'}
    finally:
        reader.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--org',required=True)
    parser.add_argument('--id',required=True)
    args=parser.parse_args()
    try:
        print(json.dumps(verify(args.org,args.id),indent=2))
    except AcquisitionError as exc:
        print(json.dumps({'error_code':exc.code}))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
