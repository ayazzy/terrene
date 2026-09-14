'use client';

import { ArrowUpRight, CalendarClock, Database, GitBranch } from 'lucide-react';
import {
  assessmentCreatedLabel,
  assessmentStateClass,
  assessmentStateLabel,
} from './assessment-timeline-format';

export type SiteAssessmentTimelineItem = {
  id: string;
  version: number;
  state: string;
  created: string;
  dataset_ids?: string[] | null;
};

export default function SiteAssessmentTimeline({
  assessments,
  selectedAssessmentId,
  latestAssessmentId,
  currentBoundaryVersion,
  emptyMessage,
  onSelect,
}: {
  assessments: SiteAssessmentTimelineItem[];
  selectedAssessmentId?: string;
  latestAssessmentId?: string;
  currentBoundaryVersion: number;
  emptyMessage: string;
  onSelect: (assessmentId: string) => void;
}) {
  return (
    <section className="assessment-history" aria-labelledby="history-title">
      <header className="assessment-history-heading">
        <p className="eyebrow">RETAINED HISTORY</p>
        <h2 id="history-title">Assessment timeline</h2>
        <p>
          Select an immutable assessment to move its saved boundary, evidence
          and model output together across the map and dossier.
        </p>
      </header>

      <aside className="history-interpretation-note">
        <strong>Read entries as retained states, not causes of change.</strong>
        <span>
          A newer assessment does not by itself establish that the site or its
          conditions changed.
        </span>
      </aside>

      {assessments.length ? (
        <ol className="assessment-timeline" aria-label="Saved assessments">
          {assessments.map((item) => {
            const isSelected = item.id === selectedAssessmentId;
            const isLatest = item.id === latestAssessmentId;
            const usesCurrentBoundary = item.version === currentBoundaryVersion;
            const sourceCount = item.dataset_ids?.length;
            return (
              <li key={item.id}>
                <button
                  type="button"
                  className={`assessment-timeline-entry${isSelected ? ' is-selected' : ''}`}
                  aria-current={isSelected ? 'step' : undefined}
                  onClick={() => onSelect(item.id)}
                >
                  <span className="assessment-entry-heading">
                    <span>
                      <small>{assessmentCreatedLabel(item.created)}</small>
                      <strong>Boundary v{item.version}</strong>
                    </span>
                    <span
                      className={`assessment-state state-${assessmentStateClass(item.state)}`}
                    >
                      {assessmentStateLabel(item.state)}
                    </span>
                  </span>

                  <span className="assessment-entry-metadata">
                    <span>
                      <GitBranch size={13} aria-hidden="true" />
                      {usesCurrentBoundary
                        ? 'Matches current Site boundary'
                        : `Historical boundary · current Site is v${currentBoundaryVersion}`}
                    </span>
                    {sourceCount != null && sourceCount > 0 && (
                      <span>
                        <Database size={13} aria-hidden="true" /> {sourceCount}{' '}
                        source version{sourceCount === 1 ? '' : 's'} retained
                      </span>
                    )}
                  </span>

                  <span className="assessment-entry-footer">
                    <span>
                      {isSelected && <b>Viewing</b>}
                      {isLatest && <small>Latest assessment</small>}
                    </span>
                    <span>
                      {isSelected ? 'Shown on map' : 'View assessment'}
                      <ArrowUpRight size={14} aria-hidden="true" />
                    </span>
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      ) : (
        <div className="assessment-history-empty">
          <CalendarClock size={18} aria-hidden="true" />
          <p>{emptyMessage}</p>
        </div>
      )}
    </section>
  );
}
