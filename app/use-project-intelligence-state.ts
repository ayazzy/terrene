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

export function useProjectIntelligenceState(enabled: boolean) {
  const [subjects, setSubjects] = useState<ProjectSubject[]>([]);
  const [selectedSubjectId, setSelectedSubjectId] = useState<string | null>(null);
  const [runs, setRuns] = useState<ProjectIntelligenceRunSummary[]>([]);
  const [runsSubjectId, setRunsSubjectId] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [run, setRun] = useState<ProjectIntelligenceRun | null>(null);
  const [detailRunId, setDetailRunId] = useState<string | null>(null);
  const [subjectsLoaded, setSubjectsLoaded] = useState(false);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const subjectRequest = useRef(0);
  const runRequest = useRef(0);
  const detailRequest = useRef(0);

  useEffect(() => {
    if (!enabled) return;
    const request = ++subjectRequest.current;
    void readProjectSubjects()
      .then((items) => {
        if (request !== subjectRequest.current) return;
        setSubjects(items);
        setSubjectsLoaded(true);
        setSelectedSubjectId((current) =>
          current && items.some((item) => item.id === current)
            ? current
            : (items[0]?.id ?? null),
        );
      })
      .catch((reason: Error) => {
        if (request === subjectRequest.current) setError(reason.message);
      })
  }, [enabled, retry]);

  useEffect(() => {
    if (!enabled || !selectedSubjectId) return;
    const request = ++runRequest.current;
    void readProjectIntelligenceRuns(selectedSubjectId)
      .then((items) => {
        if (request !== runRequest.current) return;
        setRuns(items);
        setRunsSubjectId(selectedSubjectId);
        setSelectedRunId((current) =>
          current && items.some((item) => item.id === current)
            ? current
            : (items[0]?.id ?? null),
        );
      })
      .catch((reason: Error) => {
        if (request === runRequest.current) setError(reason.message);
      })
  }, [enabled, selectedSubjectId, retry]);

  useEffect(() => {
    if (!enabled || !selectedRunId) return;
    const request = ++detailRequest.current;
    void readProjectIntelligenceRun(selectedRunId)
      .then((item) => {
        if (request === detailRequest.current) {
          setRun(item);
          setDetailRunId(selectedRunId);
        }
      })
      .catch((reason: Error) => {
        if (request === detailRequest.current) setError(reason.message);
      })
  }, [enabled, selectedRunId, retry]);

  const visibleRuns = runsSubjectId === selectedSubjectId ? runs : [];
  const visibleRun = (
    detailRunId === selectedRunId
    && run?.project_subject_id === selectedSubjectId
  ) ? run : null;
  const selectSubject = (subjectId: string) => {
    runRequest.current += 1;
    detailRequest.current += 1;
    setError('');
    setSelectedSubjectId(subjectId);
    setSelectedRunId(null);
    setRun(null);
    setDetailRunId(null);
  };
  const selectRun = (runId: string) => {
    detailRequest.current += 1;
    setError('');
    setSelectedRunId(runId);
    setRun(null);
    setDetailRunId(null);
  };
  const retryReads = () => {
    subjectRequest.current += 1;
    runRequest.current += 1;
    detailRequest.current += 1;
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
