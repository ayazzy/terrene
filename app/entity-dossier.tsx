'use client';

import type { ReactNode, Ref } from 'react';
import { Layers3, PanelRightClose } from 'lucide-react';
import styles from './entity-dossier.module.css';

type HistoryState = {
  label: string;
  onReturnLatest: () => void;
};

type EntityDossierProps = {
  className: string;
  open: boolean;
  ariaLabel: string;
  entityKind: string;
  title: string;
  location: string;
  artifact: string;
  evidenceAsOf?: string;
  status?: ReactNode;
  actions?: ReactNode;
  historyState?: HistoryState;
  closeButtonRef?: Ref<HTMLButtonElement>;
  onCollapse: () => void;
  onOpenLayers?: () => void;
  children: ReactNode;
};

export default function EntityDossier({
  className,
  open,
  ariaLabel,
  entityKind,
  title,
  location,
  artifact,
  evidenceAsOf,
  status,
  actions,
  historyState,
  closeButtonRef,
  onCollapse,
  onOpenLayers,
  children,
}: EntityDossierProps) {
  return (
    <section
      className={`${styles.dossier} entity-dossier ${className}${open ? '' : ' dossier-collapsed'}`}
      aria-label={ariaLabel}
      aria-hidden={!open}
      data-entity-dossier={entityKind.toLocaleLowerCase('en-GB')}
    >
      <header className={`${styles.header} entity-dossier-heading`}>
        <div className={styles.identity}>
          <p className={styles.kind}>{entityKind}</p>
          <h1>{title}</h1>
          <div className={styles.envelope}>
            <span>{location}</span>
            <span>{artifact}</span>
            {evidenceAsOf && <span>{evidenceAsOf}</span>}
            {status}
          </div>
        </div>
        <div className={styles.actions}>
          {actions}
          {onOpenLayers && (
            <button className="text-btn" onClick={onOpenLayers}>
              <Layers3 size={15} /> Map layers
            </button>
          )}
          <button
            ref={closeButtonRef}
            className="icon-btn"
            aria-label={`Collapse ${entityKind.toLocaleLowerCase('en-GB')} dossier`}
            onClick={onCollapse}
          >
            <PanelRightClose size={17} />
          </button>
        </div>
      </header>
      {historyState && (
        <output className={`${styles.history} entity-dossier-history`}>
          <span>
            <strong>Historical evidence envelope</strong>
            {historyState.label}
          </span>
          <button className="text-btn" onClick={historyState.onReturnLatest}>
            Return to latest
          </button>
        </output>
      )}
      <div className={styles.body}>{children}</div>
    </section>
  );
}
