"""Dev mode agent app — DuckDB backend, mock SpiceDB, no MLflow.

Usage:
    from data_agent_core.agent.dev import create_dev_app
    from data_agent_core.config.loader import load_config
    config = load_config("agent-config.yaml")
    create_dev_app(config, db_path="/tmp/dev.duckdb")
"""

from __future__ import annotations

import asyncio
import os
import time

from data_agent_core.agent.chainlit_db import init_db
from data_agent_core.agent.output import clean_output
from data_agent_core.agent.tracing import TracingHandler
from data_agent_core.config.models import DomainConfig


def create_dev_app(
    config: DomainConfig,
    db_path: str = ":memory:",
    trino_live: bool = False,
) -> None:
    """Register Chainlit handlers for local development.

    Args:
        config: Domain configuration.
        db_path: DuckDB database path (ignored when trino_live=True).
        trino_live: If True, connect to real Trino + SpiceDB instead of
                    DuckDB + mock permissions.
    """
    import chainlit as cl
    from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
    from langchain_openai import ChatOpenAI
    from langgraph.prebuilt import create_react_agent
    from langchain_core.messages import HumanMessage, AIMessage

    conninfo = init_db()
    cl.data._data_layer = SQLAlchemyDataLayer(conninfo=conninfo)

    from data_agent_core.tools.metadata import (
        create_describe_datasets_tool,
        create_get_methodology_tool,
    )

    describe_datasets = create_describe_datasets_tool(config)
    get_methodology = create_get_methodology_tool(config)

    if trino_live:
        from data_agent_core.tools.trino import create_query_trino_tool
        from data_agent_core.tools.spicedb import create_check_permission_tool

        query_trino_tool = create_query_trino_tool(config)
        check_permission = create_check_permission_tool()

        tools = [query_trino_tool, describe_datasets, get_methodology, check_permission]
        mode = "live"
        print(f"[live] Tools: {[t.name for t in tools]}", flush=True)
        print(f"[live] Trino: {os.environ.get('TRINO_QUERY_HOST', 'trino')}:{os.environ.get('TRINO_QUERY_PORT', '8080')}", flush=True)
        print(f"[live] SpiceDB: {os.environ.get('SPICEDB_ENDPOINT', 'dev:50051')}", flush=True)
    else:
        import duckdb
        from data_agent_core.tools.trino import create_query_duckdb_tool
        from data_agent_core.tools.spicedb import create_mock_permission_tool
        from data_agent_core.testing.sample_data import load_sample_data
        import data_agent_core.testing.retail_sample_data  # noqa: F401 — registers loaders
        import data_agent_core.testing.repo_sample_data  # noqa: F401 — registers loaders

        query_trino_tool, duckdb_conn = create_query_duckdb_tool(config, db_path)
        load_sample_data(duckdb_conn, config)
        check_permission = create_mock_permission_tool()

        tools = [query_trino_tool, describe_datasets, get_methodology, check_permission]
        mode = "dev"
        print(f"[dev] Tools: {[t.name for t in tools]}", flush=True)
        print(f"[dev] DuckDB: {db_path}", flush=True)

    def _build_agent(username: str = "anonymous"):
        llm = ChatOpenAI(
            model=os.environ.get("MODEL_NAME", "qwen36-27b"),
            base_url=os.environ.get(
                "MODEL_ENDPOINT",
                "http://localhost:8000/v1",
            ),
            api_key=os.environ.get("OPENAI_API_KEY", "not-required"),
            temperature=0.3,
            max_tokens=8192,
            streaming=False,
            model_kwargs={
                "extra_body": {
                    "chat_template_kwargs": {"enable_thinking": False}
                }
            },
        )

        prompt = config.system_prompt.replace("{current_user}", username)

        return create_react_agent(
            model=llm,
            tools=tools,
            prompt=prompt,
        )

    # --- Chainlit handlers ---

    @cl.set_starters
    async def starters():
        return [
            cl.Starter(label=s.label, message=s.message)
            for s in config.starters
        ]

    @cl.password_auth_callback
    def auth_callback(username: str, password: str):
        valid_user = os.environ.get("AUTH_USERNAME", "admin")
        valid_pass = os.environ.get("AUTH_PASSWORD", "admin")
        if username == valid_user and password == valid_pass:
            return cl.User(identifier=username, metadata={"role": "admin"})
        return None

    @cl.on_chat_start
    async def start():
        user = cl.user_session.get("user")
        username = user.identifier if user else "anonymous"
        agent = _build_agent(username=username)
        cl.user_session.set("agent", agent)
        cl.user_session.set("chat_history", [])

    @cl.on_message
    async def on_message(message: cl.Message):
        agent = cl.user_session.get("agent")
        chat_history = cl.user_session.get("chat_history")

        t_start = time.time()

        messages = []
        for role, content in chat_history:
            if role == "human":
                messages.append(HumanMessage(content=content))
            else:
                messages.append(AIMessage(content=content))
        messages.append(HumanMessage(content=message.content))

        handler = TracingHandler()

        def _run_agent():
            return agent.invoke(
                {"messages": messages},
                config={"callbacks": [handler]},
            )

        step_desc = config.step_description or f"Query {config.domain_display_name} data..."
        async with cl.Step(name=step_desc, type="run") as step:
            result = await asyncio.get_event_loop().run_in_executor(None, _run_agent)
            if handler.tool_names:
                step.output = "Tools called: " + ", ".join(handler.tool_names)
            else:
                step.output = "Completed"

        t_end = time.time()
        total = t_end - t_start
        query_time = (handler.last_tool_end - t_start) if handler.last_tool_end else 0
        gen_time = total - query_time

        # Extract final AI message
        raw_output = ""
        for m in reversed(result.get("messages", [])):
            if hasattr(m, "type") and m.type == "ai" and not getattr(m, "tool_calls", None):
                raw_output = m.content or ""
                break

        answer, reasoning = clean_output(raw_output)

        # Build footer
        footer_parts = [f"**[{mode.upper()} MODE]**"]
        if handler.tool_names:
            tools_used = ", ".join(f"`{t}`" for t in handler.tool_names)
            footer_parts.append(f"**Tools used:** {tools_used}")

        timing_parts = []
        if query_time > 0:
            timing_parts.append(f"**Query:** {query_time:.1f}s")
        if gen_time > 0:
            timing_parts.append(f"**Generation:** {gen_time:.1f}s")
        timing_parts.append(f"**Total:** {total:.1f}s")
        footer_parts.append(" | ".join(timing_parts))

        footer = "\n\n---\n" + " | ".join(footer_parts)

        msg = cl.Message(content=answer + footer)
        await msg.send()

        # Reasoning step
        if reasoning:
            async with cl.Step(name="Reasoning", type="tool", parent_id=msg.id) as rstep:
                rstep.output = reasoning

        chat_history.extend([
            ("human", message.content),
            ("ai", answer),
        ])
