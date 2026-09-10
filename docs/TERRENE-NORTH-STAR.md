# Terrene North Star

## Thesis

Terrene's long-term goal is a computational model of land and human interventions. Terrene is not primarily an environmental-data aggregator, GIS viewer, BNG application, restoration product or renewable-screening product. Those may be inputs, interfaces, modules or applications built on a shared foundation.

Public data is an input, not the product. The intended progression is:

> ingest → normalize → represent → reason → simulate → act → observe → update

Wetland is an early reasoning primitive, not Terrene's identity. The map is an interface into Terrene Earth, not the product itself.

## Terrene Earth — representation

Terrene Earth is the canonical, evidence-backed representation of what exists and what is known about it. Its scope may include terrain, soil, hydrology, climate, vegetation, ecology, land use, parcels, habitats, watercourses, catchments, protected areas, buildings, roads, transmission and other infrastructure, dams, projects, layouts, surveys, permits, interventions, customer and field evidence, provenance, timestamps and uncertainty.

Its question is:

> What exists here, and what do we know about it?

Terrene Earth separates represented objects and relationships from evidence about them. It preserves source identity, spatial and temporal support, uncertainty, coverage and provenance rather than flattening heterogeneous evidence into a universal score.

## Terrene Reasoning — computation

Terrene Reasoning consists of modular deterministic or scientific models operating on Terrene Earth. Possible modules include wetland or restoration suitability, buildable area, habitat impact, hydrological behaviour, environmental constraints, climate exposure and infrastructure/environment interactions.

Its question is:

> What is possible, constrained, risky, suitable or likely here—and why?

Reasoning outputs are interpretations, not reusable Earth facts. Models, bindings, configurations and runs must be versioned and inspectable.

## Terrene Scenario — intervention

Terrene Scenario will represent proposed change as a model input:

> current state → intervention → computed alternative or future state

A near-term example is drawing a proposed development footprint and recomputing habitat impact, watercourse intersections, flood exposure, constraints, usable area and unknowns. Scenario is not yet a completed repository layer. The current architecture should not be optimized around 3D visualization.

Its question is:

> What changes if we do this?

## Terrene Applications — workflows

Terrene Applications turn the shared Earth, Reasoning and Scenario foundations into validated workflows. Potential applications include Screen, Diligence, Scenario, Monitor, Portfolio, Nature/BNG, Restoration, Field Evidence, and infrastructure or renewable-development applications.

Applications should share the same foundations rather than create isolated evidence models. A horizontal architecture does not require a horizontal go-to-market strategy.

## Product and commercial discipline

Terrene is a company, not an open-ended research project. Technical sophistication matters only where it improves real, expensive decisions. Customer discovery should determine which vertical application receives priority and which evidence, reasoning and scenario capabilities are commercially necessary.

The present wedge hypothesis is early-stage site screening and diligence for land-intensive development, potentially beginning with UK utility-scale solar, battery energy storage or related infrastructure. This remains a hypothesis until supported by customer evidence; see [Customer Discovery](CUSTOMER-DISCOVERY.md).
