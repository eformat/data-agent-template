---
schema_version: 1
id: RAC-KW855KN68PTK
type: requirement
---
# DomainConfig — Single YAML-Driven Configuration

## Problem

Domain agent projects (MLB, NNDSS, Retail) each need identical infrastructure wiring — Trino connection, MLflow tracking, SpiceDB auth, MCP server, deployment manifests — but differ only in domain-specific content: datasets, methodology, aliases, system prompt. Without a shared configuration schema, each project re-invents its own config format, making the framework impossible to maintain across domains.

## Requirements

- [REQ-001] A single Pydantic v2 model (DomainConfig) MUST define the complete configuration surface for any domain agent, with `validate_assignment=True` enforcing runtime type safety.
- [REQ-002] A YAML loader MUST flatten a human-readable nested structure (domain, data, enrichment, mlflow, starters, eval, mcp, deployment sections) into the flat DomainConfig fields.
- [REQ-003] Minimal config (domain_name, domain_display_name, domain_description only) MUST produce a valid DomainConfig with defaults: trino_catalog="lakehouse", replicas=1, agent resources 200m/512Mi, mcp resources 100m/512Mi.
- [REQ-004] Aliases MUST be resolved from both a top-level aliases dict and per-dataset alias lists in the YAML, merged at load time.
- [REQ-005] System prompt MUST be loadable from a file path (system_prompt_file field) with fallback to inline text (system_prompt field).
- [REQ-006] A JSON Schema export (get_json_schema()) MUST be available for external validation tools and editor support.
- [REQ-007] All factory functions (tool creation, MCP server, eval pipeline, deploy rendering, dev mode) MUST consume a single DomainConfig instance — no factory MAY require additional config sources.

## Success Metrics

- Any new domain agent can be configured with a single agent-config.yaml file and zero Python boilerplate for configuration.
- `data-agent validate --config <path>` catches all schema errors before runtime.
- JSON Schema renders correctly in VS Code / IDE YAML plugins for autocompletion.

## Risks

- Pydantic v2 breaking changes across minor versions could invalidate existing configs.
- Flat model grows unwieldy as new integrations are added — may need namespaced sub-models.

## Assumptions

- All domain agents share the same infrastructure stack (Trino/Iceberg, MLflow, SpiceDB, Chainlit).
- YAML is the preferred human-facing config format; Python objects are runtime-only.

## Related Decisions

RAC-KW86NFEZ9KFT
