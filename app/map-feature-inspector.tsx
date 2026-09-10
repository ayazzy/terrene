'use client';

import { LocateFixed, X } from 'lucide-react';
import {
  mapFeatureName,
  mapLayerLabel,
  mapRelationshipSummary,
  type ScreeningMapFeature,
  type ScreeningMapLayer,
} from './screening-map-features';

type Props = {
  feature: ScreeningMapFeature;
  layer?: ScreeningMapLayer;
  limitations: string[];
  onLocate: () => void;
  onClose: () => void;
};

export default function MapFeatureInspector({
  feature,
  layer,
  limitations,
  onLocate,
  onClose,
}: Props) {
  const properties = feature.properties;
  const classification =
    properties.classification ||
    properties.site_theme ||
    properties.object_type;
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
            {properties.source.provider} · {properties.source.dataset} · release{' '}
            {properties.source.release}
          </p>
          <p className="map-source-qualification">
            Generalised source mapping for screening context—not surveyed,
            cadastral, legal or engineering geometry.
          </p>
          {layer && <p className="nature-muted">{layer.qualification}</p>}
        </div>
      </div>
      <div className="map-feature-inspector-actions">
        <button onClick={onLocate}>
          <LocateFixed size={14} /> Locate object
        </button>
      </div>
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
              <dt>Layer coverage basis</dt>
              <dd>{layer.coverage_basis.join(' · ')}</dd>
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
