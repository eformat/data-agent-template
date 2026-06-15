"""data-agent CLI — scaffold, validate, dev, test, build, deploy."""

import click


@click.group()
@click.version_option(package_name="data-agent-core")
def main():
    """Data Agent Framework — build methodology-aware agents on Trino/Iceberg."""


@main.command()
@click.argument("name")
@click.option("--output-dir", default=".", help="Parent directory for the new project.")
def init(name: str, output_dir: str):
    """Scaffold a new domain agent project."""
    from data_agent_core.scaffold.generate import scaffold_project

    scaffold_project(name, output_dir)
    click.echo(f"Scaffolded project: {name}/")


@main.command()
@click.option("--config", default="agent-config.yaml", help="Path to agent-config.yaml.")
def validate(config: str):
    """Validate agent-config.yaml against the DomainConfig schema."""
    from data_agent_core.config.loader import load_config

    try:
        cfg = load_config(config)
        click.echo(f"Valid: {cfg.domain_display_name} ({cfg.domain_name})")
    except Exception as exc:
        click.echo(f"Validation error: {exc}", err=True)
        raise SystemExit(1)


@main.command()
@click.option("--config", default="agent-config.yaml", help="Path to agent-config.yaml.")
@click.option("--port", default=8080, help="Chainlit port.")
@click.option("--host", default="0.0.0.0", help="Chainlit host.")
@click.option("--trino-live", is_flag=True, default=False, help="Connect to real Trino + SpiceDB instead of DuckDB.")
def dev(config: str, port: int, host: str, trino_live: bool):
    """Run the agent locally with mock Trino (DuckDB) and mock SpiceDB."""
    import os
    import subprocess
    import sys
    import tempfile
    from pathlib import Path

    from data_agent_core.config.loader import load_config

    cfg = load_config(config)
    mode = "LIVE" if trino_live else "DEV"
    click.echo(f"[{mode}] Config: {cfg.domain_display_name} ({cfg.domain_name})")

    config_abs = str(Path(config).resolve())

    dev_dir = tempfile.mkdtemp(prefix=f"data-agent-dev-{cfg.domain_name}-")
    db_path = os.path.join(dev_dir, "dev.duckdb")

    os.environ["DATA_AGENT_DEV_MODE"] = "1"
    os.environ["CHAINLIT_DB_PATH"] = os.path.join(dev_dir, "chainlit.db")

    if not os.environ.get("CHAINLIT_AUTH_SECRET"):
        import secrets
        os.environ["CHAINLIT_AUTH_SECRET"] = secrets.token_hex(32)

    dev_app = os.path.join(dev_dir, "app.py")
    with open(dev_app, "w") as f:
        f.write(f'''"""Auto-generated dev mode app."""
import os
os.environ["DATA_AGENT_DEV_MODE"] = "1"
os.environ["CHAINLIT_DB_PATH"] = {repr(os.environ["CHAINLIT_DB_PATH"])}

from data_agent_core.config.loader import load_config
from data_agent_core.agent.dev import create_dev_app

config = load_config({repr(config_abs)})
create_dev_app(config, db_path={repr(db_path)}, trino_live={trino_live})
''')

    click.echo(f"DuckDB: {db_path}")
    click.echo(f"Dev app: {dev_app}")
    click.echo(f"Starting Chainlit on http://{host}:{port}")
    click.echo("Login: admin / admin")
    click.echo("---")

    # Run chainlit
    result = subprocess.run(
        [sys.executable, "-m", "chainlit", "run", dev_app,
         "--port", str(port), "--host", host, "--headless"],
        check=False,
    )
    raise SystemExit(result.returncode)


@main.command()
@click.option("--config", default="agent-config.yaml", help="Path to agent-config.yaml.")
def test(config: str):
    """Run the test matrix (unit, integration, eval pipeline compile)."""
    import subprocess
    import sys

    result = subprocess.run([sys.executable, "-m", "pytest", "-v"], check=False)
    raise SystemExit(result.returncode)


@main.command()
def schema():
    """Print the DomainConfig JSON Schema."""
    from data_agent_core.config.schema import get_json_schema

    import json
    click.echo(json.dumps(get_json_schema(), indent=2))
