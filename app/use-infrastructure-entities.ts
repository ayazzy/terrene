'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  readProjectIntelligenceRuns,
  readProjectSubjects,
  type ProjectIntelligenceRunSummary,
  type ProjectSubject,
} from './project-intelligence';

export function useInfrastructureEntities() {
  const generation = useRef(0);
  const [subjects, setSubjects] = useState<ProjectSubject[]>([]);
  const [runs, setRuns] = useState<
    Record<string, ProjectIntelligenceRunSummary[]>
  >({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const reload = useCallback(async () => {
    const request = ++generation.current;
    setLoading(true);
    setError('');
    try {
      const nextSubjects = await readProjectSubjects();
      const runReads = await Promise.allSettled(
        nextSubjects.map((subject) => readProjectIntelligenceRuns(subject.id)),
      );
      if (request !== generation.current) return;
      const nextRuns: Record<string, ProjectIntelligenceRunSummary[]> = {};
      runReads.forEach((result, index) => {
        if (result.status === 'fulfilled')
          nextRuns[nextSubjects[index].id] = result.value;
      });
      setSubjects(nextSubjects);
      setRuns(nextRuns);
      if (runReads.some((result) => result.status === 'rejected'))
        setError('Some Project Intelligence run states are unavailable.');
    } catch (reason) {
      if (request !== generation.current) return;
      setError(
        reason instanceof Error
          ? reason.message
          : 'Project Subjects are unavailable.',
      );
    } finally {
      if (request === generation.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => void reload());
    return () => {
      generation.current += 1;
    };
  }, [reload]);

  return { subjects, runs, loading, error, reload };
}
