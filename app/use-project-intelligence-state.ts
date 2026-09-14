'use client';
import { useEffect, useRef, useState } from 'react';
import {
  readProjectIntelligenceRun,
  readProjectIntelligenceRuns,
  readProjectSubjects,
  type ProjectIntelligenceRun,
  type ProjectIntelligenceRunSummary,
  type ProjectSubject,
} from './project-intelligence';
import { createLatestRequestFence } from './operating-picture-state';

export type ProjectIntelligenceNavigation = {
  selectedSubjectId: string | null;
  selectedRunId: string | null;
  onSubjectChange: (
    id: string | null,
    method: 'push' | 'replace',
  ) => void;
  onRunChange: (id: string | null, method: 'push' | 'replace') => void;
};

export function useProjectIntelligenceState(
  enabled: boolean,
  navigation: ProjectIntelligenceNavigation,
) {
  const [subjects, setSubjects] = useState<ProjectSubject[]>([]);
  const [runs, setRuns] = useState<ProjectIntelligenceRunSummary[]>([]);
  const [runsSubjectId, setRunsSubjectId] = useState<string | null>(null);
  const [run, setRun] = useState<ProjectIntelligenceRun | null>(null);
  const [detailRunId, setDetailRunId] = useState<string | null>(null);
  const [subjectsLoaded, setSubjectsLoaded] = useState(false);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const subjectRequest = useRef(createLatestRequestFence());
  const runRequest = useRef(createLatestRequestFence());
  const detailRequest = useRef(createLatestRequestFence());
  const navigationRef = useRef(navigation);
  const { selectedSubjectId, selectedRunId } = navigation;

  useEffect(() => {
    navigationRef.current = navigation;
  }, [navigation]);

  useEffect(() => {
    if (!enabled) {
      subjectRequest.current.invalidate();
      return;
    }
    const request = subjectRequest.current.begin();
    void readProjectSubjects()
      .then((items) => {
        if (!subjectRequest.current.isCurrent(request)) return;
        setSubjects(items);
        setSubjectsLoaded(true);
        const currentSelection = navigationRef.current.selectedSubjectId;
        if (
          currentSelection &&
          !items.some((item) => item.id === currentSelection)
        )
          navigationRef.current.onSubjectChange(null, 'replace');
        else if (!currentSelection && items[0])
          navigationRef.current.onSubjectChange(items[0].id, 'replace');
      })
      .catch((reason: Error) => {
        if (subjectRequest.current.isCurrent(request)) setError(reason.message);
      })
  }, [enabled, retry]);

  useEffect(() => {
    const request = runRequest.current.begin();
    detailRequest.current.invalidate();
    if (!enabled || !selectedSubjectId) return;
    void readProjectIntelligenceRuns(selectedSubjectId)
      .then((items) => {
        if (!runRequest.current.isCurrent(request)) return;
        setRuns(items);
        setRunsSubjectId(selectedSubjectId);
        const currentSelection = navigationRef.current.selectedRunId;
        if (currentSelection && !items.some((item) => item.id === currentSelection))
          navigationRef.current.onRunChange(null, 'replace');
        else if (!currentSelection && items[0])
          navigationRef.current.onRunChange(items[0].id, 'replace');
      })
      .catch((reason: Error) => {
        if (runRequest.current.isCurrent(request)) setError(reason.message);
      })
  }, [enabled, selectedSubjectId, retry]);

  useEffect(() => {
    const request = detailRequest.current.begin();
    if (!enabled || !selectedRunId) return;
    void readProjectIntelligenceRun(selectedRunId)
      .then((item) => {
        if (!detailRequest.current.isCurrent(request)) return;
        if (
          item.project_subject_id !==
          navigationRef.current.selectedSubjectId
        ) {
          navigationRef.current.onRunChange(null, 'replace');
          return;
        }
        setRun(item);
        setDetailRunId(selectedRunId);
      })
      .catch((reason: Error) => {
        if (detailRequest.current.isCurrent(request)) setError(reason.message);
      })
  }, [enabled, selectedRunId, retry]);

  const visibleRuns = runsSubjectId === selectedSubjectId ? runs : [];
  const visibleRun = (
    detailRunId === selectedRunId
    && run?.project_subject_id === selectedSubjectId
  ) ? run : null;
  const selectSubject = (subjectId: string) => {
    runRequest.current.invalidate();
    detailRequest.current.invalidate();
    setError('');
    navigationRef.current.onSubjectChange(subjectId, 'push');
    navigationRef.current.onRunChange(null, 'replace');
    setRun(null);
    setDetailRunId(null);
  };
  const selectRun = (runId: string) => {
    detailRequest.current.invalidate();
    setError('');
    navigationRef.current.onRunChange(runId, 'push');
    setRun(null);
    setDetailRunId(null);
  };
  const retryReads = () => {
    subjectRequest.current.invalidate();
    runRequest.current.invalidate();
    detailRequest.current.invalidate();
    setError('');
    setSubjectsLoaded(false);
    setRunsSubjectId(null);
    setDetailRunId(null);
    setRetry((value) => value + 1);
  };

  return {
    subjects,
    selectedSubject: subjects.find((item) => item.id === selectedSubjectId) ?? null,
    selectedSubjectId,
    setSelectedSubjectId: selectSubject,
    runs: visibleRuns,
    selectedRunId,
    setSelectedRunId: selectRun,
    run: visibleRun,
    loading: enabled && (
      !subjectsLoaded
      || (!!selectedSubjectId && runsSubjectId !== selectedSubjectId)
      || (!!selectedRunId && detailRunId !== selectedRunId)
    ),
    error,
    retry: retryReads,
  };
}
