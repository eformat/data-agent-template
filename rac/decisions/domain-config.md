---
schema_version: 1
id: RAC-KW86NFEZ9KFT
type: decision
---
# Single Pydantic v2 DomainConfig Drives All Factory Functions

## Context

The framework supports multiple domain agents (MLB, NNDSS, Retail) that share identical infrastructure — Trino, MLflow, SpiceDB, MCP, deployment manifests — but differ in domain content. Early prototypes used ad-hoc config dicts passed to each factory, leading to inconsistent parameter names, missing validation, and duplicated wiring code across domains.

## Decision

We adopt a single Pydantic v2 model (DomainConfig) as the sole configuration surface. A YAML loader flattens human-readable nested sections into the flat model. Every factory function — tool creation, MCP server, eval pipeline, deploy rendering, dev mode — consumes one DomainConfig instance and no other config source. A JSON Schema export is provided for editor support.

## Consequences

**Easier:** Adding a new domain agent requires only a YAML file — no Python config boilerplate. Schema validation catches errors before runtime. IDE autocompletion works via JSON Schema.

**Harder:** The flat model grows as integrations are added; may eventually need namespaced sub-models. Pydantic v2 is a hard dependency — breaking changes across minor versions could require migration effort.

## Status

Accepted

## Category

Architecture

## Alternatives Considered

- **Per-domain Python config classes** — rejected because it duplicates schema definitions and prevents the "one YAML file" developer experience.
- **Untyped dict/JSON config** — rejected because it provides no validation, no defaults, and no editor support.
- **Dynaconf or Hydra** — rejected as unnecessary dependencies for the config complexity involved; Pydantic v2 already handles validation, defaults, and JSON Schema.

## Related Requirements

RAC-KW855KN68PTK
