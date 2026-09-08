'use client';

import { useState } from 'react';
import { Download, ArrowUpRight, Droplets } from 'lucide-react';
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from '@/components/ui/accordion';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet';

type Observation = {
  id: string;
  variable: string;
  value: number | string | null;
  unit: string;
  source: string;
  source_dataset: string;
  source_version: string;
  source_url?: string;
  timestamp: string | null;
  retrieved_at: string;
  method: string;
  observed_or_derived: string;
  epistemic_status: string;
  confidence: number;
  uncertainty: string;
  input_ids: string[];
  raw_source_ids: string[];
  missing_reason?: string;
  spatial: {
    geometry_or_cell_reference: string;
    crs: string;
    spatial_resolution_m: number | null;
    aggregation?: string;
  };
};
type Input = {
  variable: string;
  observation_id: string | null;
  value: number | string | null;
  source?: string;
  missing_reason?: string;
};
type Score = {
  key: string;
  label: string;
  score: number | null;
  confidence: number;
  coverage: number;
  status: string;
  rule: string;
  inputs: Input[];
  missing_inputs: string[];
  band?: string;
  supporting_evidence?: string[];
};
type Model = {
  current_state?: Record<
    string,
    {
      value: string | number | null;
      observation_id: string | null;
      timestamp: string | null;
    }
  >;
  evidence_summary?: {
    gating_coverage?: { available: number; required: number; fraction: number };
    data_coverage: { available: number; required: number; fraction: number };
    data_quality: { index: number | null; label: string; meaning: string };
    model_confidence: { label: string; meaning: string };
  };
  model_version: string;
  state_as_of: string;
  signature: string;
  components: Score[];
  overall: {
    score: number | null;
    band: string;
    confidence: number;
    confidence_label: string;
    rule: string;
    blocking_gaps: string[];
  };
  missing_inputs: { variable: string; reason: string; role: string }[];
  review_flags: string[];
  limitations: string;
  synthetic: boolean;
  config: object;
};
type Earth = {
  normalized: Record<string, Record<string, Observation[]>>;
  derived: Record<string, Observation>;
  selection_notes: Record<string, string>;
  raw: {
    id: string;
    source_dataset: string;
    storage_reference: string | null;
    checksum: string | null;
    raw_semantics: string;
  }[];
};
const bandText = (band: string) => band.replaceAll('_', ' ');
const legacyBand = (value: number | null) =>
  value === null
    ? 'INSUFFICIENT_DATA'
    : value >= 85
      ? 'VERY_HIGH'
      : value >= 65
        ? 'HIGH'
        : value >= 35
          ? 'MODERATE'
          : value >= 15
            ? 'LOW'
            : 'VERY_LOW';
const percent = (v: number) => Math.round(v * 100);
const valueText = (o: { value: number | string | null; unit?: string }) =>
  o.value === null
    ? 'Unknown'
    : typeof o.value === 'number'
      ? `${o.value.toLocaleString('en-GB', { maximumFractionDigits: 4 })}${o.unit ? ' ' + o.unit : ''}`
      : o.value;

export default function NaturePanel({
  model,
  earth,
  assessmentState,
  hasResult,
  error,
}: {
  model?: Model;
  earth?: Earth;
  assessmentState?: string;
  hasResult: boolean;
  error?: string;
}) {
  const [evidence, setEvidence] = useState<Observation | null>(null);
  if (!model || !earth)
    return (
      <div className="nature-panel">
        <p className="eyebrow">NATURE INTELLIGENCE</p>
        <h2>Wetland restoration</h2>
        {error && <p className="alert error">{error}</p>}
        <div className="nature-empty">
          <Droplets size={28} />
          <p>
            {hasResult
              ? 'This saved V0 assessment predates the wetland model. Run screening to create a new assessment; the original evidence will remain in history.'
              : ['queued', 'running'].includes(assessmentState || '')
                ? `Assessment ${assessmentState}. Environmental inputs and model results will appear here.`
                : 'Run screening to assess this parcel’s wetland potential, restoration need and constraints.'}
          </p>
        </div>
        <p className="nature-muted">
          Missing measurements stay unknown. No suitability scores are supplied
          by an LLM.
        </p>
      </div>
    );
  const observations = [
    ...Object.values(earth.normalized).flatMap((domain) =>
      Object.values(domain).flat(),
    ),
    ...Object.values(earth.derived),
  ];
  const byId = new Map(observations.map((o) => [o.id, o]));
  const overall = model.overall;
  const inspect = (id: string | null) => {
    if (id && byId.has(id)) setEvidence(byId.get(id)!);
  };
  function download() {
    const url = URL.createObjectURL(
      new Blob(
        [
          JSON.stringify(
            { wetland_model: model, environmental_state: earth },
            null,
            2,
          ),
        ],
        { type: 'application/json' },
      ),
    );
    const a = document.createElement('a');
    a.href = url;
    a.download = 'crc-wetland-evidence.json';
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <div className="nature-panel">
      <p className="eyebrow">NATURE INTELLIGENCE · V0.1</p>
      <h2>Wetland restoration</h2>
      <p className="nature-muted">First-pass suitability · England</p>
      {model.synthetic && (
        <div className="alert">Synthetic inputs · demonstration only</div>
      )}
      <div className={'nature-outcome ' + overall.band.toLowerCase()}>
        <span>Overall restoration opportunity</span>
        <strong>{overall.band.replaceAll('_', ' ').toLowerCase()}</strong>
        {model.evidence_summary ? (
          <>
            <p>
              Data coverage{' '}
              <b>
                {
                  (
                    model.evidence_summary.gating_coverage ||
                    model.evidence_summary.data_coverage
                  ).available
                }{' '}
                /{' '}
                {
                  (
                    model.evidence_summary.gating_coverage ||
                    model.evidence_summary.data_coverage
                  ).required
                }{' '}
                applicable scored inputs
              </b>
            </p>
            <p title={model.evidence_summary.data_quality.meaning}>
              Available data quality{' '}
              <b>{model.evidence_summary.data_quality.label}</b>
            </p>
            <p title={model.evidence_summary.model_confidence.meaning}>
              Model confidence{' '}
              <b>{model.evidence_summary.model_confidence.label}</b>
            </p>
          </>
        ) : (
          <p>
            Legacy combined data-support index: {percent(overall.confidence)} /
            100. This is not predictive accuracy.
          </p>
        )}
        {!!overall.blocking_gaps.length && (
          <p>
            An overall ranking remains unavailable. Inspect the component
            evidence below. Needed:{' '}
            {overall.blocking_gaps.join(', ').toLowerCase()}.
          </p>
        )}
      </div>
      <p className="nature-muted">
        Provisional rules, not a validated prediction. Open a component to
        inspect its calculation and evidence.
      </p>
      {model.current_state && (
        <div className="nature-muted">
          <p>
            Mapped land cover:{' '}
            <b>
              {String(
                model.current_state['land_use.current_cover']?.value ||
                  'Unknown',
              ).replaceAll('_', ' ')}
            </b>
            {model.current_state['land_use.current_cover']?.timestamp &&
              ` · reference year ${model.current_state['land_use.current_cover'].timestamp.slice(0, 4)}`}
          </p>
          <p>
            Actual wetland condition:{' '}
            <b>
              {model.current_state['ecology.habitat_condition']?.value === null
                ? 'Unknown — ecological survey needed'
                : 'Survey evidence available'}
            </b>
            . Mapped cover alone does not establish restoration need.
          </p>
        </div>
      )}
      <Accordion className="nature-scores" multiple>
        {model.components
          .filter((c) => c.key !== 'data_confidence')
          .map((c) => (
            <AccordionItem value={c.key} key={c.key}>
              <AccordionTrigger className="nature-score-trigger">
                <span>
                  <span>{c.label}</span>
                  <small>
                    {c.status === 'partial'
                      ? `Partial evidence · ${percent(c.coverage)}% input coverage`
                      : c.status === 'unknown'
                        ? 'Insufficient data'
                        : 'Provisional index'}
                  </small>
                </span>
                <b>{bandText(c.band || legacyBand(c.score))}</b>
              </AccordionTrigger>
              <AccordionContent className="nature-score-detail">
                <p>{c.rule}</p>
                {c.coverage < 1 && c.score !== null && (
                  <p className="alert">
                    This category describes available evidence only. Missing
                    inputs could change it.
                  </p>
                )}
                {!!c.supporting_evidence?.length && (
                  <ul>
                    {c.supporting_evidence.map((reason) => (
                      <li key={reason}>{reason}</li>
                    ))}
                  </ul>
                )}
                {c.score !== null && (
                  <details>
                    <summary>Inspect internal index</summary>
                    <p>
                      {c.score} / 100 · uncalibrated calculation, retained for
                      reproducibility.
                    </p>
                  </details>
                )}
                <p className="nature-muted">
                  Input coverage {percent(c.coverage)}% · Data support{' '}
                  {percent(c.confidence)} / 100 · not predictive accuracy
                </p>
                <ul className="nature-inputs">
                  {c.inputs.map((i) => (
                    <li key={i.variable}>
                      <button
                        disabled={!i.observation_id}
                        onClick={() => inspect(i.observation_id)}
                      >
                        <span>
                          <code>{i.variable}</code>
                          <small>
                            {valueText(i)} · {i.source || 'No source connected'}
                          </small>
                        </span>
                        {i.observation_id && <ArrowUpRight size={15} />}
                      </button>
                      {i.missing_reason && <p>{i.missing_reason}</p>}
                    </li>
                  ))}
                </ul>
              </AccordionContent>
            </AccordionItem>
          ))}
        <AccordionItem value="environment">
          <AccordionTrigger>
            All environmental observations ({observations.length})
          </AccordionTrigger>
          <AccordionContent>
            <p className="nature-muted">
              Includes terrain statistics, mapped land cover and source
              failures. Classification date may precede today; mapped wetland
              absence does not prove habitat absence.
            </p>
            <ul className="nature-inputs">
              {observations
                .filter((o) => o.source !== 'CRC')
                .map((o) => (
                  <li key={o.id}>
                    <button onClick={() => inspect(o.id)}>
                      <span>
                        <code>{o.variable}</code>
                        <small>
                          {valueText(o)} ·{' '}
                          {o.timestamp?.slice(0, 10) ||
                            'Observation date unknown'}
                        </small>
                      </span>
                      <ArrowUpRight size={15} />
                    </button>
                  </li>
                ))}
            </ul>
          </AccordionContent>
        </AccordionItem>
        <AccordionItem value="gaps">
          <AccordionTrigger>
            Missing inputs ({model.missing_inputs.length})
          </AccordionTrigger>
          <AccordionContent>
            <ul className="nature-gaps">
              {model.missing_inputs.map((g) => (
                <li key={g.variable}>
                  <code>{g.variable}</code>
                  <p>
                    {g.reason} <span className="nature-muted">{g.role}.</span>
                  </p>
                </li>
              ))}
            </ul>
          </AccordionContent>
        </AccordionItem>
        <AccordionItem value="review">
          <AccordionTrigger>Checks before intervention</AccordionTrigger>
          <AccordionContent>
            <ul className="nature-gaps">
              {model.review_flags.map((f) => (
                <li key={f}>{f}</li>
              ))}
            </ul>
          </AccordionContent>
        </AccordionItem>
        <AccordionItem value="method">
          <AccordionTrigger>Model method and limitations</AccordionTrigger>
          <AccordionContent>
            <p>{overall.rule}</p>
            <p>{model.limitations}</p>
            <p>Weights and thresholds used for this run:</p>
            <pre>{JSON.stringify(model.config, null, 2)}</pre>
            <p className="nature-muted">
              {model.model_version}
              <br />
              State snapshot:{' '}
              {new Date(model.state_as_of).toLocaleString('en-GB')}
              <br />
              No future-state simulation is implemented.
            </p>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
      <button className="nature-download" onClick={download}>
        <Download size={15} /> Download evidence JSON
      </button>
      <Sheet
        open={!!evidence}
        onOpenChange={(open) => !open && setEvidence(null)}
      >
        <SheetContent className="nature-evidence">
          <SheetHeader>
            <SheetTitle>Environmental evidence</SheetTitle>
            <SheetDescription>{evidence?.variable}</SheetDescription>
          </SheetHeader>
          {evidence && (
            <div className="nature-evidence-body">
              <h3>{valueText(evidence)}</h3>
              <p>
                {evidence.epistemic_status} · {evidence.observed_or_derived} ·
                Source quality judgement {percent(evidence.confidence)} / 100
              </p>
              {evidence.missing_reason && (
                <p className="alert">{evidence.missing_reason}</p>
              )}
              <dl>
                <dt>Source / dataset</dt>
                <dd>
                  {evidence.source} · {evidence.source_dataset}
                </dd>
                <dt>Source version</dt>
                <dd>
                  <code>{evidence.source_version}</code>
                </dd>
                <dt>Observation date</dt>
                <dd>
                  {evidence.timestamp ||
                    'Unknown — retrieval date is not an observation date'}
                </dd>
                <dt>Retrieved / computed</dt>
                <dd>{evidence.retrieved_at}</dd>
                <dt>Original resolution</dt>
                <dd>
                  {evidence.spatial.spatial_resolution_m === null
                    ? 'Unknown'
                    : evidence.spatial.spatial_resolution_m + ' m'}
                </dd>
                <dt>Spatial support</dt>
                <dd>
                  {evidence.spatial.geometry_or_cell_reference} ·{' '}
                  {evidence.spatial.crs}
                </dd>
                <dt>Aggregation</dt>
                <dd>{evidence.spatial.aggregation || 'None recorded'}</dd>
                <dt>Calculation</dt>
                <dd>{evidence.method}</dd>
                <dt>Uncertainty</dt>
                <dd>{evidence.uncertainty}</dd>
                {earth.selection_notes[evidence.variable] && (
                  <>
                    <dt>Provider selection</dt>
                    <dd>{earth.selection_notes[evidence.variable]}</dd>
                  </>
                )}
              </dl>
              {evidence.source_url && (
                <a href={evidence.source_url} target="_blank" rel="noreferrer">
                  Open source dataset ↗
                </a>
              )}
              {evidence.input_ids.length > 0 && (
                <>
                  <h4>Trace input evidence</h4>
                  {evidence.input_ids.map((id) => (
                    <button
                      className="nature-parent"
                      key={id}
                      onClick={() => inspect(id)}
                    >
                      {byId.get(id)?.variable || id}
                      <ArrowUpRight size={14} />
                    </button>
                  ))}
                </>
              )}
              <h4>Raw source references</h4>
              {evidence.raw_source_ids.map((id) => {
                const raw = earth.raw.find((r) => r.id === id);
                return (
                  <div key={id} className="nature-raw">
                    <b>{raw?.source_dataset || id}</b>
                    <p>{raw?.raw_semantics}</p>
                    <code>
                      {raw?.storage_reference || 'Snapshot unavailable'}
                    </code>
                    {raw?.checksum && (
                      <p>
                        SHA-256 <code>{raw.checksum}</code>
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}
