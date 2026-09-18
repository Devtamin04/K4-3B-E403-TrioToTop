from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast


class ConfigurationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class EvaluatorSettings:
    backend: Literal["ollama", "openai", "fixture"]
    model: str | None
    api_key: str | None
    base_url: str | None
    ollama_send_format: bool
    max_attempts: int
    timeout_seconds: float
    fixture_path: Path | None

    @classmethod
    def from_env(cls) -> EvaluatorSettings:
        evaluator_backend = os.getenv("EVALUATOR_BACKEND")
        if evaluator_backend == "fixture":
            backend: Literal["ollama", "openai", "fixture"] = "fixture"
        elif evaluator_backend is not None:
            raise ConfigurationError(
                "EVALUATOR_BACKEND may only be set to 'fixture'; "
                "use LLM_PROVIDER for live evaluators"
            )
        else:
            raw_provider = os.getenv("LLM_PROVIDER")
            if raw_provider not in {"ollama", "openai"}:
                raise ConfigurationError(
                    "LLM_PROVIDER must be explicitly set to 'ollama' or 'openai'"
                )
            backend = cast(Literal["ollama", "openai", "fixture"], raw_provider)
        max_attempts = _positive_int("EVALUATOR_MAX_ATTEMPTS", default=2)
        timeout_seconds = _positive_float("EVALUATOR_TIMEOUT_SECONDS", default=30)

        if backend == "ollama":
            api_key = _required("OLLAMA_API_KEY")
            model = _required("EVALUATOR_MODEL")
            base_url = os.getenv("OLLAMA_BASE_URL", "https://ollama.com").strip()
            if not base_url:
                raise ConfigurationError("OLLAMA_BASE_URL must not be empty")
            ollama_send_format = _boolean("OLLAMA_USE_FORMAT", default=False)
            fixture_path = None
        elif backend == "openai":
            api_key = _required("OPENAI_API_KEY")
            model = _required("EVALUATOR_MODEL")
            base_url = None
            ollama_send_format = False
            fixture_path = None
        else:
            api_key = None
            model = None
            base_url = None
            ollama_send_format = False
            fixture_path = Path(_required("EVALUATOR_FIXTURE_PATH"))

        return cls(
            backend=backend,
            model=model,
            api_key=api_key,
            base_url=base_url,
            ollama_send_format=ollama_send_format,
            max_attempts=max_attempts,
            timeout_seconds=timeout_seconds,
            fixture_path=fixture_path,
        )


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigurationError(f"{name} must be set")
    return value


def _positive_int(name: str, *, default: int) -> int:
    raw = os.getenv(name)
    try:
        value = default if raw is None else int(raw)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be an integer") from error
    if value < 1:
        raise ConfigurationError(f"{name} must be at least 1")
    return value


def _positive_float(name: str, *, default: float) -> float:
    raw = os.getenv(name)
    try:
        value = default if raw is None else float(raw)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be numeric") from error
    if value <= 0:
        raise ConfigurationError(f"{name} must be positive")
    return value


def _boolean(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} must be a boolean")
