import type {
  Capture,
  CaptureQuery,
  CaptureCatalogue,
  CaptureDetail,
} from './acquisitions';

type Phase = 'idle' | 'loading' | 'ready' | 'error';
export type CaptureBrowserState = {
  query: CaptureQuery;
  entries: Capture[];
  page: CaptureCatalogue | null;
  scanned: number;
  listStatus: Phase;
  listError: string;
  selected: Capture | null;
  detail: CaptureDetail | null;
  detailStatus: Phase;
  detailError: string;
};
type Readers = {
  catalogue: (
    query: CaptureQuery,
    cursor: string | undefined,
    signal: AbortSignal,
  ) => Promise<CaptureCatalogue>;
  detail: (selected: Capture, signal: AbortSignal) => Promise<CaptureDetail>;
};
/** Request fences also reject late responses from transports that ignore abort. */
export function createCaptureBrowser(
  readers: Readers,
  initialQuery: CaptureQuery,
) {
  let state: CaptureBrowserState = {
    query: initialQuery,
    entries: [],
    page: null,
    scanned: 0,
    listStatus: 'idle',
    listError: '',
    selected: null,
    detail: null,
    detailStatus: 'idle',
    detailError: '',
  };
  let listVersion = 0,
    detailVersion = 0;
  let listAbort: AbortController | undefined,
    detailAbort: AbortController | undefined;
  const listeners = new Set<() => void>();
  const emit = (patch: Partial<CaptureBrowserState>) => {
    state = { ...state, ...patch };
    listeners.forEach((fn) => fn());
  };
  const clearDetail = () => {
    detailVersion++;
    detailAbort?.abort();
  };
  const accessFailure = (error: unknown) =>
    !!error &&
    typeof error === 'object' &&
    'status' in error &&
    (error.status === 401 || error.status === 403);
  const message = (error: unknown) =>
    error instanceof Error
      ? error.message
      : 'The evidence service is unavailable. Retry to check again.';
  async function load(query: CaptureQuery, append: boolean) {
    if (append && (state.listStatus === 'loading' || !state.page?.next_cursor))
      return;
    const cursor = append ? (state.page?.next_cursor ?? undefined) : undefined;
    listAbort?.abort();
    listAbort = new AbortController();
    const signal = listAbort.signal,
      version = ++listVersion;
    if (!append) {
      clearDetail();
      emit({
        query: { ...query },
        entries: [],
        page: null,
        scanned: 0,
        selected: null,
        detail: null,
        detailStatus: 'idle',
        detailError: '',
      });
    }
    emit({ listStatus: 'loading', listError: '' });
    try {
      const page = await readers.catalogue(query, cursor, signal);
      if (version !== listVersion || signal.aborted) return;
      if (cursor && page.next_cursor === cursor)
        throw new Error('The search did not advance. Start a new search.');
      const prior = append ? state.entries : [];
      const identities = new Set(
        prior.map((e) => e.acquisition_id + ':' + e.attempt_id),
      );
      emit({
        page,
        entries: [
          ...prior,
          ...page.entries.filter(
            (e) => !identities.has(e.acquisition_id + ':' + e.attempt_id),
          ),
        ],
        scanned: state.scanned + page.scanned_count,
        listStatus: 'ready',
      });
    } catch (error) {
      if (version !== listVersion || signal.aborted) return;
      if (accessFailure(error)) {
        clearDetail();
        emit({
          entries: [],
          page: null,
          scanned: 0,
          selected: null,
          detail: null,
          detailStatus: 'idle',
          detailError: '',
        });
      }
      emit({ listStatus: 'error', listError: message(error) });
    }
  }
  async function select(selected: Capture) {
    clearDetail();
    detailAbort = new AbortController();
    const signal = detailAbort.signal,
      version = detailVersion;
    emit({ selected, detail: null, detailStatus: 'loading', detailError: '' });
    try {
      const detail = await readers.detail(selected, signal);
      if (version !== detailVersion || signal.aborted) return;
      emit({ detail, detailStatus: 'ready' });
    } catch (error) {
      if (version !== detailVersion || signal.aborted) return;
      if (accessFailure(error)) {
        listVersion++;
        listAbort?.abort();
        emit({
          entries: [],
          page: null,
          scanned: 0,
          selected: null,
          detail: null,
          detailStatus: 'idle',
          listStatus: 'error',
          listError: message(error),
        });
      } else
        emit({
          detail: null,
          detailStatus: 'error',
          detailError: message(error),
        });
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
    search: (query: CaptureQuery) => load(query, false),
    more: () => load(state.query, true),
    select,
    close: () => {
      clearDetail();
      emit({
        selected: null,
        detail: null,
        detailStatus: 'idle',
        detailError: '',
      });
    },
    dispose: () => {
      listVersion++;
      listAbort?.abort();
      clearDetail();
    },
  };
}
