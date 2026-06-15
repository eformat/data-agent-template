"""System prompt with MLflow Prompt Registry integration."""

from __future__ import annotations

import os


class PromptManager:
    """Manages system prompts with MLflow registry fallback."""

    def __init__(self, prompt_name: str, default_prompt: str):
        self._prompt_name = prompt_name
        self._default = default_prompt
        self._mlflow_enabled = False

    def register(self) -> None:
        """Register prompt in MLflow if not already present."""
        mlflow_uri = os.environ.get("MLFLOW_TRACKING_URI", "").strip()
        if not mlflow_uri:
            return

        try:
            import mlflow

            try:
                existing = mlflow.genai.load_prompt(self._prompt_name, version=1, allow_missing=True)
                if existing is None:
                    mlflow.genai.register_prompt(
                        name=self._prompt_name,
                        template=self._default,
                        commit_message="Initial registration",
                        tags={"source": "data-agent-core"},
                    )
                    mlflow.genai.set_prompt_alias(self._prompt_name, alias="production", version=1)
                    print(f"[prompts] Registered '{self._prompt_name}' v1 in MLflow", flush=True)
                else:
                    print(f"[prompts] '{self._prompt_name}' already exists (v{existing.version})", flush=True)
            except Exception as exc:
                print(f"[prompts] Failed to register '{self._prompt_name}': {exc}", flush=True)

            self._mlflow_enabled = True
        except Exception as exc:
            print(f"[prompts] MLflow unavailable: {exc}", flush=True)

    def get_prompt(self) -> str:
        """Load system prompt from MLflow or fallback to default."""
        if not self._mlflow_enabled:
            return self._default
        try:
            import mlflow
            prompt = mlflow.genai.load_prompt(
                f"prompts:/{self._prompt_name}@production",
                allow_missing=True,
                cache_ttl_seconds=60,
            )
            if prompt:
                return prompt.template
        except Exception:
            pass
        return self._default


def create_prompt_manager(prompt_name: str, default_prompt: str) -> PromptManager:
    """Create a PromptManager for the given prompt name and default."""
    return PromptManager(prompt_name, default_prompt)
