"""Predictor function factory for evaluation.

Invokes the LangGraph agent directly (same code as the Chainlit app)
rather than calling via HTTP, avoiding Chainlit websocket complexity.
"""

from __future__ import annotations

import os
from typing import Callable

from data_agent_core.config.models import DomainConfig


def create_predict_fn(
    config: DomainConfig,
    model_name: str = "",
    model_endpoint: str = "",
    trino_host: str = "",
    trino_port: int = 8080,
) -> Callable[[str], str]:
    """Create a prediction function that invokes the agent.

    Args:
        config: DomainConfig for the agent.
        model_name: LLM model name (default from env).
        model_endpoint: LLM endpoint URL (default from env).
        trino_host: Trino host (default from env).
        trino_port: Trino port (default from env).
    """
    _model_name = model_name or os.environ.get("MODEL_NAME", "qwen36-27b")
    _model_endpoint = model_endpoint or os.environ.get(
        "MODEL_ENDPOINT", "http://localhost:8000/v1",
    )
    _trino_host = trino_host or os.environ.get("TRINO_QUERY_HOST", "trino")
    _trino_port = trino_port or int(os.environ.get("TRINO_QUERY_PORT", "8080"))

    os.environ["TRINO_QUERY_HOST"] = _trino_host
    os.environ["TRINO_QUERY_PORT"] = str(_trino_port)

    def predict_fn(question: str) -> str:
        try:
            import nest_asyncio
            nest_asyncio.apply()
        except ImportError:
            pass

        from langchain_openai import ChatOpenAI
        from langgraph.prebuilt import create_react_agent
        from langchain_core.messages import HumanMessage

        from data_agent_core.tools.trino import create_query_trino_tool
        from data_agent_core.tools.metadata import (
            create_describe_datasets_tool,
            create_get_methodology_tool,
        )

        query_trino = create_query_trino_tool(config)
        describe_datasets = create_describe_datasets_tool(config)
        get_methodology = create_get_methodology_tool(config)

        llm = ChatOpenAI(
            model=_model_name,
            base_url=_model_endpoint,
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

        agent = create_react_agent(
            model=llm,
            tools=[query_trino, describe_datasets, get_methodology],
            prompt=config.system_prompt,
        )

        try:
            import mlflow
            with mlflow.start_span(name=f"{config.domain_name}-agent-eval") as span:
                span.set_inputs({"question": question})
                result = agent.invoke({"messages": [HumanMessage(content=question)]})
                output = ""
                for m in reversed(result.get("messages", [])):
                    if hasattr(m, "type") and m.type == "ai" and not getattr(m, "tool_calls", None):
                        output = m.content or ""
                        break
                span.set_outputs({"response": output[:500]})
                return output
        except Exception as e:
            print(f"Agent error: {e}")
            return f"Error: {e}"

    return predict_fn
