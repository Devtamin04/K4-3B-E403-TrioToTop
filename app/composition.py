from __future__ import annotations

from pathlib import Path

from app.adapters.evaluator_fake import FixtureEvaluator
from app.adapters.evaluator_llm import LlmEvaluator
from app.adapters.student_fake import DeterministicStudentGenerator
from app.adapters.student_llm import LlmStudentGenerator
from app.config import ConfigurationError, EvaluatorSettings, StudentSettings
from app.llm.interfaces import StructuredLlmClient
from app.teachback.interfaces import Evaluator, StudentGenerator

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def build_student(
    student_settings: StudentSettings,
    evaluator_settings: EvaluatorSettings,
) -> StudentGenerator:
    if student_settings.backend == "deterministic":
        return DeterministicStudentGenerator()
    if student_settings.model is None:
        raise ConfigurationError("LLM student requires STUDENT_MODEL")
    if evaluator_settings.backend == "fixture":
        raise ConfigurationError(
            "LLM student requires a live LLM_PROVIDER; fixture mode has no provider"
        )
    return LlmStudentGenerator(
        client=build_llm_client(evaluator_settings),
        model=student_settings.model,
        prompt_path=PROJECT_ROOT / "app" / "prompts" / "student_v1.md",
        max_attempts=student_settings.max_attempts,
        timeout_seconds=student_settings.timeout_seconds,
    )


def build_evaluator(settings: EvaluatorSettings) -> Evaluator:
    if settings.backend == "fixture":
        if settings.fixture_path is None:
            raise ConfigurationError("fixture evaluator requires EVALUATOR_FIXTURE_PATH")
        return FixtureEvaluator(settings.fixture_path)

    if settings.model is None:
        raise ConfigurationError("live evaluator requires EVALUATOR_MODEL")
    return LlmEvaluator(
        client=build_llm_client(settings),
        model=settings.model,
        prompt_path=PROJECT_ROOT / "app" / "prompts" / f"{settings.prompt_version}.md",
        max_attempts=settings.max_attempts,
        timeout_seconds=settings.timeout_seconds,
    )


def build_llm_client(settings: EvaluatorSettings) -> StructuredLlmClient:
    client: StructuredLlmClient
    if settings.backend == "ollama":
        from app.llm.ollama_client import OllamaStructuredLlmClient

        if settings.api_key is None or settings.base_url is None:
            raise ConfigurationError("Ollama provider requires OLLAMA_API_KEY and OLLAMA_BASE_URL")
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

        if settings.api_key is None:
            raise ConfigurationError("OpenAI provider requires OPENAI_API_KEY")
        client = OpenAiStructuredLlmClient(settings.api_key)

    return client
