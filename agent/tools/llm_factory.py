"""LLM factory: creates provider-appropriate chat models for each agent node.

For OpenAI-compatible relays we bypass langchain-openai entirely and call
the openai SDK directly, avoiding _create_chat_result / model_dump errors
caused by relay services that return non-standard response envelopes.
"""

import os
from typing import Any, List, Optional

import openai
from langchain_anthropic import ChatAnthropic
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

# Default model per node — overridden by AGENT_MODEL_<NODE> env var
_NODE_DEFAULTS: dict[str, str] = {
    "ingest":  "openai",
    "plan":    "openai",
    "execute": "openai",
    "review":  "anthropic",
    "test":    "openai",
    "evolve":  "openai",
}


class _OpenAIDirectChatModel(BaseChatModel):
    """Calls openai.OpenAI directly — works with any OpenAI-compatible relay."""

    model_name: str

    @property
    def _llm_type(self) -> str:
        return "openai-direct"

    @property
    def _identifying_params(self) -> dict:
        return {"model_name": self.model_name}

    def _to_openai_messages(self, messages: List[BaseMessage]) -> list[dict]:
        role_map = {"human": "user", "ai": "assistant", "system": "system", "tool": "tool"}
        return [{"role": role_map.get(m.type, "user"), "content": m.content} for m in messages]

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        client = openai.OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL") or None,
        )
        params: dict[str, Any] = {
            "model": self.model_name,
            "messages": self._to_openai_messages(messages),
        }
        if stop:
            params["stop"] = stop

        response = client.chat.completions.create(**params)
        content = response.choices[0].message.content or ""
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])


def make_llm(node: str) -> BaseChatModel:
    """Return the correct LLM for a node.

    Resolution order:
      1. AGENT_MODEL_<NODE>   (e.g. AGENT_MODEL_REVIEW=claude-opus-4-7)
      2. ANTHROPIC_MODEL / OPENAI_MODEL  (provider-level default)
      3. Built-in fallback
    """
    provider_hint = _NODE_DEFAULTS.get(node, "openai")
    if provider_hint == "anthropic":
        fallback = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    else:
        fallback = os.getenv("OPENAI_MODEL", "gpt-5.4")

    model = os.getenv(f"AGENT_MODEL_{node.upper()}", fallback)

    if "claude" in model.lower():
        return ChatAnthropic(model=model)
    else:
        return _OpenAIDirectChatModel(model_name=model)
