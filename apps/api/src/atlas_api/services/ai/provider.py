"""Claude client wrapper with tool-use mode, retry, and cost tracking.

Every Claude call goes through `call_tool()`, which:
1. Checks the daily token cap — short-circuits if exceeded.
2. Sends a tool-use request with a strict JSON schema.
3. Validates the response against the expected Pydantic model.
4. On schema violation, retries once.
5. On any failure after retry, returns None (caller falls back).
6. Records token usage for cost tracking.
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import UTC, datetime
from typing import Any, TypeVar

import anthropic
import httpx
import structlog
from pydantic import BaseModel, ValidationError

from atlas_api.config import settings

log = structlog.get_logger()
T = TypeVar("T", bound=BaseModel)

# ── Daily token counter (in-memory, prototype-grade) ───────────────────────


class _DailyTokenCounter:
    """Thread-safe daily token counter. Resets at midnight UTC."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._date: str = ""
        self._total: int = 0

    def _maybe_reset(self) -> None:
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        if self._date != today:
            self._date = today
            self._total = 0

    def add(self, tokens: int) -> None:
        with self._lock:
            self._maybe_reset()
            self._total += tokens

    def remaining(self) -> int:
        with self._lock:
            self._maybe_reset()
            return max(0, settings.ai_daily_token_cap - self._total)

    @property
    def total_today(self) -> int:
        with self._lock:
            self._maybe_reset()
            return self._total

    def is_exceeded(self) -> bool:
        return self.remaining() <= 0


token_counter = _DailyTokenCounter()


# ── Tool schema builder ───────────────────────────────────────────────────


def _pydantic_to_tool_schema(name: str, description: str, model: type[BaseModel]) -> dict[str, Any]:
    """Convert a Pydantic model to an Anthropic tool definition."""
    schema = model.model_json_schema()
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    return {
        "name": name,
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


# ── Core call function ────────────────────────────────────────────────────


def _get_client() -> anthropic.Anthropic:
    """Lazy client construction. Raises if no API key configured."""
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")
    return anthropic.Anthropic(
        api_key=settings.anthropic_api_key,
        timeout=httpx.Timeout(60.0, connect=10.0),
    )


def compute_prompt_hash(messages: list[dict[str, Any]], system: str) -> str:
    """SHA-256 of the serialized prompt (messages + system)."""
    blob = json.dumps({"system": system, "messages": messages}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def compute_input_hash(grounding_data: dict[str, Any]) -> str:
    """SHA-256 of the grounding data used to build the prompt."""
    blob = json.dumps(grounding_data, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def call_tool[T: BaseModel](
    *,
    messages: list[dict[str, Any]],
    system: str,
    tool_name: str,
    tool_description: str,
    result_model: type[T],
    max_tokens: int = 2048,
) -> tuple[T | None, dict[str, Any]]:
    """Call Claude with a single tool and parse the result.

    Returns:
        (parsed_result, metadata_dict) where metadata contains:
        - model, tokens_in, tokens_out, prompt_hash, raw_response
        On failure: (None, metadata_dict)
    """
    meta: dict[str, Any] = {
        "model": settings.ai_model,
        "tokens_in": 0,
        "tokens_out": 0,
        "prompt_hash": compute_prompt_hash(messages, system),
        "raw_response": None,
        "error": None,
    }

    # Check token cap
    if token_counter.is_exceeded():
        meta["error"] = "daily_token_cap_exceeded"
        log.warning("ai_token_cap_exceeded", remaining=0, cap=settings.ai_daily_token_cap)
        return None, meta

    tool_def = _pydantic_to_tool_schema(tool_name, tool_description, result_model)
    client = _get_client()

    for attempt in range(2):  # 1 try + 1 retry
        try:
            response = client.messages.create( # type: ignore[call-overload]
                model=settings.ai_model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
                tools=[tool_def],
                tool_choice={"type": "tool", "name": tool_name},
            )

            # Track tokens
            usage = response.usage
            tokens_used = (usage.input_tokens or 0) + (usage.output_tokens or 0)
            token_counter.add(tokens_used)
            meta["tokens_in"] = usage.input_tokens or 0
            meta["tokens_out"] = usage.output_tokens or 0

            # Extract tool use block
            tool_block = None
            for block in response.content:
                if block.type == "tool_use" and block.name == tool_name:
                    tool_block = block
                    break

            if tool_block is None:
                meta["error"] = f"no_tool_use_block_attempt_{attempt}"
                log.warning("ai_no_tool_block", attempt=attempt, tool=tool_name)
                if attempt == 0:
                    continue
                return None, meta

            meta["raw_response"] = tool_block.input

            # Validate against Pydantic model
            try:
                parsed = result_model.model_validate(tool_block.input)
                return parsed, meta
            except ValidationError as ve:
                meta["error"] = f"validation_error_attempt_{attempt}: {ve}"
                log.warning("ai_validation_error", attempt=attempt, error=str(ve))
                if attempt == 0:
                    continue
                return None, meta

        except httpx.TimeoutException as e:
            meta["error"] = f"timeout_attempt_{attempt}: {e}"
            log.warning("ai_timeout", attempt=attempt, error=str(e))
            if attempt == 0:
                continue
            return None, meta
        except anthropic.APIError as e:
            meta["error"] = f"api_error_attempt_{attempt}: {e}"
            log.warning("ai_api_error", attempt=attempt, error=str(e))
            if attempt == 0:
                continue
            return None, meta
        except Exception as e:
            meta["error"] = f"unexpected_error: {e}"
            log.exception("ai_unexpected_error")
            return None, meta

    return None, meta
