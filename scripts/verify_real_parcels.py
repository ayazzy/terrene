"""Run an independent real-site inspection set without creating workspace sites.

Use the same DATABASE_URL / CRC_DATA_DIR as API and worker. Environmental raw
snapshots are the normal pipeline artifacts; no fixture values are substituted.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.benchmark import fetch_benchmark, benchmark_overlap
from backend.core import analyze, latest, engine, ROOT, boundary, load_object
from backend.earth import EarthState, fingerprint
from backend.land_evidence import (
    BuiltWorldObservation,
    PriorityHabitatObservation,
    project_land_evidence,
)
from backend.land_evidence_store import (
    load_land_evidence_snapshot,
    persist_land_evidence_snapshot,
)
from backend.wetland import model_spec, run_wetland
from backend.wetland_binding import bind_wetland_input


def paired_coverage(before, after):
    """Count identical variables in each pair, including condition if applicable."""
    variables = after['wetland_model']['evidence_summary']['gating_coverage']['variables']
    states = [EarthState.model_validate(r['environmental_state']) for r in (before, after)]
    counts = [sum(s.get(v) is not None and s.get(v).value is not None for v in variables) for s in states]
    return {'variables': variables, 'required': len(variables), 'before_available': counts[0],
            'after_available': counts[1], 'after_missing': [v for v in variables if states[1].get(v) is None or states[1].get(v).value is None]}


def inspect_priority_habitats(projection):
    observations = [item for item in projection.observations
                    if isinstance(item, PriorityHabitatObservation)]
    classes = [item for item in observations
               if item.definition_id == 'ecology.priority_habitat.mapped_overlap_fraction']
    union = next((item for item in observations
                  if item.definition_id == 'ecology.priority_habitat.any_mapped_overlap_fraction'), None)
    gaps = [item.model_dump(mode='json') for item in projection.gaps
            if (item.definition_id or '').startswith('ecology.priority_habitat.')]
    return {
        'coverage_status': union.support.coverage_status if union else (
            gaps[0]['state'] if gaps else 'unavailable'
        ),
        'known_mapped_zero': bool(union and union.known_zero),
        'union_mapped_area_ha': union.measurement.mapped_intersection_area_ha if union else None,
        'union_overlap_fraction': union.measurement.overlap_fraction if union else None,
        'source_release': union.provenance.source_release if union else None,
        'source_schema_version': union.provenance.source_schema_version if union else None,
        'source_metadata_revision_date': (
            union.provenance.source_metadata_revision_date if union else None
        ),
        'source_capture_end_date': union.provenance.source_capture_end_date if union else None,
        'source_service_data_last_edit': (
            union.provenance.source_service_data_last_edit.isoformat() if union else None
        ),
        'habitats': [
            {
                'code': item.dimensions['habitat_code'],
                'name': item.mapped_habitat_name,
                'mapped_area_ha': item.measurement.mapped_intersection_area_ha,
                'overlap_fraction': item.measurement.overlap_fraction,
                'source_feature_reference_ids': item.source_feature_reference_ids,
            }
            for item in classes
        ],
        'source_feature_count': len(projection.source_feature_references),
        'source_features': [item.model_dump(mode='json')
                            for item in projection.source_feature_references],
        'gaps': gaps,
    }


def inspect_built_world(projection):
    observations = [item for item in projection.observations
                    if isinstance(item, BuiltWorldObservation)]
    by_definition = {item.definition_id: item for item in observations}
    gaps = [item.model_dump(mode='json') for item in projection.gaps
            if (item.definition_id or '').startswith(
                ('built.building.', 'built.functional_site.', 'transport.railway_')
            )]
    counts = {
        object_type: sum(item.object_type == object_type for item in projection.objects)
        for object_type in ('building', 'functional_site', 'railway_track', 'railway_station')
    }

    def observation(definition_id):
        item = by_definition.get(definition_id)
        if item is None:
            return None
        return {
            'value': item.value.value,
            'unit': item.unit,
            'known_mapped_zero': item.known_zero,
            'numerator': item.measurement.numerator,
            'denominator': item.measurement.denominator,
            'numerator_unit': item.measurement.numerator_unit,
            'denominator_unit': item.measurement.denominator_unit,
            'aggregation': item.measurement.aggregation,
            'supporting_object_ids': item.supporting_object_ids,
        }

    return {
        'coverage_status': (
            observations[0].support.coverage_status if observations else
            gaps[0]['state'] if gaps else 'unavailable'
        ),
        'source_release': observations[0].provenance.source_release if observations else None,
        'source_schema_version': (
            observations[0].provenance.source_schema_version if observations else None
        ),
        'rail_distance_coverage_status': (
            'partial' if any(item['reason_code'] == 'partial_search_coverage'
                             for item in gaps) else 'full'
        ),
        'object_counts': counts,
        'objects': [item.model_dump(mode='json') for item in projection.objects],
        'relationship_count': len(projection.relationships),
        'relationships': [item.model_dump(mode='json') for item in projection.relationships],
        'observations': {
            definition_id: observation(definition_id)
            for definition_id in (
                'built.building.mapped_overlap_fraction',
                'built.functional_site.mapped_overlap_fraction',
                'transport.railway_track.mapped_length_within',
                'transport.railway_track.distance_min',
                'transport.railway_station.distance_min',
            )
        },
        'functional_sites': [
            {
                'source_feature_id': item.source_feature_id,
                'distinctive_name': item.distinctive_name,
                'site_theme': item.site_theme,
                'classification': item.classification,
            }
            for item in projection.objects if item.object_type == 'functional_site'
        ],
        'railway_stations': [
            {
                'source_feature_id': item.source_feature_id,
                'distinctive_name': item.distinctive_name,
                'classification': item.classification,
            }
            for item in projection.objects if item.object_type == 'railway_station'
        ],
        'gaps': gaps,
    }


def inspect_result(feature, before, pre_phi, pre_built, after, benchmark, snapshot_check):
    model = after['wetland_model']
    state = EarthState.model_validate(after['environmental_state'])
    # Recomputing a saved canonical state must reproduce exactly, including lineage.
    if run_wetland(state, {k: model[k] for k in model_spec()}) != model:
        raise AssertionError('Saved state did not reproduce deterministic model output')
    if model['synthetic'] or any(r.synthetic for r in state.raw):
        raise AssertionError('Synthetic input reached a real-site verification run')
    raw_ids = {r.id for r in state.raw}
    obs_ids = {o.id for o in state.observations()}
    if any(set(o.raw_source_ids) - raw_ids or set(o.input_ids) - obs_ids for o in state.observations()):
        raise AssertionError('Unresolved provenance in real-site state')
    components = {c['key']: {k: c.get(k) for k in ('band', 'score', 'coverage', 'status', 'missing_inputs', 'supporting_evidence')}
                  for c in model['components'] if c['key'] != 'data_confidence'}
    selected = {v: state.get(v).model_dump(mode='json') for v in state.selected if state.get(v) is not None}
    physical = components['physical_potential']
    disagreements = []
    if benchmark['status'] == 'mapped_overlap':
        if model['overall']['band'] == 'INSUFFICIENT_DATA':
            disagreements.append('EA maps reconnection opportunity while CRC cannot rank restoration: ' + ', '.join(model['overall']['blocking_gaps']) + '. This is a missing-evidence discrepancy, not a low CRC prediction.')
        elif model['overall']['band'] == 'LOW':
            disagreements.append('EA reconnection geometry overlaps but CRC restoration index is low. Inspect current cover and constraints; the two products target different questions.')
    elif benchmark['status'] == 'no_mapped_overlap' and physical['band'] in ('HIGH', 'VERY_HIGH'):
        disagreements.append('No EA reconnection overlap but CRC physical component is high on available evidence. Active floodplain and reconnection opportunity are different concepts; incomplete physical component is not an established disagreement.')
    if feature['properties']['group'] == 'developed_comparison':
        developed = state.get('land_use.developed_fraction')
        if developed is None or developed.value is None:
            disagreements.append('Developed comparison cannot be checked: land-cover/development evidence unavailable.')
        elif developed.value < .5:
            disagreements.append('Mapped developed fraction is below half of this operational developed-site sample. Inspect source class definition, source age and sample geometry; do not assume land is freely restorable.')
    if pre_phi['wetland_model'] != pre_built['wetland_model']:
        raise AssertionError('PHI changed the legacy wetland result or evidence summary')
    if pre_phi['environmental_state'] != pre_built['environmental_state']:
        raise AssertionError('PHI entered or changed the legacy environmental state')
    if pre_phi['findings'] != [item for item in pre_built['findings']
                               if item['key'] != 'priority_habitats']:
        raise AssertionError('PHI changed an existing non-PHI finding')
    if pre_built['wetland_model'] != after['wetland_model']:
        raise AssertionError('Built-world evidence changed the legacy wetland result')
    if pre_built['environmental_state'] != after['environmental_state']:
        raise AssertionError('Built-world evidence entered or changed the legacy environmental state')
    if pre_built['findings'] != [item for item in after['findings']
                                 if item['key'] != 'built_world']:
        raise AssertionError('Built-world evidence changed an existing finding')
    projection = project_land_evidence(after)
    built_world = inspect_built_world(projection)
    developed = state.get('land_use.developed_fraction')
    infrastructure = state.get('human.infrastructure_fraction')
    if infrastructure is not None and infrastructure.value is not None:
        raise AssertionError('Built-world evidence populated legacy infrastructure input')
    return {'id': feature['id'], **feature['properties'], 'area_ha': after['area_ha'],
            'coverage': paired_coverage(before, after), 'before_band': before['wetland_model']['overall']['band'],
            'before_data_support_index': next(c['score'] for c in before['wetland_model']['components'] if c['key']=='data_confidence'),
            'after_band': model['overall']['band'], 'after_evidence': model['evidence_summary'],
            'components': components, 'benchmark': benchmark,
            'disagreements': disagreements or ['No qualitative discrepancy established; this is a desk inspection, not validation.'],
            'missing_inputs': model['missing_inputs'], 'review_flags': model['review_flags'],
            'selected_observations': selected, 'raw_sources': [r.model_dump(mode='json') for r in state.raw],
            'model_spec': {k: model[k] for k in model_spec()}, 'state_fingerprint': model['state_fingerprint'],
            'priority_habitats': inspect_priority_habitats(projection),
            'worldcover_built_up_fraction': (
                developed.value if developed is not None else None
            ),
            'built_world': built_world,
            'land_evidence_snapshot': snapshot_check,
            'wetland_phi_parity': 'exact',
            'wetland_built_world_parity': 'exact',
            'legacy_environmental_state_parity': 'exact',
            'non_phi_findings_parity': 'exact', 'non_built_findings_parity': 'exact',
            'deterministic_replay': 'passed', 'provenance_resolution': 'passed', 'synthetic': False}


def write_report(path, report):
    rows = report['sites']
    def number(v, places=1): return 'unknown' if v is None else f'{v:.{places}f}'
    lines = ['# Real Oxford parcel verification', '', f"Run: {report['run_id']} · {report['completed_at']}", '',
             'This is a purposive engineering inspection of real Oxford locations, not independent predictive validation. Site expectations were documented before results; no example labels become model inputs and no thresholds were fitted to these examples.', '',
             'Six features use actual Natural England SSSI reference geometries. Six are explicitly bounded sample windows at real developed/woodland locations, not legal property boundaries. All are inside the retained Oxford source coverage. The window coordinates and primary expectation sources are in `real-verification-sites.geojson`.', '',
             'The historical Port Meadow assessment `18054630-584d-473d-8d04-653c4f2ca268` reported 3.3/100 combined data support and INSUFFICIENT_DATA. That support index is not the percentage of available inputs. The optional habitat-proximity input is excluded from the required denominator. The before/after counts below apply the identical after-applicable input list to the old overlay-only evidence and new real evidence. The before replay uses the current deterministic formula without new acquisition, rather than rewriting historical saved output.', '',
             '| Site | WorldCover built-up % | OML buildings | OML building union % | Functional sites | Rail length within (m) | Track distance (m) | Station distance (m) | PHI mapped union % |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        phi=r['priority_habitats']; built=r['built_world']; obs=built['observations']
        building=obs['built.building.mapped_overlap_fraction']
        track_length=obs['transport.railway_track.mapped_length_within']
        track_distance=obs['transport.railway_track.distance_min']
        station_distance=obs['transport.railway_station.distance_min']
        lines.append(
            f"| {r['name']} | {number(None if r['worldcover_built_up_fraction'] is None else r['worldcover_built_up_fraction']*100,2)} | "
            f"{built['object_counts']['building']} | {number(None if building is None else building['value']*100,2)} | "
            f"{built['object_counts']['functional_site']} | {number(None if track_length is None else track_length['value'],2)} | "
            f"{number(None if track_distance is None else track_distance['value'],2)} | "
            f"{number(None if station_distance is None else station_distance['value'],2)} | "
            f"{number(None if phi['union_overlap_fraction'] is None else phi['union_overlap_fraction']*100,2)} |"
        )
    lines += ['', 'OpenMap Local mapped zeroes are source-and-scale observations, not claims that no real object exists. Railway tracks remain lines; their length is not converted to surface area. WorldCover and PHI remain independent evidence families and are not reconciled into the OpenMap measurements.', '',
              '## Benchmark interpretation', '',
              '[EA WWNP Floodplain Reconnection Potential](https://www.data.gov.uk/dataset/11873c69-d971-44ce-a648-872da9be847f/wwnp-floodplain-reconnection-potential) identifies possible reconnection, particularly currently poorly connected land near channels. It supplies binary geometry, not a high/low wetland opportunity class. A currently active floodplain can be physically wet and absent from this map. The benchmark is never fed into CRC scoring. Current land use, hydrology and consent still require site review.', '',
              f"Extract: {report['benchmark'].get('feature_count','unknown')} features; SHA-256 `{report['benchmark'].get('sha256','unavailable')}`. Raw originals are retained; {len(report['benchmark'].get('reference_repairs',[]))} invalid reference geometries require Shapely make_valid during intersection. Source creation 2017-09-01 and catalog revision 2024-05-31 are metadata dates, not parcel observation dates.", '',
              '## Site evidence and remaining gaps', '']
    for r in rows:
        built=r['built_world']; observations=built['observations']
        building=observations['built.building.mapped_overlap_fraction']
        functional=observations['built.functional_site.mapped_overlap_fraction']
        track=observations['transport.railway_track.mapped_length_within']
        track_distance=observations['transport.railway_track.distance_min']
        station_distance=observations['transport.railway_station.distance_min']
        sites=', '.join(
            ((item['distinctive_name'] + ' — ') if item['distinctive_name'] else '')
            + item['site_theme'] + ' / ' + item['classification']
            for item in built['functional_sites']
        ) or 'none mapped'
        lines += [f"### {r['name']}", '', r['expected_qualitative'], '',
                  'Expectation sources: '+', '.join(f'[primary source {i+1}]({u})' for i,u in enumerate(r['expectation_sources']))+'.', '',
                  f"OpenMap Local: parcel-object coverage {built['coverage_status']}; rail-distance search coverage {built['rail_distance_coverage_status']}; {built['object_counts']['building']} building objects with {number(None if building is None else building['value']*100,4)}% unioned parcel overlap; {built['object_counts']['functional_site']} functional-site objects ({sites}); {number(None if track is None else track['value'],3)} m unioned railway track length within; nearest mapped track {number(None if track_distance is None else track_distance['value'],3)} m; nearest mapped station {number(None if station_distance is None else station_distance['value'],3)} m; {built['relationship_count']} inspectable relationships.", '',
                  f"WorldCover mapped built-up fraction: {number(None if r['worldcover_built_up_fraction'] is None else r['worldcover_built_up_fraction']*100,2)}%. PHI mapped union: {number(None if r['priority_habitats']['union_overlap_fraction'] is None else r['priority_habitats']['union_overlap_fraction']*100,2)}%. These can disagree because their source semantics and resolutions differ.", '',
                  'Available physical reasons: '+'; '.join(r['components']['physical_potential'].get('supporting_evidence') or ['none'])+'.', '',
                  'Still missing applicable inputs: '+', '.join(r['coverage']['after_missing'])+'.', '',
                  'Inspection / discrepancies: '+' '.join(r['disagreements']), '']
    lines += ['## Reproduction and limits', '',
              'Run `.venv/bin/python scripts/verify_real_parcels.py` with the same database and environment as the worker. The script reads shared overlay datasets but creates no workspace sites or assessment database rows. Normal immutable acquisition artifacts and full before/pre-PHI/pre-built/after outputs are retained under `data/`. `real-verification-results.json` retains model signatures, exact object and relationship records, selected observations, source lineage, discrepancies and replay results.', '',
              'Every completed site passed deterministic replay, non-synthetic-input checks and raw/parent provenance resolution. Adding PHI and then OpenMap Local each left the complete legacy wetland result and bound environmental state exactly unchanged at every site. A PHI-era pre-built snapshot and a built-world-enriched snapshot were committed for every boundary; each old manifest was re-read after the new commit and remained byte-identical.', '',
              'These checks verify computation, not ecological truth. The examples share geography and data sources, include existing valuable habitats, and do not form a randomized holdout. PHI is an inventory rather than a current field survey: mapped zero is not ecological absence, mapped habitat is not a condition assessment, and no known-wetland label establishes restoration need or feasibility. The main scientific gaps are recorded explicitly per site.', '']
    path.write_text('\n'.join(lines))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sites', default='docs/real-verification-sites.geojson')
    parser.add_argument('--only', help='Comma-separated feature IDs')
    parser.add_argument('--run-id', default=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    parser.add_argument('--refresh', action='store_true')
    args=parser.parse_args()
    examples=json.loads(Path(args.sites).read_text())['features']
    if args.only: examples=[f for f in examples if f['id'] in args.only.split(',')]
    with engine.connect() as c:
        current_datasets=latest(c)
        dataset_ids=[r['id'] for r in current_datasets]
        pre_phi_dataset_ids=[r['id'] for r in current_datasets
                             if r['key'] not in ('priority_habitats', 'built_world')]
        pre_built_dataset_ids=[r['id'] for r in current_datasets
                               if r['key'] != 'built_world']
    if not dataset_ids: raise RuntimeError('Import the real shared overlay datasets first')
    output=ROOT/'verification'/args.run_id; output.mkdir(parents=True,exist_ok=True)
    try: benchmark=fetch_benchmark(ROOT/'environmental'/'benchmark',refresh=args.refresh)
    except Exception as error: benchmark={'status':'unavailable','error':str(error)}
    report={'run_id':args.run_id,'dataset_ids':dataset_ids,'benchmark':benchmark,'sites':[]}
    for f in examples:
        print(f"Assessing {f['id']}",flush=True)
        job={'id':f"verification-{args.run_id}-{f['id']}", 'site_id':f"verification-{f['id']}",
             'site_name':f['properties']['name'],'version':1,'geometry':boundary(f),
             'dataset_ids':dataset_ids,'created':datetime.now(timezone.utc).isoformat()}
        before=analyze(job|{'model_spec':model_spec(environment_version=None)})
        pre_phi=analyze(job|{'dataset_ids':pre_phi_dataset_ids,
                             'model_spec':model_spec(refresh_sources=args.refresh)})
        pre_built=analyze(job|{'dataset_ids':pre_built_dataset_ids,
                               'model_spec':model_spec(refresh_sources=args.refresh)})
        after=analyze(job|{'model_spec':model_spec(refresh_sources=args.refresh)})
        for label,result in [('before',before),('pre-phi',pre_phi),
                             ('pre-built',pre_built),('after',after)]:
            (output/f"{f['id']}-{label}.json").write_text(json.dumps(result,indent=2))
        prior_projection=project_land_evidence(pre_built)
        enriched_projection=project_land_evidence(after)
        prior_state=bind_wetland_input(prior_projection, job['geometry'])
        enriched_state=bind_wetland_input(enriched_projection, job['geometry'])
        if prior_state.model_dump(mode='json') != enriched_state.model_dump(mode='json'):
            raise AssertionError('Built-world evidence entered the legacy wetland binding')
        prior_snapshot=persist_land_evidence_snapshot(
            prior_projection, org='verification', site_id=job['site_id'],
        )
        prior_manifest=load_object(prior_snapshot.manifest_key)
        enriched_snapshot=persist_land_evidence_snapshot(
            enriched_projection, org='verification', site_id=job['site_id'],
        )
        if prior_snapshot.id == enriched_snapshot.id:
            raise AssertionError('Built-world evidence did not create a new immutable snapshot')
        if load_object(prior_snapshot.manifest_key) != prior_manifest:
            raise AssertionError('Prior snapshot manifest changed after built-world snapshot commit')
        if load_land_evidence_snapshot(enriched_snapshot.id, org='verification') != enriched_projection:
            raise AssertionError('Built-world snapshot round trip failed')
        snapshot_check={
            'pre_built_snapshot_id': prior_snapshot.id,
            'pre_built_content_hash': prior_snapshot.content_hash,
            'built_world_snapshot_id': enriched_snapshot.id,
            'built_world_content_hash': enriched_snapshot.content_hash,
            'new_snapshot': True,
            'prior_manifest_unchanged': True,
            'round_trip': 'passed',
        }
        overlap=(benchmark_overlap(job['geometry'],benchmark) if benchmark.get('sha256') else
                 {'status':'unknown','overlap_fraction':None,'reason':benchmark.get('error','Unavailable')})
        row=inspect_result(f,before,pre_phi,pre_built,after,overlap,snapshot_check)
        report['sites'].append(row)
        report['completed_at']=datetime.now(timezone.utc).isoformat()
        (output/'summary.json').write_text(json.dumps(report,indent=2))
        c=row['coverage'];print(f"{f['id']}: {c['before_available']}/{c['required']} -> {c['after_available']}/{c['required']} {row['after_band']}",flush=True)
    Path('docs/real-verification-results.json').write_text(json.dumps(report,indent=2))
    write_report(Path('docs/REAL-VERIFICATION.md'),report)
    print(f"Saved {len(report['sites'])} verified sites to docs/REAL-VERIFICATION.md",flush=True)


if __name__=='__main__': main()
