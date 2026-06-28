---
schema_version: 1
id: RAC-KW86NH6F62TY
type: decision
---
# Scaffold Generator with Kustomize Deploy Templates from DomainConfig

## Context

Creating a new domain agent requires dozens of boilerplate files: Containerfiles, kustomize manifests, deployment configs, scripts, and test stubs. Without a generator, each new project copy-pastes from an existing one, leading to drift and inconsistency. Deploy manifests contain domain-specific values (namespace, resource limits, endpoints) that must be correct-by-construction.

## Decision

We implement `data-agent init <name>` to scaffold a complete project and `render_deploy_tree(config)` to generate OpenShift/K8s manifests from DomainConfig. All template variables are flattened from DomainConfig using Python string.Template.safe_substitute. Containerfiles use UBI base images. Scripts are made executable. CHAINLIT_AUTH_SECRET is generated as random 32-byte hex per scaffold run. Kustomize is the deployment strategy.

## Consequences

**Easier:** New domain agents start with a complete, valid project structure in one command. Deploy manifests are always consistent with the config. UBI base images satisfy OpenShift security requirements.

**Harder:** safe_substitute silently passes through unrecognized variables rather than failing — mistyped variable names produce broken manifests without error. OpenShift API version changes may invalidate generated manifests. Kustomize-only means Helm users must adapt.

## Status

Accepted

## Category

Technical

## Alternatives Considered

- **Helm charts instead of kustomize** — rejected because kustomize is the preferred overlay strategy in the target OpenShift environments and avoids the templating complexity of Helm.
- **Cookiecutter or Copier for scaffolding** — rejected as unnecessary dependencies; Python string.Template handles the variable substitution needed, and the scaffold is simple enough to not need a full project templating framework.
- **No scaffold (manual project setup)** — rejected because copy-paste-from-existing was the root cause of configuration drift between domain agents.

## Related Requirements

RAC-KW855PSFC7QN
