"""Tests for deploy template rendering."""

from pathlib import Path

from data_agent_core.config.models import (
    DeploymentConfig,
    DomainConfig,
    ResourceSpec,
)
from data_agent_core.deploy.render import (
    build_template_vars,
    render_deploy_tree,
    render_template,
    TEMPLATES_DIR,
)


def _make_config(**overrides) -> DomainConfig:
    defaults = dict(
        domain_name="test-agent",
        domain_display_name="Test Agent",
        domain_description="A test agent",
        trino_schema="test",
        mlflow_experiment_name="test-data-agent",
        mlflow_prompt_name="test-agent.system",
        mlflow_span_name="test_agent",
        deployment=DeploymentConfig(
            namespace="test-ns",
            model_name="test-model",
            model_endpoint="http://model.example.com/v1",
            s3_endpoint="http://minio.minio.svc.cluster.local:9000",
            s3_bucket="test-data",
        ),
    )
    defaults.update(overrides)
    return DomainConfig(**defaults)


def test_resource_spec_defaults():
    r = ResourceSpec()
    assert r.cpu_request == "200m"
    assert r.memory_request == "512Mi"
    assert r.cpu_limit == "1"
    assert r.memory_limit == "1Gi"


def test_deployment_config_defaults():
    d = DeploymentConfig()
    assert d.replicas == 1
    assert d.trino_host == "trino.trino.svc.cluster.local"
    assert d.trino_port == 8443
    assert d.chainlit_pvc_size == "2Gi"
    assert d.route_timeout == "600s"
    assert d.route_tls_termination == "edge"
    assert d.mcp_resources.cpu_request == "100m"
    assert d.mcp_resources.cpu_limit == "500m"


def test_build_template_vars():
    config = _make_config()
    v = build_template_vars(config)
    assert v["DOMAIN_NAME"] == "test-agent"
    assert v["NAMESPACE"] == "test-ns"
    assert v["MODEL_NAME"] == "test-model"
    assert v["TRINO_PORT"] == "8443"
    assert v["AGENT_CPU_REQUEST"] == "200m"
    assert v["MCP_CPU_LIMIT"] == "500m"
    assert v["S3_ENDPOINT_HOST"] == "minio.minio.svc.cluster.local:9000"
    assert v["CHAINLIT_PVC_SIZE"] == "2Gi"


def test_build_template_vars_namespace_fallback():
    config = _make_config(deployment=DeploymentConfig())
    v = build_template_vars(config)
    assert v["NAMESPACE"] == "test-agent"


def test_render_template(tmp_path):
    tmpl = tmp_path / "test.yaml"
    tmpl.write_text("name: ${DOMAIN_NAME}\nns: ${NAMESPACE}")
    result = render_template(tmpl, {"DOMAIN_NAME": "foo", "NAMESPACE": "bar"})
    assert result == "name: foo\nns: bar"


def test_render_template_safe_substitute(tmp_path):
    tmpl = tmp_path / "test.yaml"
    tmpl.write_text("name: ${DOMAIN_NAME}\nunknown: ${NOT_A_VAR}")
    result = render_template(tmpl, {"DOMAIN_NAME": "foo"})
    assert "foo" in result
    assert "${NOT_A_VAR}" in result


def test_render_deploy_tree(tmp_path):
    config = _make_config()
    name = config.domain_name

    # Create directory structure that render_deploy_tree expects
    for d in [
        tmp_path / "agents" / f"{name}-agent" / "deploy",
        tmp_path / "agents" / f"{name}-mcp-server" / "deploy",
        tmp_path / "deploy",
        tmp_path / "scripts",
    ]:
        d.mkdir(parents=True, exist_ok=True)

    render_deploy_tree(config, tmp_path)

    # Agent manifests
    agent_deploy = tmp_path / "agents" / f"{name}-agent" / "deploy"
    assert (agent_deploy / "deployment.yaml").exists()
    assert (agent_deploy / "service.yaml").exists()
    assert (agent_deploy / "route.yaml").exists()
    assert (agent_deploy / "chainlit-pvc.yaml").exists()
    assert (agent_deploy / "buildconfig.yaml").exists()
    assert (agent_deploy / "imagestream.yaml").exists()
    assert (agent_deploy / "kustomization.yaml").exists()

    # MCP server manifests
    mcp_deploy = tmp_path / "agents" / f"{name}-mcp-server" / "deploy"
    assert (mcp_deploy / "deployment.yaml").exists()
    assert (mcp_deploy / "service.yaml").exists()
    assert (mcp_deploy / "buildconfig.yaml").exists()
    assert (mcp_deploy / "imagestream.yaml").exists()
    assert (mcp_deploy / "kustomization.yaml").exists()

    # Common manifests
    common = tmp_path / "deploy"
    assert (common / "dspa.yaml").exists()
    assert (common / "mlflow-rbac.yaml").exists()
    assert (common / "pipeline-s3-secret.yaml").exists()
    assert (common / "maas-key-secret.yaml").exists()
    assert (common / "kustomization.yaml").exists()

    # Scripts
    scripts = tmp_path / "scripts"
    assert (scripts / "deploy-all.sh").exists()
    assert (scripts / "set-model.sh").exists()
    assert (scripts / "register-prompt.sh").exists()

    # Makefile
    assert (tmp_path / "Makefile").exists()

    # Containerfiles
    assert (tmp_path / "agents" / f"{name}-agent" / "Containerfile").exists()
    assert (tmp_path / "agents" / f"{name}-mcp-server" / "Containerfile").exists()


def test_rendered_values_substituted(tmp_path):
    config = _make_config()
    render_deploy_tree(config, tmp_path)

    name = config.domain_name
    deployment = (tmp_path / "agents" / f"{name}-agent" / "deploy" / "deployment.yaml").read_text()
    assert f"name: {name}-agent" in deployment
    assert "namespace: test-ns" in deployment
    assert "test-model" in deployment
    assert "${DOMAIN_NAME}" not in deployment
    assert "${NAMESPACE}" not in deployment


def test_containerfile_uses_ubi(tmp_path):
    config = _make_config()
    render_deploy_tree(config, tmp_path)

    name = config.domain_name
    agent_cf = (tmp_path / "agents" / f"{name}-agent" / "Containerfile").read_text()
    mcp_cf = (tmp_path / "agents" / f"{name}-mcp-server" / "Containerfile").read_text()

    assert "ubi9/python-312" in agent_cf
    assert "ubi9/python-312-minimal" in agent_cf
    assert "python:3.12-slim" not in agent_cf

    assert "ubi9/python-312" in mcp_cf
    assert "ubi9/python-312-minimal" in mcp_cf
    assert "python:3.12-slim" not in mcp_cf


def test_buildconfig_references_imagestream(tmp_path):
    config = _make_config()
    render_deploy_tree(config, tmp_path)

    name = config.domain_name
    bc = (tmp_path / "agents" / f"{name}-agent" / "deploy" / "buildconfig.yaml").read_text()
    assert f"name: {name}-agent:latest" in bc
    assert "kind: ImageStreamTag" in bc


def test_scripts_executable(tmp_path):
    import os
    import stat

    config = _make_config()
    render_deploy_tree(config, tmp_path)

    for script in (tmp_path / "scripts").iterdir():
        if script.suffix == ".sh":
            mode = os.stat(script).st_mode
            assert mode & stat.S_IXUSR, f"{script.name} should be executable"
