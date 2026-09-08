"""One narrow pipeline; model implementations consume EarthState only."""
import html

from backend.adapters import normalize_findings
from backend.derived import compute_features
from backend.wetland import MODEL_VERSION, run_wetland

MODELS = {MODEL_VERSION: run_wetland}


def assess_nature(job, findings):
    state = normalize_findings(job, findings)
    if ((job.get('model_spec') or {}).get('environment_version') and
            not any(f.get('synthetic', False) for f in findings)):
        from backend.environment import enrich_state
        state = enrich_state(state, job, refresh=job['model_spec'].get('refresh_sources', False))
    state = compute_features(state)
    spec = job.get('model_spec')
    version = spec['model_version'] if spec else MODEL_VERSION
    if version not in MODELS:
        raise ValueError('Unsupported pinned model version: ' + version)
    return {'environmental_state': state.model_dump(mode='json'),
            'wetland_model': MODELS[version](state, spec)}


def model_report(result):
    """Export the saved result, never silently recompute a historical report."""
    model = result.get('wetland_model')
    if not model:
        return '<section><h2>Wetland model</h2><p>This historical V0 assessment predates the wetland model. Run a new assessment to obtain model results.</p></section>'
    esc = lambda value: html.escape(str(value))
    overall = model['overall']
    body = f'<section><h2>Wetland restoration model</h2><p>{esc(model["model_version"])} · {esc(overall["band"].replace("_", " "))} · Legacy data-support index {round(overall["confidence"]*100)}% ({esc(overall["confidence_label"])})</p><p>{esc(model["limitations"])}</p>'
    if model['synthetic']:
        body += '<p><b>SYNTHETIC INPUTS: this result is a demonstration, not a real-site assessment.</b></p>'
    if model.get('evidence_summary'):
        evidence = model['evidence_summary']
        coverage = evidence['data_coverage']
        body += f"<p>Data coverage: {coverage['available']} / {coverage['required']} applicable scored inputs. Available data quality: {esc(evidence['data_quality']['label'])}. Model confidence: UNVALIDATED.</p>"
    body += '<details><summary>Internal overall index (uncalibrated)</summary><p>' + ('Unknown' if overall['score'] is None else esc(overall['score']) + ' / 100') + '</p><p>' + esc(overall['rule']) + '</p></details>'
    for component in model['components']:
        body += f'<h3>{esc(component["label"])}: {"Unknown" if component["score"] is None else esc(component.get("band", "Internal index " + str(component["score"])).replace("_", " "))}</h3><p>{esc(component["rule"])}<br>Input coverage {round(component["coverage"]*100)}% · data support {round(component["confidence"]*100)}% (not predictive accuracy)</p>'
        body += '<ul>' + ''.join(f'<li>{esc(i["variable"])}: {esc(i.get("value"))} · source {esc(i.get("source"))} · evidence {esc(i.get("observation_id"))}</li>' for i in component['inputs']) + '</ul>'
    body += '<h3>Missing inputs and review</h3><ul>' + ''.join('<li>'+esc(g['variable']+': '+g['reason'])+'</li>' for g in model['missing_inputs']) + ''.join('<li>'+esc(f)+'</li>' for f in model['review_flags']) + '</ul>'
    body += '<details><summary>Complete model configuration and provenance</summary><pre style="white-space:pre-wrap;overflow-wrap:anywhere">'
    import json
    body += esc(json.dumps({'model': model, 'environmental_state': result['environmental_state']}, indent=2)) + '</pre></details></section>'
    return body
