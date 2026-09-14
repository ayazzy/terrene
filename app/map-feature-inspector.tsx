'use client';

import { Link2, LocateFixed, X } from 'lucide-react';
import {
  mapFeatureName,
  mapLayerLabel,
  mapRelationshipSummary,
  type InfrastructureSceneFeature,
  type InfrastructureSceneLayer,
  type SceneSource,
} from './infrastructure-map-scene';

type Props = {
  feature: InfrastructureSceneFeature;
  layer?: InfrastructureSceneLayer;
  sources: SceneSource[];
  limitations: string[];
  relatedVisible: boolean;
  onToggleRelated: () => void;
  onLocate: () => void;
  onClose: () => void;
};

export default function MapFeatureInspector({
  feature,
  layer,
  sources,
  limitations,
  relatedVisible,
  onToggleRelated,
  onLocate,
  onClose,
}: Props) {
  const properties = feature.properties;
  const classification =
    properties.classification ||
    properties.site_theme ||
    properties.object_type;
  const objectSource = sources.find(
    (source) => source.id === properties.object_source_id,
  );
  const height = properties.height;
  return (
    <section
      className="map-feature-inspector"
      aria-label="Selected map evidence"
    >
      <div className="map-feature-inspector-heading">
        <span>
          <p className="eyebrow">SELECTED TERRENE EARTH OBJECT</p>
          <h2>{mapFeatureName(feature)}</h2>
          <small>
            {mapLayerLabel(properties.layer_id)} ·{' '}
            {classification.replaceAll('_', ' ')}
          </small>
        </span>
        <button
          className="icon-btn"
          aria-label="Close selected map evidence"
          onClick={onClose}
        >
          <X size={16} />
        </button>
      </div>
      <div className="map-feature-inspector-body">
        <div>
          <strong>Relationship to parcel</strong>
          {properties.relationships.length ? (
            properties.relationships.map((relationship) => (
              <p key={relationship.id}>
                {mapRelationshipSummary(relationship)}
              </p>
            ))
          ) : (
            <p>No parcel relationship is represented for this source object.</p>
          )}
        </div>
        <div>
          <strong>Source</strong>
          <p>
            {objectSource
              ? `${objectSource.provider} · ${objectSource.dataset} · release ${objectSource.release}`
              : `Release ${properties.source_release}`}
          </p>
          <p className="map-source-qualification">
            Generalised source mapping for screening context—not surveyed,
            cadastral, legal or engineering geometry.
          </p>
          {layer && <p className="nature-muted">{layer.qualification}</p>}
        </div>
        {height && (
          <div>
            <strong>Building height evidence</strong>
            {height.state === 'available' || height.state === 'partial' ? (
              <>
                <p>
                  P90{' '}
                  {height.p90_height_m?.toLocaleString('en-GB', {
                    maximumFractionDigits: 2,
                  })}{' '}
                  m · P50{' '}
                  {height.p50_height_m?.toLocaleString('en-GB', {
                    maximumFractionDigits: 2,
                  })}{' '}
                  m
                </p>
                <p className="nature-muted">
                  {height.sample_count} retained cells ·{' '}
                  {height.coverage_fraction === null
                    ? 'coverage unavailable'
                    : `${(height.coverage_fraction * 100).toLocaleString('en-GB', { maximumFractionDigits: 2 })}% valid coverage`}
                </p>
              </>
            ) : (
              <p>
                {height.state === 'gap'
                  ? `Unavailable · ${height.reason_code?.replaceAll('_', ' ') || 'evidence gap'}`
                  : 'Unsupported by this historical snapshot'}
              </p>
            )}
            <p className="map-source-qualification">{height.qualification}</p>
          </div>
        )}
      </div>
      <div className="map-feature-inspector-actions">
        <button onClick={onLocate}>
          <LocateFixed size={14} /> Locate object
        </button>
        {!!properties.relationships.length && (
          <button aria-pressed={relatedVisible} onClick={onToggleRelated}>
            <Link2 size={14} />
            {relatedVisible ? 'Hide related objects' : 'Show related objects'}
          </button>
        )}
      </div>
      {!!properties.relationships.length && (
        <p className="map-relationship-note">
          Highlights the retained parcel endpoint for these typed relationships.
          No object-to-object network is inferred.
        </p>
      )}
      <details className="map-feature-provenance">
        <summary>Advanced provenance</summary>
        <dl>
          <dt>Object ID</dt>
          <dd>{properties.object_id}</dd>
          <dt>Feature code</dt>
          <dd>{properties.feature_code}</dd>
          <dt>Geometry fingerprint</dt>
          <dd>{properties.geometry_fingerprint}</dd>
          <dt>Authoritative geometry</dt>
          <dd>{properties.authoritative_geometry_crs}</dd>
          {height?.evidence_time && (
            <>
              <dt>Height evidence retrieved</dt>
              <dd>{new Date(height.evidence_time).toLocaleString('en-GB')}</dd>
            </>
          )}
          {properties.relationships.map((relationship) => (
            <div key={relationship.id}>
              <dt>Relationship ID</dt>
              <dd>{relationship.id}</dd>
              <dt>Exact predicate</dt>
              <dd>{relationship.predicate}</dd>
              <dt>Geometry semantics</dt>
              <dd>{relationship.geometry_semantics}</dd>
            </div>
          ))}
          {layer && (
            <>
              <dt>Layer source references</dt>
              <dd>
                {layer.source_reference_ids.join(' · ') || 'None retained'}
              </dd>
            </>
          )}
        </dl>
        {limitations.map((limitation) => (
          <p key={limitation}>{limitation}</p>
        ))}
      </details>
    </section>
  );
}
