'use client';

import { useEffect, useRef } from 'react';
import {
  Clock3,
  Crosshair,
  Database,
  FileSearch,
  GitCompareArrows,
  Layers3,
  MapPin,
  Menu,
  Orbit,
  PanelLeft,
  PanelLeftClose,
  PanelLeftOpen,
  RefreshCw,
  Search,
  X,
} from 'lucide-react';
import styles from './operating-shell.module.css';

export type OperatingShellView =
  | 'workspace'
  | 'site'
  | 'project-intelligence'
  | 'compare'
  | 'data';

export type ShellSearchResult = {
  id: string;
  name: string;
  kind: 'site' | 'project_subject';
  detail: string;
  evidenceState: string;
};

export type ShellSelection = {
  kind: 'site' | 'project_subject';
  label: string;
  id: string;
};

type OperatingRailProps = {
  view: OperatingShellView;
  siteCount: number;
  compact: boolean;
  mobileOpen: boolean;
  onViewChange: (view: Exclude<OperatingShellView, 'site'>) => void;
  onCompactChange: () => void;
  onMobileClose: () => void;
};

const railItems = [
  { view: 'workspace', label: 'Sites', icon: PanelLeft },
  { view: 'compare', label: 'Compare sites', icon: GitCompareArrows },
  {
    view: 'project-intelligence',
    label: 'Project intelligence',
    icon: FileSearch,
  },
  { view: 'data', label: 'Data sources', icon: Database },
] as const;

export function OperatingRail({
  view,
  siteCount,
  compact,
  mobileOpen,
  onViewChange,
  onCompactChange,
  onMobileClose,
}: OperatingRailProps) {
  const closeButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!mobileOpen) return;
    closeButton.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onMobileClose();
    };
    document.addEventListener('keydown', closeOnEscape);
    return () => document.removeEventListener('keydown', closeOnEscape);
  }, [mobileOpen, onMobileClose]);
  return (
    <aside
      id="primary-navigation"
      className={`${styles.rail}${compact ? ` ${styles.railCompact}` : ''}${mobileOpen ? ` ${styles.railMobileOpen}` : ''}`}
      aria-label="Primary navigation"
    >
      <div className={styles.brand}>
        <span className={styles.brandMark} aria-hidden="true">
          <Orbit />
        </span>
        <span className={styles.brandIdentity}>
          <strong>Terrene</strong>
          <small>Infrastructure intelligence</small>
        </span>
        <button
          ref={closeButton}
          className={styles.railToggle}
          aria-label={
            mobileOpen
              ? 'Close navigation'
              : compact
                ? 'Expand navigation'
                : 'Collapse navigation'
          }
          title={
            mobileOpen
              ? 'Close navigation'
              : compact
                ? 'Expand navigation'
                : 'Collapse navigation'
          }
          aria-controls="primary-navigation"
          aria-expanded={!compact}
          onClick={mobileOpen ? onMobileClose : onCompactChange}
        >
          {mobileOpen ? (
            <X />
          ) : compact ? (
            <PanelLeftOpen />
          ) : (
            <PanelLeftClose />
          )}
        </button>
      </div>

      <nav className={styles.navigation} aria-label="Operating picture">
        {railItems.map((item, index) => {
          const Icon = item.icon;
          const active =
            item.view === 'workspace'
              ? view === 'workspace' || view === 'site'
              : view === item.view;
          return (
            <button
              key={item.view}
              className={active ? styles.navigationActive : undefined}
              aria-current={active ? 'page' : undefined}
              aria-label={item.label}
              data-tooltip={item.label}
              onClick={() => onViewChange(item.view)}
            >
              <span className={styles.railIndex} aria-hidden="true">
                {String(index + 1).padStart(2, '0')}
              </span>
              <Icon aria-hidden="true" />
              <span className={styles.navigationLabel}>{item.label}</span>
              {item.view === 'workspace' && (
                <span className={styles.navigationCount}>{siteCount}</span>
              )}
            </button>
          );
        })}
      </nav>

      <div className={styles.scopeMark} aria-label="Oxfordshire pilot scope">
        <MapPin aria-hidden="true" />
        <span>
          <strong>Oxfordshire</strong>
          <small>Pilot scope · England</small>
        </span>
      </div>
    </aside>
  );
}

type OperatingCommandBarProps = {
  viewLabel: string;
  query: string;
  searchResults: ShellSearchResult[];
  onQueryChange: (query: string) => void;
  onOpenEntity: (result: ShellSearchResult) => void;
  onMobileMenu: () => void;
  mobileNavigationOpen: boolean;
  sourceStatus: string;
  sourceAsOf: string;
  sourceState: 'loading' | 'available' | 'partial' | 'unavailable';
  selection: ShellSelection | null;
  refreshing: boolean;
  onRefresh: () => void;
};

export function OperatingCommandBar({
  viewLabel,
  query,
  searchResults,
  onQueryChange,
  onOpenEntity,
  onMobileMenu,
  mobileNavigationOpen,
  sourceStatus,
  sourceAsOf,
  sourceState,
  selection,
  refreshing,
  onRefresh,
}: OperatingCommandBarProps) {
  const mobileMenuButton = useRef<HTMLButtonElement>(null);
  const previousMobileOpen = useRef(mobileNavigationOpen);
  useEffect(() => {
    if (previousMobileOpen.current && !mobileNavigationOpen)
      mobileMenuButton.current?.focus();
    previousMobileOpen.current = mobileNavigationOpen;
  }, [mobileNavigationOpen]);
  const hasQuery = query.trim().length > 0;
  return (
    <header className={styles.commandBar}>
      <button
        ref={mobileMenuButton}
        className={styles.mobileMenu}
        aria-label={
          mobileNavigationOpen ? 'Close navigation' : 'Open navigation'
        }
        aria-controls="primary-navigation"
        aria-expanded={mobileNavigationOpen}
        onClick={onMobileMenu}
      >
        <Menu />
      </button>

      <div className={styles.viewIdentity}>
        <span>Infrastructure operating picture</span>
        <small className={styles.mobileContext}>
          Oxfordshire · {sourceAsOf.replace('As of ', '')}
        </small>
        <strong>{viewLabel}</strong>
      </div>

      <form
        className={styles.search}
        aria-label="Search infrastructure entities"
        onSubmit={(event) => {
          event.preventDefault();
          if (searchResults[0]) onOpenEntity(searchResults[0]);
        }}
      >
        <Search aria-hidden="true" />
        <label htmlFor="operating-picture-search">
          Search infrastructure entities
        </label>
        <input
          id="operating-picture-search"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="Search Sites and Project Subjects"
          autoComplete="off"
        />
        {hasQuery && (
          <div className={styles.searchResults}>
            {searchResults.length ? (
              searchResults.map((entity) => (
                <button
                  key={`${entity.kind}:${entity.id}`}
                  type="button"
                  onClick={() => onOpenEntity(entity)}
                >
                  {entity.kind === 'site' ? (
                    <MapPin aria-hidden="true" />
                  ) : (
                    <FileSearch aria-hidden="true" />
                  )}
                  <span>
                    <strong>{entity.name}</strong>
                    <small>
                      {entity.detail} · {entity.evidenceState}
                    </small>
                  </span>
                  <code>{entity.id.slice(-8).toUpperCase()}</code>
                </button>
              ))
            ) : (
              <p>No matching Sites or Project Subjects</p>
            )}
          </div>
        )}
      </form>

      <div className={styles.commandContext}>
        <div className={`${styles.contextItem} ${styles.scope}`}>
          <MapPin aria-hidden="true" />
          <span>
            <small>Scope</small>
            <strong>Oxfordshire</strong>
          </span>
        </div>
        <div
          className={styles.contextItem}
          data-state={sourceState}
          aria-label={`Source availability: ${sourceStatus}. ${sourceAsOf}`}
        >
          <Layers3 aria-hidden="true" />
          <span>
            <small>Sources</small>
            <strong>{sourceStatus}</strong>
          </span>
        </div>
        <div className={`${styles.contextItem} ${styles.asOf}`}>
          <Clock3 aria-hidden="true" />
          <span>
            <small>Source records</small>
            <strong>{sourceAsOf}</strong>
          </span>
        </div>
        <div className={`${styles.contextItem} ${styles.selection}`}>
          <Crosshair aria-hidden="true" />
          <span>
            <small>Selection</small>
            <strong>{selection?.label || 'No entity selected'}</strong>
          </span>
          {selection && <code>{selection.id.slice(-8).toUpperCase()}</code>}
        </div>
        <button
          className={styles.refresh}
          aria-label={
            refreshing ? 'Refreshing source records' : 'Refresh source records'
          }
          title={
            refreshing ? 'Refreshing source records' : 'Refresh source records'
          }
          disabled={refreshing}
          onClick={onRefresh}
        >
          <RefreshCw aria-hidden="true" />
        </button>
      </div>
    </header>
  );
}
