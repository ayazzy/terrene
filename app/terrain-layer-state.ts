import type { Capture, CaptureCatalogue, CaptureQuery } from './acquisitions';
import type { TerrainPreview } from './terrain-preview';
type Phase = 'idle' | 'loading' | 'ready' | 'error';
export type TerrainLayerState = {
  entries: Capture[];
  page: CaptureCatalogue | null;
  query: CaptureQuery | null;
  listStatus: Phase;
  listError: string;
  selected: Capture | null;
  preview: TerrainPreview | null;
  previewStatus: Phase;
  previewError: string;
  shown: boolean;
};
type Readers = {
  catalogue: (
    query: CaptureQuery,
    cursor: string | undefined,
    signal: AbortSignal,
  ) => Promise<CaptureCatalogue>;
  preview: (selected: Capture, signal: AbortSignal) => Promise<TerrainPreview>;
};
export function createTerrainLayer(readers: Readers, timeoutMs = 20000) {
  const initial: TerrainLayerState = {
    entries: [],
    page: null,
    query: null,
    listStatus: 'idle',
    listError: '',
    selected: null,
    preview: null,
    previewStatus: 'idle',
    previewError: '',
    shown: false,
  };
  let state = initial,
    listVersion = 0,
    previewVersion = 0;
  let listAbort: AbortController | undefined,
    previewAbort: AbortController | undefined;
  let listTimer: ReturnType<typeof setTimeout> | undefined,
    previewTimer: ReturnType<typeof setTimeout> | undefined;
  const listeners = new Set<() => void>();
  const emit = (patch: Partial<TerrainLayerState>) => {
    state = { ...state, ...patch };
    listeners.forEach((fn) => fn());
  };
  const cancelPreview = () => {
    previewVersion++;
    previewAbort?.abort();
    clearTimeout(previewTimer);
  };
  const cancelList = () => {
    listVersion++;
    listAbort?.abort();
    clearTimeout(listTimer);
  };
  const clear = () => {
    cancelPreview();
    emit({
      selected: null,
      preview: null,
      previewStatus: 'idle',
      previewError: '',
      shown: false,
    });
  };
  const reset = () => {
    cancelList();
    cancelPreview();
    emit(initial);
  };
  const access = (e: unknown) =>
    !!e &&
    typeof e === 'object' &&
    'status' in e &&
    (e.status === 401 || e.status === 403);
  const message = (e: unknown) =>
    e instanceof Error
      ? e.message
      : 'Terrain is unavailable. Retry to check again.';
  async function search(query: CaptureQuery, append = false) {
    if (append && (state.listStatus === 'loading' || !state.page?.next_cursor))
      return;
    const cursor = append ? (state.page?.next_cursor ?? undefined) : undefined;
    cancelList();
    if (!append) clear();
    const version = listVersion,
      abort = (listAbort = new AbortController());
    emit({
      query,
      listStatus: 'loading',
      listError: '',
      ...(append ? {} : { entries: [], page: null }),
    });
    listTimer = setTimeout(() => {
      if (version !== listVersion) return;
      cancelList();
      emit({
        listStatus: 'error',
        listError: 'The terrain search timed out. Retry to check again.',
      });
    }, timeoutMs);
    try {
      const page = await readers.catalogue(query, cursor, abort.signal);
      if (version !== listVersion || abort.signal.aborted) return;
      if (cursor && page.next_cursor === cursor)
        throw new Error('The search did not advance. Search again.');
      const entries = append ? state.entries : [];
      const seen = new Set(
        entries.map((e) => e.acquisition_id + ':' + e.attempt_id),
      );
      emit({
        page,
        entries: [
          ...entries,
          ...page.entries.filter(
            (e) => !seen.has(e.acquisition_id + ':' + e.attempt_id),
          ),
        ],
        listStatus: 'ready',
      });
    } catch (e) {
      if (version !== listVersion || abort.signal.aborted) return;
      if (access(e)) reset();
      emit({ listStatus: 'error', listError: message(e) });
    } finally {
      if (version === listVersion) clearTimeout(listTimer);
    }
  }
  async function select(selected: Capture) {
    cancelPreview();
    const version = previewVersion,
      abort = (previewAbort = new AbortController());
    emit({
      selected,
      preview: null,
      previewStatus: 'loading',
      previewError: '',
      shown: true,
    });
    previewTimer = setTimeout(() => {
      if (version !== previewVersion) return;
      cancelPreview();
      emit({
        previewStatus: 'error',
        previewError: 'The terrain preview timed out. Retry to check again.',
      });
    }, timeoutMs);
    try {
      const preview = await readers.preview(selected, abort.signal);
      if (version !== previewVersion || abort.signal.aborted) return;
      emit({ preview, previewStatus: 'ready' });
    } catch (e) {
      if (version !== previewVersion || abort.signal.aborted) return;
      if (access(e)) reset();
      emit({ preview: null, previewStatus: 'error', previewError: message(e) });
    } finally {
      if (version === previewVersion) clearTimeout(previewTimer);
    }
  }
  return {
    getSnapshot: () => state,
    subscribe: (fn: () => void) => {
      listeners.add(fn);
      return () => {
        listeners.delete(fn);
      };
    },
    search,
    more: () => (state.query ? search(state.query, true) : Promise.resolve()),
    select,
    clear,
    reset,
    show: (shown: boolean) => emit({ shown }),
    dispose: () => {
      cancelList();
      cancelPreview();
    },
  };
}
