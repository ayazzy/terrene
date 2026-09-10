"""Render a small, reproducible manual QA sheet for real PHI/site geography."""
import json
from pathlib import Path
import sys
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from shapely.geometry import shape
from shapely.ops import transform

from backend import core
from backend.priority_habitats import normalize_properties


SAMPLES = ('port-meadow', 'oxford-station', 'wytham-slope')
PRIORITY_COLOURS = {
    'CFPGM': '#3b82f6',
    'LMEAD': '#16a34a',
    'DWOOD': '#92400e',
}
SUPPORTING_COLOUR = '#eab308'
DISPLAY_TITLES = {
    'wytham-slope': 'Wytham Woods hillside sample',
}


def polygon_parts(geometry):
    return [geometry] if geometry.geom_type == 'Polygon' else list(geometry.geoms)


def svg_path(geometry, project):
    parts = []
    for polygon in polygon_parts(geometry):
        for ring in (polygon.exterior, *polygon.interiors):
            coordinates = [project(x, y) for x, y in ring.coords]
            parts.append('M ' + ' L '.join(f'{x:.2f} {y:.2f}' for x, y in coordinates) + ' Z')
    return ' '.join(parts)


def main():
    sites = {
        feature['id']: feature
        for feature in json.loads(Path('docs/real-verification-sites.geojson').read_text())['features']
        if feature['id'] in SAMPLES
    }
    results = {
        item['id']: item
        for item in json.loads(Path('docs/real-verification-results.json').read_text())['sites']
        if item['id'] in SAMPLES
    }
    with core.engine.connect() as connection:
        dataset = next(item for item in core.latest(connection)
                       if item['key'] == 'priority_habitats')
        records = []
        for site_id in SAMPLES:
            site = sites[site_id]
            parcel_wgs84 = shape(site['geometry'])
            minx, miny, maxx, maxy = parcel_wgs84.bounds
            rows = connection.execute(select(
                core.features.c.geometry, core.features.c.properties,
            ).where(
                core.features.c.dataset_id == dataset['id'],
                core.features.c.minx <= maxx,
                core.features.c.maxx >= minx,
                core.features.c.miny <= maxy,
                core.features.c.maxy >= miny,
            )).mappings()
            hits = []
            for row in rows:
                geometry_wgs84 = shape(row['geometry'])
                if not geometry_wgs84.intersects(parcel_wgs84):
                    continue
                hits.append((transform(core.forward, geometry_wgs84),
                             normalize_properties(row['properties'])))
            records.append((site_id, transform(core.forward, parcel_wgs84), hits))

    width, height = 1600, 650
    panel_width, map_size = 515, 450
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width / 2:.0f}" height="{height / 2:.0f}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<defs><pattern id="supporting-hatch" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="10" height="10" fill="#fde68a"/><line x1="0" y1="0" x2="0" y2="10" stroke="#a16207" stroke-width="3"/></pattern></defs>',
        f'<text x="{width / 2:.0f}" y="28" text-anchor="middle" font-family="Arial, sans-serif" font-size="22" font-weight="700">Natural England Priority Habitats Inventory (England) · Sep_25</text>',
        f'<text x="{width / 2:.0f}" y="54" text-anchor="middle" font-family="Arial, sans-serif" font-size="16">Manual source-geometry inspection · exact site/source polygons in EPSG:27700</text>',
    ]
    for index, (site_id, parcel, hits) in enumerate(records):
        result = results[site_id]
        plotted = set()
        minx, miny, maxx, maxy = parcel.bounds
        extent = max(maxx - minx, maxy - miny) * 1.16
        centre_x, centre_y = (minx + maxx) / 2, (miny + maxy) / 2
        minx, maxx = centre_x - extent / 2, centre_x + extent / 2
        miny, maxy = centre_y - extent / 2, centre_y + extent / 2
        left, top = 30 + index * panel_width, 120
        def project(x, y):
            return (left + (x - minx) / extent * map_size,
                    top + map_size - (y - miny) / extent * map_size)

        svg.append(f'<defs><clipPath id="panel-{index}"><rect x="{left}" y="{top}" width="{map_size}" height="{map_size}"/></clipPath></defs>')
        svg.append(f'<rect x="{left}" y="{top}" width="{map_size}" height="{map_size}" fill="#f8fafc" stroke="#cbd5e1"/>')
        svg.append(f'<g clip-path="url(#panel-{index})">')
        for geometry, properties in hits:
            priority_codes = [item['code'] for item in properties['main_habitats']
                              if item['status'] == 'priority']
            code = priority_codes[0] if priority_codes else properties['main_habitats'][0]['code']
            supporting = not priority_codes
            colour = SUPPORTING_COLOUR if supporting else PRIORITY_COLOURS.get(code, '#7c3aed')
            fill = 'url(#supporting-hatch)' if supporting else colour
            svg.append(f'<path d="{svg_path(geometry, project)}" fill="{fill}" fill-opacity="0.42" fill-rule="evenodd" stroke="{colour}" stroke-width="1.2"/>')
            plotted.add((code, supporting))
        svg.append(f'<path d="{svg_path(parcel, project)}" fill="none" fill-rule="evenodd" stroke="#111827" stroke-width="3"/>')
        svg.append('</g>')
        phi = result['priority_habitats']
        classes = ', '.join(item['code'] for item in phi['habitats']) or 'no main priority class'
        centre = left + map_size / 2
        display_title = DISPLAY_TITLES.get(site_id, result['name'])
        title_length = max(200, min(420, len(display_title) * 7.5))
        metric = (f"main priority union {100 * phi['union_overlap_fraction']:.2f}% · "
                  + (classes if phi['habitats'] else 'mapped zero'))
        svg.extend([
            f'<text x="{centre}" y="82" text-anchor="middle" font-family="Arial, sans-serif" font-size="13" font-weight="700" textLength="{title_length}" lengthAdjust="spacingAndGlyphs">{escape(display_title)}</text>',
            f'<text x="{centre}" y="101" text-anchor="middle" font-family="Arial, sans-serif" font-size="11">{escape(metric)}</text>',
            f'<text x="{centre}" y="117" text-anchor="middle" font-family="Arial, sans-serif" font-size="12">{phi["source_feature_count"]} intersecting source feature(s)</text>',
            f'<line x1="{left + 12}" y1="{top + 18}" x2="{left + 38}" y2="{top + 18}" stroke="#111827" stroke-width="3"/>',
            f'<text x="{left + 45}" y="{top + 22}" font-family="Arial, sans-serif" font-size="11">verification boundary</text>',
        ])
        legend_y = top + 42
        for code, supporting in sorted(plotted):
            fill = 'url(#supporting-hatch)' if supporting else PRIORITY_COLOURS.get(code, '#7c3aed')
            label = code + (' (supporting / non-priority)' if supporting else ' (main priority)')
            svg.extend([
                f'<rect x="{left + 12}" y="{legend_y}" width="26" height="13" fill="{fill}" stroke="#475569"/>',
                f'<text x="{left + 45}" y="{legend_y + 11}" font-family="Arial, sans-serif" font-size="11">{escape(label)}</text>',
            ])
            legend_y += 19
        svg.append(f'<text x="{centre}" y="{top + map_size + 22}" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#475569">BNG centre {centre_x:.0f} E, {centre_y:.0f} N</text>')
    svg.append('</svg>')
    output = Path('docs/priority-habitats-source-inspection.svg')
    output.write_text('\n'.join(svg))
    print(output)


if __name__ == '__main__':
    main()
