'use client';

import { useState } from 'react';
import {
  Download,
  ArrowUpRight,
  ArrowLeft,
  MapPin,
  Droplets,
} from 'lucide-react';
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from '@/components/ui/accordion';
import type { OverlayFinding } from './site-evidence';
import { EvidenceBadge } from './status-primitives';
import {
  humanize,
  variableLabel,
  observationState,
  observationValue,
  componentBand,
  linkedFindings,
} from './site-evidence';

export type Observation = {
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
  input_coverage?: number;
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
export type Model = {
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
export type Earth = {
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
const percent = (v: number) => Math.round(v * 100);
const valueText = observationValue;

export default function NaturePanel({
  model,
  earth,
  assessmentState,
  hasResult,
  error,
  section = 'overview',
  onSection,
  findings = [],
  onMapEvidence,
  onInspect,
}: {
  model?: Model;
  earth?: Earth;
  assessmentState?: string;
  hasResult: boolean;
  error?: string;
  section?: string;
  onSection?: (section: string) => void;
  findings?: OverlayFinding[];
  onMapEvidence?: (key: string) => void;
  onInspect?: () => void;
}) {
  const [evidence, setEvidence] = useState<Observation | null>(null);
  const [evidenceFilter, setEvidenceFilter] = useState('all');
  if (!model || !earth)
    return (
      <div className="nature-panel">
        <p className="eyebrow">NATURE INTELLIGENCE</p>
        <h2>Wetland investigation</h2>
        {error && <p className="alert error">{error}</p>}
        <div className="nature-empty">
          <Droplets size={28} />
          <p>
            {hasResult
              ? 'This saved V0 assessment predates the wetland model. Create a new assessment to run the current model; the original evidence will remain in history.'
              : ['queued', 'running'].includes(assessmentState || '')
                ? `Assessment ${assessmentState}. Environmental inputs and model results will appear here.`
                : 'Create a new assessment to inspect this parcel’s physical environment, ecological evidence and constraints.'}
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
    if (id && byId.has(id)) {
      setEvidence(byId.get(id)!);
      onInspect?.();
    }
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
  const componentKeys: Record<string, string[]> = {
    physical: ['physical_potential', 'hydrological_relevance'],
    ecology: ['restoration_need', 'ecological_opportunity'],
    constraints: ['implementation_feasibility'],
  };
  const coverage =
    model.evidence_summary?.gating_coverage ||
    model.evidence_summary?.data_coverage;
  const primary = [
    'physical_potential',
    'restoration_need',
    'implementation_feasibility',
  ];
  const titles: Record<string, string> = {
    physical_potential: 'Physical potential',
    restoration_need: 'Restoration need',
    implementation_feasibility: 'Implementation feasibility',
  };
  const destination: Record<string, string> = {
    physical_potential: 'physical',
    restoration_need: 'ecology',
    implementation_feasibility: 'constraints',
  };
  const domain =
    section === 'physical'
      ? ['terrain.', 'hydrology.', 'soil.']
      : section === 'ecology'
        ? ['ecology.', 'regulatory.', 'land_use.current_cover']
        : [
            'human.',
            'regulatory.',
            'ecology.irreplaceable_habitat_fraction',
            'land_use.developed_fraction',
          ];
  const observationRow = (o: Observation) => (
    <li key={o.id}>
      <button onClick={() => inspect(o.id)}>
        <span>
          <span>{variableLabel(o.variable)}</span>
          <small>
            {valueText(o)} · {o.source}
          </small>
        </span>
        <EvidenceBadge state={observationState(o)}>
          {observationState(o) === 'modelled' ? 'Derived' : observationState(o)}
        </EvidenceBadge>
      </button>
    </li>
  );
  return (
    <div className="nature-panel">
      {model.synthetic && (
        <div className="alert">Synthetic inputs · demonstration only</div>
      )}
      {!evidence && (
        <>
          {section === 'overview' && (
            <>
              <p className="eyebrow">WETLAND INVESTIGATION</p>
              <h2>Wetland assessment</h2>
              <p className="nature-muted">
                <b>Model unvalidated.</b> Physical characteristics do not
                establish restoration need.
              </p>
              <div className="analysis-dimensions">
                {primary.map((key) => {
                  const c = model.components.find((item) => item.key === key);
                  return (
                    c && (
                      <button
                        key={key}
                        onClick={() => onSection?.(destination[key])}
                      >
                        <span>
                          <small>{titles[key]}</small>
                          <strong>{componentBand(c)}</strong>
                        </span>
                        <span>
                          {c.score !== null && (
                            <EvidenceBadge
                              state={c.coverage < 1 ? 'partial' : 'modelled'}
                            >
                              {c.coverage < 1
                                ? 'Partial evidence'
                                : 'Provisional'}
                            </EvidenceBadge>
                          )}
                          <ArrowUpRight size={14} />
                        </span>
                      </button>
                    )
                  );
                })}
              </div>
              <button
                className="evidence-summary-link"
                onClick={() => onSection?.('evidence')}
              >
                <span>
                  <strong>
                    {coverage
                      ? coverage.available < coverage.required
                        ? 'Partial evidence'
                        : 'Required inputs present'
                      : 'Inspect evidence completeness'}
                  </strong>
                  <small>
                    {coverage
                      ? `${coverage.available} of ${coverage.required} required inputs present`
                      : 'Legacy assessment · detailed inputs retained'}{' '}
                    · inspect gaps
                  </small>
                </span>
                <ArrowUpRight size={16} />
              </button>
              <h3>Key observations</h3>
              <ul className="nature-inputs key-observations">
                {[
                  'terrain.slope_deg',
                  'hydrology.watercourse_intersection',
                  'hydrology.mapped_flood_extent_fraction',
                  'land_use.developed_fraction',
                ].map((variable) => {
                  const chosenId =
                    model.current_state?.[variable]?.observation_id;
                  const o =
                    (chosenId && byId.get(chosenId)) ||
                    observations.find(
                      (item) =>
                        item.variable === variable && item.source !== 'CRC',
                    );
                  return o ? observationRow(o) : null;
                })}
              </ul>
              {!!findings.filter(
                (f) =>
                  f.key !== 'flood' && f.measured !== null && f.measured > 0,
              ).length && (
                <p className="interpretation-note">
                  Mapped ecological designation or habitat overlaps this
                  boundary. Existing ecological value needs review before
                  considering intervention.
                </p>
              )}
              <p className="model-caution">
                <b>
                  Model{' '}
                  {humanize(
                    (
                      model.evidence_summary?.model_confidence.label ||
                      'unvalidated'
                    ).toLowerCase(),
                  )}
                </b>
                <br />
                {model.evidence_summary?.model_confidence.meaning ||
                  'No validated prediction or predictive accuracy is established.'}
              </p>
              <h3>Investigate next</h3>
              <ul className="investigation-next">
                {model.missing_inputs
                  .filter((g) => g.role !== 'optional')
                  .slice(0, 3)
                  .map((g) => (
                    <li key={g.variable}>
                      <button
                        className="text-btn"
                        onClick={() => onSection?.('evidence')}
                      >
                        {variableLabel(g.variable)} <ArrowUpRight size={13} />
                      </button>
                      <small>{g.reason}</small>
                    </li>
                  ))}
              </ul>
            </>
          )}
          {section !== 'overview' && (
            <>
              <p className="eyebrow">
                {section === 'evidence'
                  ? 'EVIDENCE REGISTER'
                  : 'ENVIRONMENTAL ANALYSIS'}
              </p>
              <h2>
                {section === 'physical'
                  ? 'Physical environment'
                  : section === 'ecology'
                    ? 'Ecology & restoration need'
                    : section === 'constraints'
                      ? 'Constraints & feasibility'
                      : 'Evidence & provenance'}
              </h2>
              <p className="nature-muted">
                {section === 'physical'
                  ? 'Terrain and mapped water context describe physical characteristics. They do not establish a reliable water supply.'
                  : section === 'ecology'
                    ? 'Mapped cover and designations do not establish habitat condition or restoration need.'
                    : section === 'constraints'
                      ? 'Development and incomplete constraint evidence must be assessed separately from physical potential.'
                      : 'Availability, source quality and model confidence are separate. Open an observation to trace its source.'}
              </p>
            </>
          )}
          {section === 'ecology' && model.current_state && (
            <p className="interpretation-note">
              Mapped cover:{' '}
              <b>
                {humanize(
                  String(
                    model.current_state['land_use.current_cover']?.value ??
                      'Unknown',
                  ),
                )}
              </b>
              . Habitat condition:{' '}
              <b>
                {model.current_state['ecology.habitat_condition']?.value == null
                  ? 'Evidence unavailable'
                  : String(
                      model.current_state['ecology.habitat_condition'].value,
                    )}
              </b>
              .
            </p>
          )}
          {componentKeys[section] && (
            <>
              <Accordion
                className="nature-scores"
                multiple
                defaultValue={componentKeys[section]}
              >
                {model.components
                  .filter((c) => componentKeys[section].includes(c.key))
                  .map((c) => (
                    <AccordionItem value={c.key} key={c.key}>
                      <AccordionTrigger className="nature-score-trigger">
                        <span>
                          {titles[c.key] || c.label}
                          <small>
                            {c.score === null
                              ? 'Insufficient evidence'
                              : c.coverage < 1
                                ? 'Partial evidence'
                                : 'Provisional rules'}{' '}
                            · {percent(c.coverage)}% input coverage
                          </small>
                        </span>
                        <b>{componentBand(c)}</b>
                      </AccordionTrigger>
                      <AccordionContent className="nature-score-detail">
                        {c.key === 'physical_potential' &&
                          !!c.supporting_evidence?.length && (
                            <ul className="supporting-reasons">
                              {c.supporting_evidence.map((reason) => (
                                <li key={reason}>{reason}</li>
                              ))}
                            </ul>
                          )}
                        {c.coverage < 1 && c.score !== null && (
                          <p className="interpretation-note">
                            This category describes available evidence only.
                            Missing inputs could change it.
                          </p>
                        )}
                        <ul className="nature-inputs">
                          {c.inputs.map((i) => (
                            <li key={i.variable}>
                              <button
                                disabled={
                                  !i.observation_id ||
                                  !byId.has(i.observation_id)
                                }
                                onClick={() => inspect(i.observation_id)}
                              >
                                <span>
                                  {variableLabel(i.variable)}
                                  <small>
                                    {i.observation_id &&
                                    byId.has(i.observation_id)
                                      ? valueText(byId.get(i.observation_id)!)
                                      : valueText(i)}
                                  </small>
                                </span>
                                <ArrowUpRight size={14} />
                              </button>
                              {i.missing_reason && <p>{i.missing_reason}</p>}
                            </li>
                          ))}
                        </ul>
                        <details className="method-detail">
                          <summary>Calculation & internal index</summary>
                          <p>{c.rule}</p>
                          <p>
                            {c.score === null
                              ? 'Index unavailable'
                              : `${c.score} / 100 · uncalibrated internal index`}
                            . Data support {percent(c.confidence)} / 100; not
                            predictive accuracy.
                          </p>
                        </details>
                      </AccordionContent>
                    </AccordionItem>
                  ))}
              </Accordion>
              <details className="domain-observations">
                <summary>All observations in this section</summary>
                <ul className="nature-inputs">
                  {observations
                    .filter((o) =>
                      domain.some((prefix) => o.variable.startsWith(prefix)),
                    )
                    .map(observationRow)}
                </ul>
              </details>
            </>
          )}
          {section === 'constraints' && (
            <>
              <h3>Checks before intervention</h3>
              <ul className="nature-gaps">
                {model.review_flags.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
            </>
          )}
          {section === 'evidence' && (
            <>
              <div className="evidence-completeness">
                <EvidenceBadge
                  state={
                    coverage && coverage.available === coverage.required
                      ? 'available'
                      : 'partial'
                  }
                >
                  {coverage && coverage.available === coverage.required
                    ? 'Required inputs present'
                    : 'Partial evidence'}
                </EvidenceBadge>
                <p>
                  {coverage &&
                    `${coverage.available} of ${coverage.required} required inputs present. `}
                  Presence alone does not establish complete spatial coverage.
                </p>
              </div>
              <h3>Evidence gaps · {model.missing_inputs.length}</h3>
              <p className="nature-muted">
                Includes scored inputs and unassessed context. The
                required-input count above comes from the model’s completeness
                gate.
              </p>
              <ul className="nature-gaps">
                {model.missing_inputs.map((g) => (
                  <li key={g.variable}>
                    <div className="gap-title">
                      <strong>{variableLabel(g.variable)}</strong>
                      <EvidenceBadge state="missing">Missing</EvidenceBadge>
                    </div>
                    <p>{g.reason}</p>
                    <small>
                      {g.variable === 'ecology.distance_to_habitat_m'
                        ? 'Optional scored input'
                        : humanize(g.role)}
                    </small>
                  </li>
                ))}
              </ul>
              <h3>Environmental observations · {observations.length}</h3>
              <label className="evidence-filter">
                Show{' '}
                <select
                  value={evidenceFilter}
                  onChange={(e) => setEvidenceFilter(e.target.value)}
                >
                  <option value="all">All observations</option>
                  <option value="available">Available observations</option>
                  <option value="modelled">Derived observations</option>
                  <option value="partial">Partial observations</option>
                  <option value="unavailable">Unavailable observations</option>
                </select>
              </label>
              <ul className="nature-inputs">
                {observations
                  .filter(
                    (o) =>
                      evidenceFilter === 'all' ||
                      observationState(o) === evidenceFilter,
                  )
                  .map(observationRow)}
              </ul>
              {!observations.some(
                (o) =>
                  evidenceFilter === 'all' ||
                  observationState(o) === evidenceFilter,
              ) && (
                <p className="nature-muted">
                  No observations in this category.
                </p>
              )}
              <Accordion multiple>
                <AccordionItem value="method">
                  <AccordionTrigger>
                    Model, source quality & limitations
                  </AccordionTrigger>
                  <AccordionContent>
                    <p>{overall.rule}</p>
                    <p>{model.limitations}</p>
                    <p>
                      Available data quality:{' '}
                      {model.evidence_summary?.data_quality.label ||
                        'Not recorded'}
                      . {model.evidence_summary?.data_quality.meaning}
                    </p>
                    <p>
                      Model confidence:{' '}
                      {model.evidence_summary?.model_confidence.label ||
                        'Unvalidated'}
                      . {model.evidence_summary?.model_confidence.meaning}
                    </p>
                    <p>
                      {model.model_version} ·{' '}
                      {new Date(model.state_as_of).toLocaleString('en-GB')}
                    </p>
                    <p>Weights and thresholds retained for this run:</p>
                    <pre>{JSON.stringify(model.config, null, 2)}</pre>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
              <button className="nature-download" onClick={download}>
                <Download size={15} /> Download evidence JSON
              </button>
            </>
          )}
        </>
      )}
      {evidence && (
        <section
          className="inline-evidence"
          aria-label="Environmental evidence detail"
        >
          <button
            className="back"
            onClick={() => {
              setEvidence(null);
              onInspect?.();
            }}
          >
            <ArrowLeft size={14} /> Back to {section}
          </button>
          <h2>{variableLabel(evidence.variable)}</h2>
          <p className="nature-muted">
            <code>{evidence.variable}</code>
          </p>
          {evidence && (
            <div className="nature-evidence-body">
              <h3>{valueText(evidence)}</h3>
              <div
                className="evidence-status-line"
                aria-label="Evidence status"
              >
                <span>{humanize(evidence.epistemic_status)}</span>
                <span>{humanize(evidence.observed_or_derived)}</span>
                <span>Source quality {percent(evidence.confidence)} / 100</span>
              </div>
              {evidence.missing_reason && (
                <p className="alert">{evidence.missing_reason}</p>
              )}
              <div className="evidence-map-links">
                {linkedFindings(evidence, findings)
                  .filter((f) => f.geometry)
                  .map((f) => (
                    <button key={f.key} onClick={() => onMapEvidence?.(f.key)}>
                      <MapPin size={14} /> Show {f.dataset} on map
                    </button>
                  ))}
                {!linkedFindings(evidence, findings).some(
                  (f) => f.geometry,
                ) && (
                  <p className="nature-muted">
                    {linkedFindings(evidence, findings).length
                      ? 'No overlap geometry retained for this observation.'
                      : 'Parcel observation · no displayable map layer in this assessment.'}
                  </p>
                )}
              </div>
              <dl className="evidence-summary">
                <dt>Source</dt>
                <dd>
                  {evidence.source} · {evidence.source_dataset}
                </dd>
                <dt>Observation date</dt>
                <dd>
                  {evidence.timestamp ||
                    'Unknown — retrieval date is not an observation date'}
                </dd>
                <dt>Resolution</dt>
                <dd>
                  {evidence.spatial.spatial_resolution_m === null
                    ? 'Unknown'
                    : evidence.spatial.spatial_resolution_m + ' m'}
                </dd>
              </dl>
              {evidence.source_url && (
                <a href={evidence.source_url} target="_blank" rel="noreferrer">
                  Open source dataset ↗
                </a>
              )}
              <details className="technical-provenance">
                <summary>Technical provenance</summary>
                <dl>
                  <dt>Source version</dt>
                  <dd>
                    <code>{evidence.source_version}</code>
                  </dd>
                  <dt>Retrieved / computed</dt>
                  <dd>{evidence.retrieved_at}</dd>
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
              </details>
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
              {!!evidence.raw_source_ids.length && (
                <details className="raw-provenance">
                  <summary>
                    Raw source references · {evidence.raw_source_ids.length}
                  </summary>
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
                </details>
              )}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
