'use client';

import { useEffect, useRef, useState } from 'react';
import { createLatestRequestFence } from './operating-picture-state';
import {
  readSiteReasoningRuns,
  type SiteReasoningRunCatalogue,
} from './site-reasoning-runs';

export type SiteReasoningRunsState =
  | 'idle'
  | 'loading'
  | 'ready'
  | 'unavailable';

export function useSiteReasoningRuns(enabled: boolean, siteId: string | null) {
  const [catalogue, setCatalogue] = useState<SiteReasoningRunCatalogue | null>(
    null,
  );
  const [catalogueSiteId, setCatalogueSiteId] = useState<string | null>(null);
  const [state, setState] = useState<SiteReasoningRunsState>('idle');
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  const requestFence = useRef(createLatestRequestFence());

  useEffect(() => {
    const fence = requestFence.current;
    const request = fence.begin();
    if (!enabled || !siteId) return;
    const abort = new AbortController();
    void readSiteReasoningRuns(siteId, abort.signal)
      .then((next) => {
        if (!fence.isCurrent(request) || abort.signal.aborted) return;
        setCatalogue(next);
        setCatalogueSiteId(siteId);
        setState('ready');
        setError('');
      })
      .catch((reason: Error) => {
        if (!fence.isCurrent(request) || abort.signal.aborted) return;
        setCatalogue(null);
        setCatalogueSiteId(siteId);
        setState('unavailable');
        setError(reason.message);
      });
    return () => {
      abort.abort();
      fence.invalidate();
    };
  }, [enabled, revision, siteId]);

  const visible = catalogueSiteId === siteId ? catalogue : null;
  return {
    catalogue: visible,
    runs: visible?.runs || [],
    state:
      !enabled || !siteId
        ? ('idle' as const)
        : catalogueSiteId === siteId
          ? state
          : ('loading' as const),
    error: catalogueSiteId === siteId ? error : '',
    refresh: () => {
      requestFence.current.invalidate();
      setCatalogueSiteId(null);
      setState('loading');
      setError('');
      setRevision((value) => value + 1);
    },
  };
}
