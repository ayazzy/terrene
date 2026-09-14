const ASSESSMENT_STATE_LABELS: Record<string, string> = {
  completed: 'Completed',
  partial: 'Partial evidence',
  queued: 'Queued',
  running: 'In progress',
  failed: 'Failed',
};

export function assessmentStateLabel(state: string) {
  return (
    ASSESSMENT_STATE_LABELS[state] ||
    state
      .replaceAll('_', ' ')
      .replace(/^./, (character) => character.toUpperCase())
  );
}

export function assessmentStateClass(state: string) {
  return state.toLowerCase().replace(/[^a-z0-9]+/g, '-');
}

export function assessmentCreatedLabel(created: string) {
  const date = new Date(created);
  if (Number.isNaN(date.getTime())) return 'Creation date unavailable';
  const day = new Intl.DateTimeFormat('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(date);
  const time = new Intl.DateTimeFormat('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
  return `Created ${day} at ${time}`;
}
