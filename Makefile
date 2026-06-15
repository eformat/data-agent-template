.PHONY: install test validate dev schema lint clean

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
