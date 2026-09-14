'use client';

import { useState, type ReactNode } from 'react';
import { ArrowLeft, ArrowUpRight, Droplets } from 'lucide-react';
import type { Model } from './nature-panel';

const WETLAND_MODEL_VERSION = 'wetland_restoration_v0_1';

function modelState(model: Model | undefined, assessmentState?: string) {
  if (model) {
    return model.overall.band === 'INSUFFICIENT_DATA'
      ? 'Insufficient evidence'
      : model.overall.band.replaceAll('_', ' ').toLowerCase();
  }
  if (assessmentState === 'queued' || assessmentState === 'running')
    return `Assessment ${assessmentState}`;
  return 'No result for this assessment';
}

export default function SiteModelCatalogue({
  model,
  assessmentState,
  children,
}: {
  model?: Model;
  assessmentState?: string;
  children: ReactNode;
}) {
  const [selected, setSelected] = useState(false);

  if (selected)
    return (
      <div className="selected-model-workspace">
        <button
          type="button"
          className="model-catalogue-back text-btn"
          onClick={() => setSelected(false)}
        >
          <ArrowLeft size={14} /> Back to model catalogue
        </button>
        {children}
      </div>
    );

  const state = modelState(model, assessmentState);
  const resultState = model
    ? model.overall.band === 'INSUFFICIENT_DATA'
      ? 'is-warning'
      : 'is-available'
    : 'is-unavailable';

  return (
    <section
      className="model-catalogue"
      aria-labelledby="model-catalogue-title"
    >
      <header className="model-catalogue-heading">
        <p className="eyebrow">TERRENE REASONING</p>
        <h2 id="model-catalogue-title">Analytical models</h2>
        <p>
          Choose a versioned model to inspect its interpretation of this
          assessment’s retained evidence.
        </p>
      </header>
      <div className="model-catalogue-list" aria-label="Available models">
        <article className="model-catalogue-card">
          <div className="model-catalogue-card-heading">
            <span className="model-catalogue-icon" aria-hidden="true">
              <Droplets size={18} />
            </span>
            <span className={`model-catalogue-state ${resultState}`}>
              {state}
            </span>
          </div>
          <p className="context-kind">Nature intelligence</p>
          <h3>Wetland assessment</h3>
          <p>
            Separates physical potential, restoration need and implementation
            feasibility. Required evidence gaps prevent an overall result.
          </p>
          <dl>
            <div>
              <dt>Version</dt>
              <dd className="model-catalogue-version">
                {model?.model_version || WETLAND_MODEL_VERSION}
              </dd>
            </div>
            <div>
              <dt>Evidence state</dt>
              <dd className="model-catalogue-result-state">{state}</dd>
            </div>
          </dl>
          <button type="button" onClick={() => setSelected(true)}>
            Open model <ArrowUpRight size={15} />
          </button>
        </article>
      </div>
      <p className="model-catalogue-note">
        Model outputs are interpretations, not Terrene Earth facts or team
        decisions.
      </p>
    </section>
  );
}
