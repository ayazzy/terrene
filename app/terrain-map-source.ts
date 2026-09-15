import type { Map } from 'maplibre-gl';
import type { TerrainPreview } from './terrain-preview';
export type TerrainRenderState = 'loading' | 'visible' | 'failed';
export const terrainSourcePrefix = 'terrene-terrain-';
/** Own exactly one image source/layer; restore on style replacement and fence disposal. */
export function mountTerrainSource(
  map: Map,
  preview: TerrainPreview,
  onState: (state: TerrainRenderState) => void,
  timeoutMs = 20000,
) {
  const id = terrainSourcePrefix + preview.preview_fingerprint;
  let disposed = false,
    failed = false;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const remove = () => {
    if (map.getLayer(id)) map.removeLayer(id);
    if (map.getSource(id)) map.removeSource(id);
  };
  const fail = () => {
    if (disposed || failed) return;
    failed = true;
    clearTimeout(timer);
    remove();
    onState('failed');
  };
  const ready = (event: { sourceId?: string }) => {
    if (disposed || failed || event.sourceId !== id || !map.getSource(id))
      return;
    if (map.isSourceLoaded(id)) {
      clearTimeout(timer);
      onState('visible');
    }
  };
  const error = (event: unknown) => {
    if (
      event &&
      typeof event === 'object' &&
      'sourceId' in event &&
      event.sourceId === id
    )
      fail();
  };
  const install = () => {
    if (disposed || failed) return;
    clearTimeout(timer);
    onState('loading');
    timer = setTimeout(fail, timeoutMs);
    try {
      if (!map.getSource(id))
        map.addSource(id, {
          type: 'image',
          url: 'data:image/png;base64,' + preview.image.data,
          coordinates: preview.grid.coordinates_wgs84 as [
            [number, number],
            [number, number],
            [number, number],
            [number, number],
          ],
        });
      if (disposed || failed) return;
      const source = map.getSource(id);
      if (source)
        source.attribution = preview.capture.attribution
          .replaceAll('&', '&amp;')
          .replaceAll('<', '&lt;')
          .replaceAll('>', '&gt;')
          .replaceAll('"', '&quot;')
          .replaceAll("'", '&#39;');
      if (!map.getLayer(id))
        map.addLayer(
          {
            id,
            type: 'raster',
            source: id,
            paint: {
              'raster-opacity': 1,
              'raster-resampling': 'nearest',
              'raster-fade-duration': 0,
            },
          },
          map
            .getStyle()
            .layers?.find(
              (layer) => layer.id.startsWith('terrene-') && layer.id !== id,
            )?.id,
        );
      ready({ sourceId: id });
    } catch {
      fail();
    }
  };
  map.on('style.load', install);
  map.on('sourcedata', ready);
  map.on('error', error);
  if (map.isStyleLoaded()) install();
  else {
    onState('loading');
    timer = setTimeout(fail, timeoutMs);
  }
  return () => {
    disposed = true;
    clearTimeout(timer);
    map.off('style.load', install);
    map.off('sourcedata', ready);
    map.off('error', error);
    remove();
  };
}
