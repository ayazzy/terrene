"""Self-contained HTML from the stored screening result and current team state."""
import html
import json

from backend.module_runs import ModuleRunRecord
from backend.screening_context import ScreeningResult


def screening_context_report(run: ModuleRunRecord, *, assessment_id: str,
                             site_name: str, review_status: str, current_version: int) -> str:
    result = ScreeningResult.model_validate(run.result)
    esc = lambda value: html.escape(str(value), quote=True)

    def refs(references):
        return '<p class="refs">Evidence: ' + ' · '.join(
            f'<a href="#{esc(ref)}">{esc(ref)}</a>'
            for values in references.model_dump().values() for ref in values
        ) + '</p>'

    def value(fact):
        if fact.value.kind == 'distribution':
            return '; '.join(f'{e.category}: {e.value}' for e in fact.value.entries) + ' (fractions)'
        return str(fact.value.value) + ' ' + fact.unit

    body = f'<h1>Terrene · Screening context</h1><h2>{esc(site_name)}</h2>'
    body += '<p>Calculated human-review context · no site-progression recommendation.</p>'
    body += (f'<section><h2>Current team review status at export</h2><p>{esc(review_status)}</p>'
             '<p>Mutable operational state, separate from the immutable calculated context. '
             'This is not the historical review status at assessment time.</p></section>')
    body += (f'<p>Assessment {esc(assessment_id)}<br>Boundary v{result.boundary_version} '
             f'· current site boundary v{current_version}<br>Run {esc(run.id)}<br>'
             f'Run content hash {esc(run.content_hash)}<br>Snapshot {esc(result.evidence_snapshot_id)}<br>'
             f'Evidence content hash {esc(result.evidence_content_hash)}<br>'
             f'Boundary fingerprint {esc(result.boundary_geometry_fingerprint)}<br>'
             f'{esc(result.model_version)} · {esc(result.input_binding_version)}<br>'
             f'Rules/configuration signature {esc(result.signature)}</p>')
    for group in result.groups:
        body += f'<section><h2>{esc(group.label)}</h2><h3>Source-bounded facts</h3>'
        if not group.facts:
            body += '<p>No source-backed observations retained for this group; this is not mapped zero.</p>'
        for fact in group.facts:
            body += (f'<article id="{esc(fact.id)}"><h4>{esc(fact.label)}</h4>'
                     f'<p>{esc(value(fact))} · {esc(fact.availability)}'
                     f'{" · known source-bounded zero" if fact.known_zero else ""}</p>'
                     f'<p>{esc(fact.limitations)}</p>{refs(fact.references)}'
                     '<details><summary>Definition, support and provenance</summary><pre>'
                     f'{esc(fact.model_dump_json(indent=2))}</pre></details></article>')
        body += '<h3>Evidence gaps</h3>'
        if not group.gaps:
            body += '<p>No explicit gaps recorded in this group; evidence completeness is not established.</p>'
        for gap in group.gaps:
            body += (f'<article id="{esc(gap.id)}"><h4>{esc(gap.definition_id or gap.legacy_variable or gap.reason_code)}</h4>'
                     f'<p>{esc(gap.state)} · {esc(gap.reason_code)}</p><p>{esc(gap.reason)}</p>'
                     f'<pre>{esc(gap.model_dump_json(indent=2))}</pre></article>')
        body += '</section>'
    for title, items in (
        ('Mapped-zero qualifications', result.mapped_zero_qualifications),
        ('Source-semantic context', result.cross_source_contexts),
        ('Unresolved human-review questions', result.review_questions),
    ):
        body += f'<section><h2>{title}</h2>'
        for item in items:
            body += f'<article><h3>{esc(item.label)}</h3><p>{esc(item.text)}</p>{refs(item.references)}</article>'
        body += '</section>'
    body += '<section><h2>Registered but unconnected capabilities</h2>'
    for capability in result.unconnected_capabilities:
        body += (f'<article id="{esc(capability.legacy_variable)}"><h3>{esc(capability.legacy_variable)}</h3>'
                 f'<p>{esc(capability.disposition)} · {esc(capability.note)}</p></article>')
    body += '</section>'
    body += '<section><h2>Limitations</h2><ul>' + ''.join(f'<li>{esc(x)}</li>' for x in result.limitations) + '</ul></section>'
    body += '<section><h2>Evidence and provenance catalogue</h2>'
    for title, records in (
        ('Sources', result.sources), ('Raw references (private locations omitted)', result.raw_references),
        ('Source features', result.source_features), ('Mapped objects', result.objects),
        ('Parcel relationships', result.relationships),
    ):
        body += f'<h3>{title}</h3>'
        for record in records:
            body += f'<details id="{esc(record.id)}"><summary>{esc(record.id)}</summary><pre>{esc(record.model_dump_json(indent=2))}</pre></details>'
    body += '<details><summary>Complete stored semantic result</summary><pre>' + esc(json.dumps(run.result, indent=2, ensure_ascii=False)) + '</pre></details></section>'
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>Terrene screening context</title><style>'
            'body{font:16px/1.6 system-ui;max-width:960px;margin:32px auto;padding:0 20px;color:#183b36}'
            'section{border-top:1px solid #ccd5d2;margin-top:24px}article{margin:20px 0}'
            'pre{white-space:pre-wrap}p,pre,a,summary{overflow-wrap:anywhere}summary{cursor:pointer}'
            '.refs{font-size:13px}a{color:#166853}@media print{body{margin:0}details{display:block}@page{margin:18mm}}'
            '</style></head><body>' + body + '</body></html>')
