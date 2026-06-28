# Retail Enterprise Authorization Demo

Example configuration for the Acme Retail Corp finance department data agent.

- `agent-config.yaml` — DomainConfig with 4 finance datasets, methodology, aliases, eval seed questions
- `system_prompt.md` — 7-consideration reasoning protocol for the finance agent

## Other departments

In production, each department (finance, sales, ops) runs as a separate MCP server with its own agent-config.yaml. The sales and ops configs are embedded in the deployment templates in the CTF repo.

## Full deployment

The complete multi-department deployment (Trino, Nessie, MinIO, SpiceDB, Keycloak, ArgoCD app-of-apps, Kagenti zero-trust) is in a separate repo:

- https://github.com/eformat/data-agent-ctf
