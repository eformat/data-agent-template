.PHONY: install test validate dev schema lint clean \
       retail-deploy retail-restart retail-expose retail-build retail-status

install:
	pip install -e ".[all]"

test:
	pytest tests/ -v

validate:
	data-agent validate --config examples/nndss/agent-config.yaml
	data-agent validate --config examples/mlb/agent-config.yaml

dev:
	data-agent dev --config examples/nndss/agent-config.yaml

schema:
	data-agent schema

lint:
	python -m py_compile src/data_agent_core/cli.py
	python -m py_compile src/data_agent_core/config/models.py
	python -m py_compile src/data_agent_core/agent/dev.py
	python -m py_compile src/data_agent_core/deploy/render.py
	python -m py_compile src/data_agent_core/eval/pipeline.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf *.egg-info build dist .pytest_cache

# ── Retail Demo (OpenShell sandboxes) ──────────────────────────

retail-build: ## Build and push Hermes sandbox + MCP server images
	podman build -f examples/retail/deploy/Containerfile.hermes-sandbox -t quay.io/eformat/hermes-openshell:latest .
	podman push quay.io/eformat/hermes-openshell:latest
	podman build -f examples/retail/deploy/mcp-server/Containerfile -t quay.io/eformat/retail-mcp-server:latest .
	podman push quay.io/eformat/retail-mcp-server:latest

retail-deploy: ## Deploy all 3 retail sandboxes (finance, sales, ops)
	./examples/retail/deploy/sandbox/deploy-sandbox.sh finance sales ops

retail-restart: ## Restart all 3 retail sandboxes (delete + recreate + expose)
	./examples/retail/deploy/sandbox/restart-sandbox.sh all

retail-restart-%: ## Restart one sandbox: make retail-restart-finance
	./examples/retail/deploy/sandbox/restart-sandbox.sh $*

retail-expose: ## Re-expose all sandbox services (idempotent)
	./examples/retail/deploy/sandbox/expose-all.sh

retail-status: ## Show sandbox status
	@openshell sandbox list -g $${OPENSHELL_GATEWAY:-prelude2-final} 2>/dev/null
	@echo "---"
	@openshell service list -g $${OPENSHELL_GATEWAY:-prelude2-final} 2>/dev/null
