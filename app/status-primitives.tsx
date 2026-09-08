import type { ReactNode } from 'react';
import {
  AlertTriangle,
  CircleDashed,
  Database,
  MinusCircle,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from '@/components/ui/empty';
import { Skeleton } from '@/components/ui/skeleton';

export type EvidenceState =
  | 'available'
  | 'modelled'
  | 'partial'
  | 'missing'
  | 'warning'
  | 'unavailable';

export function EvidenceBadge({
  state,
  children,
}: {
  state: EvidenceState;
  children?: ReactNode;
}) {
  const label = children ?? state;
  return (
    <Badge variant="outline" className={`evidence-badge is-${state}`}>
      <span className="evidence-dot" aria-hidden="true" />
      {label}
    </Badge>
  );
}

export function WorkspaceState({
  kind,
  title,
  description,
  action,
}: {
  kind: 'empty' | 'error' | 'unavailable' | 'partial';
  title: string;
  description: string;
  action?: ReactNode;
}) {
  const Icon =
    kind === 'error'
      ? AlertTriangle
      : kind === 'partial'
        ? CircleDashed
        : kind === 'unavailable'
          ? MinusCircle
          : Database;
  return (
    <Empty className={`workspace-state is-${kind}`}>
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <Icon />
        </EmptyMedia>
        <EmptyTitle>{title}</EmptyTitle>
        <EmptyDescription>{description}</EmptyDescription>
      </EmptyHeader>
      {action && <EmptyContent>{action}</EmptyContent>}
    </Empty>
  );
}

export function WorkspaceLoading() {
  return (
    <output className="workspace-loading" aria-label="Loading workspace">
      <div className="workspace-loading-head">
        <Skeleton />
        <Skeleton />
        <Skeleton />
      </div>
      {[0, 1, 2].map((row) => (
        <div className="workspace-loading-row" key={row}>
          <Skeleton />
          <Skeleton />
          <Skeleton />
          <Skeleton />
        </div>
      ))}
      <span className="sr-only">Loading workspace data…</span>
    </output>
  );
}
