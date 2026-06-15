"""Callback handler for tracking timing and tool usage."""

from __future__ import annotations

import time

from langchain_core.callbacks import BaseCallbackHandler


class TracingHandler(BaseCallbackHandler):
    """Tracks tool invocations and timing during agent execution."""

    def __init__(self):
        self.last_tool_end: float | None = None
        self.tool_names: list[str] = []

    def on_tool_start(self, serialized, input_str, **kwargs):
        self.tool_names.append(serialized.get("name", "tool"))

    def on_tool_end(self, output, **kwargs):
        self.last_tool_end = time.time()
