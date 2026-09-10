import { ArrowUpRight, MapPin } from 'lucide-react';
import type { OverlayFinding } from './site-evidence';
import { EvidenceBadge } from './status-primitives';
import { layerColor } from './site-evidence';

export default function OverlayFindings({
  findings,
  onInspect,
  onMap,
}: {
  findings: OverlayFinding[];
  onInspect: (finding: OverlayFinding) => void;
  onMap: (key: string) => void;
}) {
  if (!findings.length) return null;
  return (
    <section
      className="overlay-findings"
      aria-label="Saved reference-layer observations"
    >
      <h3>Reference-layer observations</h3>
      <p className="nature-muted">
        Exact intersections from the saved assessment. No overlap is not proof
        of absence.
      </p>
      {findings.map((f) => (
        <div className="overlay-finding" key={f.key}>
          <button className="overlay-inspect" onClick={() => onInspect(f)}>
            <i
              className="layer-swatch"
              style={{ background: layerColor(f.key) }}
            />
            <span>
              <strong>{f.dataset}</strong>
              <small>
                {f.measured === null
                  ? 'Evidence unavailable'
                  : `${f.measured.toLocaleString('en-GB', { maximumFractionDigits: 2 })} ha overlap${f.percent !== undefined ? ` · ${f.percent}% of site` : ''}`}
              </small>
            </span>
            <ArrowUpRight size={14} />
          </button>
          <div className="overlay-finding-actions">
            <EvidenceBadge
              state={f.measured === null ? 'unavailable' : 'available'}
            >
              {f.measured === null ? 'Unavailable' : 'Measured'}
            </EvidenceBadge>
            {f.geometry && (
              <button className="text-btn" onClick={() => onMap(f.key)}>
                <MapPin size={13} /> Show on map
              </button>
            )}
          </div>
        </div>
      ))}
    </section>
  );
}
