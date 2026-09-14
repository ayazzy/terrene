'use client';

import { Check, PenLine, Upload, X } from 'lucide-react';
import type { Geometry } from 'geojson';
import type { Ref } from 'react';

type Props = {
  editing: boolean;
  name: string;
  notes: string;
  stagedGeometry: Geometry | null;
  existingBoundaryLabel?: string;
  drawing: boolean;
  drawPointCount: number;
  busy: boolean;
  error: string;
  nameInputRef?: Ref<HTMLInputElement>;
  onNameChange: (value: string) => void;
  onNotesChange: (value: string) => void;
  onStartDrawing: () => void;
  onUndoDrawing: () => void;
  onFinishDrawing: () => void;
  onUpload: (file?: File) => void;
  onCancel: () => void;
  onSave: () => void;
};

export default function SiteEditorPanel({
  editing,
  name,
  notes,
  stagedGeometry,
  existingBoundaryLabel,
  drawing,
  drawPointCount,
  busy,
  error,
  nameInputRef,
  onNameChange,
  onNotesChange,
  onStartDrawing,
  onUndoDrawing,
  onFinishDrawing,
  onUpload,
  onCancel,
  onSave,
}: Props) {
  const title = editing ? 'Edit Site' : 'Add Site';
  const boundaryReady =
    !!stagedGeometry || (editing && !!existingBoundaryLabel);
  return (
    <aside
      className={`site-creation-panel${editing ? ' is-editing-site' : ''}`}
      data-map-reserved-surface="right"
      aria-label={`${title} workspace`}
    >
      <header>
        <span>
          <p className="eyebrow">{editing ? 'SITE SETTINGS' : 'NEW SITE'}</p>
          <h2>{title}</h2>
          <small>
            {editing
              ? 'Changes create a new saved boundary version.'
              : 'Define the Site while keeping its geographic context visible.'}
          </small>
        </span>
        <button
          type="button"
          className="icon-btn"
          aria-label={`Close ${title}`}
          onClick={onCancel}
        >
          <X size={16} />
        </button>
      </header>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          onSave();
        }}
      >
        <div className="site-creation-body">
          <label>
            <span>Site name</span>
            <input
              ref={nameInputRef}
              value={name}
              onChange={(event) => onNameChange(event.target.value)}
              placeholder="e.g. Lower Windrush meadow"
              maxLength={160}
            />
          </label>
          <label>
            <span>
              Notes <small>Optional</small>
            </span>
            <textarea
              value={notes}
              onChange={(event) => onNotesChange(event.target.value)}
              placeholder="Ownership, current use, questions to investigate…"
              maxLength={5000}
            />
          </label>

          <section
            className="site-boundary-step"
            aria-labelledby="site-boundary-title"
          >
            <div>
              <strong id="site-boundary-title">Boundary</strong>
              <small>WGS84 Polygon or MultiPolygon · required</small>
            </div>
            <div className="boundary-tools">
              <button
                type="button"
                aria-pressed={drawing}
                onClick={onStartDrawing}
              >
                <PenLine size={16} />
                {drawing
                  ? 'Drawing on map…'
                  : stagedGeometry
                    ? 'Redraw on map'
                    : 'Draw on map'}
              </button>
              <label className="upload-btn">
                <Upload size={16} /> Upload GeoJSON
                <input
                  type="file"
                  accept=".json,.geojson,application/geo+json,application/json"
                  onChange={(event) => onUpload(event.target.files?.[0])}
                />
              </label>
            </div>
            {drawing ? (
              <output className="boundary-drawing">
                <span>
                  {drawPointCount < 3
                    ? `Place ${3 - drawPointCount} more ${3 - drawPointCount === 1 ? 'vertex' : 'vertices'} on the map.`
                    : `${drawPointCount} vertices ready to finish.`}
                </span>
                <span className="boundary-drawing-actions">
                  <button
                    type="button"
                    disabled={!drawPointCount}
                    onClick={onUndoDrawing}
                  >
                    Undo
                  </button>
                  <button
                    type="button"
                    className="primary"
                    disabled={drawPointCount < 3}
                    onClick={onFinishDrawing}
                  >
                    Finish boundary
                  </button>
                </span>
              </output>
            ) : stagedGeometry ? (
              <output className="boundary-ready">
                <Check size={16} /> {stagedGeometry.type} staged for validation
              </output>
            ) : editing && existingBoundaryLabel ? (
              <output className="boundary-current">
                {existingBoundaryLabel} remains unchanged unless replaced.
              </output>
            ) : (
              <output className="boundary-required">
                Add a boundary to continue.
              </output>
            )}
            <p className="fineprint">
              Uploads are limited to 500 KB. Boundaries are validated on save
              and never silently repaired.
            </p>
          </section>

          {error && (
            <output className="alert error" aria-live="assertive">
              {error}
            </output>
          )}
        </div>

        <footer>
          <button type="button" onClick={onCancel}>
            Cancel
          </button>
          <button
            type="submit"
            className="primary"
            disabled={busy || !name.trim() || !boundaryReady}
          >
            {busy ? 'Saving…' : editing ? 'Save changes' : 'Save Site'}
          </button>
        </footer>
      </form>
    </aside>
  );
}
