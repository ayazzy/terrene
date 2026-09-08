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
from backend.core import analyze, latest, engine, ROOT, boundary
from backend.earth import EarthState, fingerprint
from backend.wetland import model_spec, run_wetland


def paired_coverage(before, after):
    """Count identical variables in each pair, including condition if applicable."""
    variables = after['wetland_model']['evidence_summary']['gating_coverage']['variables']
    states = [EarthState.model_validate(r['environmental_state']) for r in (before, after)]
    counts = [sum(s.get(v) is not None and s.get(v).value is not None for v in variables) for s in states]
    return {'variables': variables, 'required': len(variables), 'before_available': counts[0],
            'after_available': counts[1], 'after_missing': [v for v in variables if states[1].get(v) is None or states[1].get(v).value is None]}


def inspect_result(feature, before, after, benchmark):
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
    return {'id': feature['id'], **feature['properties'], 'area_ha': after['area_ha'],
            'coverage': paired_coverage(before, after), 'before_band': before['wetland_model']['overall']['band'],
            'before_data_support_index': next(c['score'] for c in before['wetland_model']['components'] if c['key']=='data_confidence'),
            'after_band': model['overall']['band'], 'after_evidence': model['evidence_summary'],
            'components': components, 'benchmark': benchmark,
            'disagreements': disagreements or ['No qualitative discrepancy established; this is a desk inspection, not validation.'],
            'missing_inputs': model['missing_inputs'], 'review_flags': model['review_flags'],
            'selected_observations': selected, 'raw_sources': [r.model_dump(mode='json') for r in state.raw],
            'model_spec': {k: model[k] for k in model_spec()}, 'state_fingerprint': model['state_fingerprint'],
            'deterministic_replay': 'passed', 'provenance_resolution': 'passed', 'synthetic': False}


def write_report(path, report):
    rows = report['sites']
    def number(v, places=1): return 'unknown' if v is None else f'{v:.{places}f}'
    lines = ['# Real Oxford parcel verification', '', f"Run: {report['run_id']} · {report['completed_at']}", '',
             'This is a purposive engineering inspection of real Oxford locations, not independent predictive validation. Site expectations were documented before results; no example labels become model inputs and no thresholds were fitted to these examples.', '',
             'Six features use actual Natural England SSSI reference geometries. Six are explicitly bounded sample windows at real developed/woodland locations, not legal property boundaries. All are inside the retained Oxford flood-data corridor. The window coordinates and primary expectation sources are in `real-verification-sites.geojson`.', '',
             'The historical Port Meadow assessment `18054630-584d-473d-8d04-653c4f2ca268` reported 3.3/100 combined data support and INSUFFICIENT_DATA. That support index is not the percentage of available inputs. The optional habitat-proximity input is excluded from the required denominator. The before/after counts below apply the identical after-applicable input list to the old overlay-only evidence and new real evidence. The before replay uses the current deterministic formula without new acquisition, rather than rewriting historical saved output.', '',
             '| Site | Before required inputs | After required inputs | Overall | Physical component (coverage) | Slope ° | Water distance m | Developed % | EA reconnection overlap % |',
             '|---|---:|---:|---|---|---:|---:|---:|---:|']
    for r in rows:
        c=r['coverage']; p=r['components']['physical_potential']; obs=r['selected_observations']
        def value(v): return obs.get(v,{}).get('value')
        developed=value('land_use.developed_fraction'); b=r['benchmark'].get('overlap_fraction')
        lines.append(f"| {r['name']} | {c['before_available']}/{c['required']} | {c['after_available']}/{c['required']} | {r['after_band']} | {p['band']} ({100*p['coverage']:.0f}%; {p['status']}) | {number(value('terrain.slope_deg'),2)} | {number(value('hydrology.distance_to_water_m'))} | {number(None if developed is None else developed*100)} | {number(None if b is None else b*100,2)} |")
    lines += ['', 'Physical bands based on incomplete evidence are partial component descriptions; they do not unlock restoration rankings. Data quality is a heuristic about available source evidence. Model confidence remains UNVALIDATED.', '',
              '## Benchmark interpretation', '',
              '[EA WWNP Floodplain Reconnection Potential](https://www.data.gov.uk/dataset/11873c69-d971-44ce-a648-872da9be847f/wwnp-floodplain-reconnection-potential) identifies possible reconnection, particularly currently poorly connected land near channels. It supplies binary geometry, not a high/low wetland opportunity class. A currently active floodplain can be physically wet and absent from this map. The benchmark is never fed into CRC scoring. Current land use, hydrology and consent still require site review.', '',
              f"Extract: {report['benchmark'].get('feature_count','unknown')} features; SHA-256 `{report['benchmark'].get('sha256','unavailable')}`. Raw originals are retained; {len(report['benchmark'].get('reference_repairs',[]))} invalid reference geometries require Shapely make_valid during intersection. Source creation 2017-09-01 and catalog revision 2024-05-31 are metadata dates, not parcel observation dates.", '',
              '## Site evidence and remaining gaps', '']
    for r in rows:
        lines += [f"### {r['name']}", '', r['expected_qualitative'], '',
                  'Expectation sources: '+', '.join(f'[primary source {i+1}]({u})' for i,u in enumerate(r['expectation_sources']))+'.', '',
                  'Available physical reasons: '+'; '.join(r['components']['physical_potential'].get('supporting_evidence') or ['none'])+'.', '',
                  'Still missing applicable inputs: '+', '.join(r['coverage']['after_missing'])+'.', '',
                  'Inspection / discrepancies: '+' '.join(r['disagreements']), '']
    lines += ['## Reproduction and limits', '',
              'Run `.venv/bin/python scripts/verify_real_parcels.py` with the same database and environment as the worker. The script reads shared overlay datasets but creates no workspace sites or assessment database rows. Normal immutable acquisition artifacts and full before/after outputs are retained under `data/`. `real-verification-results.json` retains model signatures, exact counts, selected observations, source lineage, discrepancies and replay results.', '',
              'Every completed site passed deterministic replay, non-synthetic-input checks and raw/parent provenance resolution. These checks verify computation, not ecological truth. The examples share geography and data sources, include existing valuable habitats, and do not form a randomized holdout. No known-wetland label establishes current habitat condition or restoration need. The main scientific gaps are recorded explicitly per site.', '']
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
    with engine.connect() as c: dataset_ids=[r['id'] for r in latest(c)]
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
        after=analyze(job|{'model_spec':model_spec(refresh_sources=args.refresh)})
        for label,result in [('before',before),('after',after)]:
            (output/f"{f['id']}-{label}.json").write_text(json.dumps(result,indent=2))
        overlap=(benchmark_overlap(job['geometry'],benchmark) if benchmark.get('sha256') else
                 {'status':'unknown','overlap_fraction':None,'reason':benchmark.get('error','Unavailable')})
        row=inspect_result(f,before,after,overlap)
        report['sites'].append(row)
        report['completed_at']=datetime.now(timezone.utc).isoformat()
        (output/'summary.json').write_text(json.dumps(report,indent=2))
        c=row['coverage'];print(f"{f['id']}: {c['before_available']}/{c['required']} -> {c['after_available']}/{c['required']} {row['after_band']}",flush=True)
    Path('docs/real-verification-results.json').write_text(json.dumps(report,indent=2))
    write_report(Path('docs/REAL-VERIFICATION.md'),report)
    print(f"Saved {len(report['sites'])} verified sites to docs/REAL-VERIFICATION.md",flush=True)


if __name__=='__main__': main()
