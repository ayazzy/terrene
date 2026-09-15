'use client';
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from 'react';
import type { Map } from 'maplibre-gl';
import type { Geometry } from 'geojson';
import { readCaptureCatalogue } from './acquisitions';
import { readTerrainPreview, type TerrainPreview } from './terrain-preview';
import { createTerrainLayer } from './terrain-layer-state';
import {
  mountTerrainSource,
  type TerrainRenderState,
} from './terrain-map-source';
import styles from './terrain-map-layer.module.css';

export function useTerrainMapLayer(map: Map | null) {
  const controller = useMemo(
    () =>
      createTerrainLayer({
        catalogue: readCaptureCatalogue,
        preview: readTerrainPreview,
      }),
    [],
  );
  const state = useSyncExternalStore(
    controller.subscribe,
    controller.getSnapshot,
    controller.getSnapshot,
  );
  const [render, setRender] = useState<TerrainRenderState>('loading');
  const token = useRef<string | null | undefined>(undefined);
  useEffect(() => () => controller.dispose(), [controller]);
  // React updates cover in-app sign-in; focus/storage cover other-document changes.
  useEffect(() => {
    const check = () => {
      const current = sessionStorage.getItem('crc-token');
      if (token.current !== undefined && token.current !== current)
        controller.reset();
      token.current = current;
    };
    check();
    window.addEventListener('focus', check);
    window.addEventListener('storage', check);
    return () => {
      window.removeEventListener('focus', check);
      window.removeEventListener('storage', check);
    };
  });
  useEffect(() => {
    if (
      !map ||
      !state.shown ||
      !state.preview ||
      state.preview.grid.state === 'no_visible_samples'
    )
      return;
    return mountTerrainSource(map, state.preview, setRender);
  }, [map, state.preview, state.shown]);
  return { state, controller, render };
}
type TerrainControl = ReturnType<typeof useTerrainMapLayer>;
const date = (value: string) =>
  new Date(value).toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'UTC',
  });
const elevation = (value: number | null) =>
  value === null ? 'No valid elevation' : `${value.toFixed(2)} m`;

export function TerrainLegend({ preview }: { preview: TerrainPreview }) {
  const constant =
    preview.legend.minimum_elevation_m === preview.legend.maximum_elevation_m;
  return (
    <section className={styles.legend} aria-label="Terrain elevation legend">
      <strong>Terrain elevation · metres ODN</strong>
      {preview.native.valid_cell_count > 0 ? (
        <>
          <div
            className={styles.ramp}
            style={constant ? { background: 'rgb(128,128,128)' } : undefined}
          />
          <div className={styles.range}>
            <span>{elevation(preview.legend.minimum_elevation_m)}</span>
            <span>{elevation(preview.legend.maximum_elevation_m)}</span>
          </div>
        </>
      ) : (
        <p>No valid native elevation cells.</p>
      )}
      <p>
        Local elevation range. Transparent areas are missing or outside the
        request. Preview colours are not measurements.
      </p>
      <small>Survey dates unknown · historical composite</small>
      <small>{preview.capture.attribution}</small>
    </section>
  );
}

export function TerrainLayerControls({
  terrain,
  map,
  onFit,
}: {
  terrain: TerrainControl;
  map: Map | null;
  onFit: (geometry: Geometry) => void;
}) {
  const { state, controller, render } = terrain;
  const search = (all = false) => {
    const b = map?.getBounds();
    if (!all && !b) return;
    void controller.search({
      source_id: 'environment_agency.lidar_dtm_1m',
      time_basis: 'capture',
      limit: 10,
      ...(!all && b
        ? {
            bbox: [
              Math.max(-180, b.getWest()),
              Math.max(-90, b.getSouth()),
              Math.min(180, b.getEast()),
              Math.min(90, b.getNorth()),
            ].join(','),
          }
        : {}),
    });
  };
  const preview = state.preview;
  return (
    <section className={styles.controls} aria-label="Independent terrain">
      <h3>Terrain · independent captures</h3>
      <p>Retained LiDAR terrain, separate from the saved assessment.</p>
      <div className={styles.actions}>
        <button disabled={!map} onClick={() => search()}>
          Search this view
        </button>
        <button onClick={() => search(true)}>Browse all terrain</button>
      </div>
      {state.query && (
        <small>
          {state.query.bbox
            ? 'Search area fixed at the last view searched.'
            : 'All retained terrain locations.'}
        </small>
      )}
      {state.listStatus === 'loading' && (
        <output>Finding retained terrain…</output>
      )}
      {state.listStatus === 'error' && <p role="alert">{state.listError}</p>}
      {!state.selected && state.previewStatus === 'error' && (
        <p role="alert">{state.previewError}</p>
      )}
      {state.listStatus === 'error' && state.query && (
        <button
          onClick={() =>
            void (state.page?.next_cursor
              ? controller.more()
              : controller.search(state.query!))
          }
        >
          Retry terrain search
        </button>
      )}
      {state.listStatus === 'ready' && !state.entries.length && (
        <output>
          {state.page?.next_cursor
            ? 'No matches in this batch. More captures can be checked.'
            : 'No retained terrain matches this search. This does not establish missing terrain data.'}
        </output>
      )}
      {!!state.entries.length && (
        <ul className={styles.captures} aria-label="Terrain captures">
          {state.entries.map((c) => (
            <li key={c.acquisition_id + ':' + c.attempt_id}>
              <button
                aria-pressed={
                  state.selected?.acquisition_id === c.acquisition_id &&
                  state.selected?.attempt_id === c.attempt_id
                }
                onClick={() => void controller.select(c)}
              >
                <strong>EA terrain · {c.acquisition_id.slice(0, 8)}</strong>
                <small>Captured {date(c.capture_completed)} UTC</small>
                <small>Survey dates unknown · 1 m native grid</small>
              </button>
            </li>
          ))}
        </ul>
      )}
      {state.page?.next_cursor && (
        <button
          disabled={state.listStatus === 'loading'}
          onClick={() => void controller.more()}
        >
          Check more terrain captures
        </button>
      )}
      {state.selected && (
        <div className={styles.selection}>
          <strong>
            Selected terrain · {state.selected.acquisition_id.slice(0, 8)}
          </strong>
          <div className={styles.actions}>
            <label>
              <input
                type="checkbox"
                checked={state.shown}
                onChange={(e) => controller.show(e.target.checked)}
              />
              Show terrain
            </label>
            <button onClick={() => controller.clear()}>Remove terrain</button>
          </div>
          {state.previewStatus === 'loading' && (
            <output>Verifying terrain files…</output>
          )}
          {state.previewStatus === 'error' && (
            <p role="alert">{state.previewError}</p>
          )}
          {state.previewStatus === 'error' && (
            <button onClick={() => void controller.select(state.selected!)}>
              Retry terrain preview
            </button>
          )}
          {preview && (
            <>
              <output>
                {!state.shown
                  ? 'Terrain hidden.'
                  : preview.grid.state === 'no_visible_samples'
                    ? 'No visible samples at preview resolution. Check native availability below.'
                    : render === 'failed'
                      ? 'Terrain could not render. It is unavailable, not empty.'
                      : render === 'visible'
                        ? 'Terrain layer on · files verified.'
                        : 'Loading terrain image…'}
              </output>
              {render === 'failed' && state.shown && (
                <button onClick={() => void controller.select(state.selected!)}>
                  Retry terrain rendering
                </button>
              )}
              <button
                onClick={() => onFit(preview.requested_geometry as Geometry)}
              >
                Fit terrain extent
              </button>
              <p>
                {preview.native.valid_cell_count.toLocaleString('en-GB')} /{' '}
                {preview.native.area_cell_count.toLocaleString('en-GB')} native
                cells available.
              </p>
              <small>
                Preview {preview.grid.width} × {preview.grid.height} pixels ·
                original 1 m grid retained
              </small>
              <TerrainLegend preview={preview} />
              <details>
                <summary>Source and capture references</summary>
                <p>Environment Agency · {preview.capture.licence}</p>
                <p>Captured {date(preview.capture.capture_completed)} UTC</p>
                <dl>
                  <dt>Capture</dt>
                  <dd>{preview.capture.acquisition_id}</dd>
                  <dt>Attempt</dt>
                  <dd>{preview.capture.attempt_id}</dd>
                  <dt>Source raster SHA-256</dt>
                  <dd>{preview.capture.native_raster_sha256}</dd>
                </dl>
                <p>
                  Display only. Small features may disappear at preview
                  resolution. No new assessment, height or flood result.
                </p>
              </details>
            </>
          )}
        </div>
      )}
    </section>
  );
}
