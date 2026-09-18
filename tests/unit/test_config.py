from __future__ import annotations

import pytest

from app.config import ConfigurationError, EvaluatorSettings, StudentSettings


def test_provider_selection_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EVALUATOR_BACKEND", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    with pytest.raises(ConfigurationError, match="LLM_PROVIDER"):
        EvaluatorSettings.from_env()


def test_openai_backend_requires_model_and_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EVALUATOR_BACKEND", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("EVALUATOR_MODEL", raising=False)
    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
        EvaluatorSettings.from_env()


def test_fixture_backend_must_be_deliberate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVALUATOR_BACKEND", "fixture")
    monkeypatch.setenv("EVALUATOR_FIXTURE_PATH", "tests/fixtures/evaluator_cases.yaml")

    settings = EvaluatorSettings.from_env()

    assert settings.backend == "fixture"
    assert settings.fixture_path is not None


def test_ollama_configuration_uses_cloud_safe_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EVALUATOR_BACKEND", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_API_KEY", "secret")
    monkeypatch.setenv("EVALUATOR_MODEL", "configured-model")
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_USE_FORMAT", raising=False)

    settings = EvaluatorSettings.from_env()

    assert settings.backend == "ollama"
    assert settings.base_url == "https://ollama.com"
    assert settings.model == "configured-model"
    assert not settings.ollama_send_format


def test_ollama_format_can_be_explicitly_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EVALUATOR_BACKEND", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_API_KEY", "secret")
    monkeypatch.setenv("EVALUATOR_MODEL", "configured-model")
    monkeypatch.setenv("OLLAMA_USE_FORMAT", "true")

    assert EvaluatorSettings.from_env().ollama_send_format


def test_student_defaults_to_the_deterministic_generator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("STUDENT_BACKEND", raising=False)
    monkeypatch.delenv("STUDENT_MODEL", raising=False)

    settings = StudentSettings.from_env()

    assert settings.backend == "deterministic"
    assert settings.model is None


def test_llm_student_requires_an_explicit_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STUDENT_BACKEND", "llm")
    monkeypatch.delenv("STUDENT_MODEL", raising=False)

    with pytest.raises(ConfigurationError, match="STUDENT_MODEL"):
        StudentSettings.from_env()


def test_unknown_student_backend_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STUDENT_BACKEND", "magic")

    with pytest.raises(ConfigurationError, match="STUDENT_BACKEND"):
        StudentSettings.from_env()
