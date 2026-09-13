'use client';

import { useCallback, useEffect, useMemo, useSyncExternalStore } from 'react';
import {
  changeOperatingMode,
  createBrowserOperatingPictureAdapter,
  createOperatingPictureController,
  defaultOperatingPictureState,
  normalizeOperatingPictureState,
  selectOperatingEntity,
  type OperatingArtifactSelection,
  type OperatingDossierSection,
  type OperatingEntitySelection,
  type OperatingMode,
  type OperatingPictureState,
} from './operating-picture-state';

const noopSubscribe = () => () => {};

export function useOperatingPictureState() {
  const controller = useMemo(
    () =>
      typeof window === 'undefined'
        ? null
        : createOperatingPictureController(
            createBrowserOperatingPictureAdapter(),
          ),
    [],
  );
  const state = useSyncExternalStore(
    controller?.subscribe ?? noopSubscribe,
    controller?.getState ?? (() => defaultOperatingPictureState),
    () => defaultOperatingPictureState,
  );

  useEffect(() => () => controller?.destroy(), [controller]);

  const transition = useCallback(
    (
      change:
        | Partial<OperatingPictureState>
        | ((current: OperatingPictureState) => OperatingPictureState),
      method: 'push' | 'replace' = 'push',
    ) => {
      controller?.transition(
        (current) =>
          normalizeOperatingPictureState(
            typeof change === 'function'
              ? change(current)
              : { ...current, ...change },
          ),
        method,
      );
    },
    [controller],
  );

  const setMode = useCallback(
    (mode: OperatingMode) => {
      transition((current) => changeOperatingMode(current, mode));
    },
    [transition],
  );

  const selectEntity = useCallback(
    (selection: OperatingEntitySelection, mode?: OperatingMode) => {
      transition((current) => selectOperatingEntity(current, selection, mode));
    },
    [transition],
  );

  const setArtifact = useCallback(
    (artifact: OperatingArtifactSelection) =>
      transition({ artifact, section: 'overview' }),
    [transition],
  );
  const setSection = useCallback(
    (section: OperatingDossierSection) => transition({ section }),
    [transition],
  );
  const setDossierOpen = useCallback(
    (dossierOpen: boolean) => transition({ dossierOpen }),
    [transition],
  );
  const setHiddenLayers = useCallback(
    (hiddenLayers: string[]) => transition({ hiddenLayers }, 'replace'),
    [transition],
  );

  return {
    state,
    transition,
    setMode,
    selectEntity,
    setArtifact,
    setSection,
    setDossierOpen,
    setHiddenLayers,
  };
}
