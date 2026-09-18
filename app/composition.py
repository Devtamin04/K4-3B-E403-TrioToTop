from __future__ import annotations

from pathlib import Path

from app.adapters.evaluator_fake import FixtureEvaluator
from app.adapters.evaluator_llm import LlmEvaluator
from app.config import ConfigurationError, EvaluatorSettings
from app.llm.interfaces import StructuredLlmClient
from app.teachback.interfaces import Evaluator

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def build_evaluator(settings: EvaluatorSettings) -> Evaluator:
    if settings.backend == "fixture":
        if settings.fixture_path is None:
            raise ConfigurationError("fixture evaluator requires EVALUATOR_FIXTURE_PATH")
        return FixtureEvaluator(settings.fixture_path)

    client: StructuredLlmClient
    if settings.backend == "ollama":
        from app.llm.ollama_client import OllamaStructuredLlmClient

        if settings.api_key is None or settings.model is None or settings.base_url is None:
            raise ConfigurationError(
                "Ollama evaluator requires OLLAMA_API_KEY, OLLAMA_BASE_URL, and EVALUATOR_MODEL"
            )
        client = OllamaStructuredLlmClient(
            api_key=settings.api_key,
            base_url=settings.base_url,
            send_format=settings.ollama_send_format,
        )
    else:
        try:
            from app.llm.openai_client import OpenAiStructuredLlmClient
        except ImportError as error:
            raise ConfigurationError(
                "OpenAI provider requires the optional 'openai' dependency"
            ) from error

        if settings.api_key is None or settings.model is None:
            raise ConfigurationError("OpenAI evaluator requires OPENAI_API_KEY and EVALUATOR_MODEL")
        client = OpenAiStructuredLlmClient(settings.api_key)

    if settings.model is None:
        raise ConfigurationError("live evaluator requires EVALUATOR_MODEL")
    return LlmEvaluator(
        client=client,
        model=settings.model,
        prompt_path=PROJECT_ROOT / "app" / "prompts" / "evaluator_v1.md",
        max_attempts=settings.max_attempts,
        timeout_seconds=settings.timeout_seconds,
    )
