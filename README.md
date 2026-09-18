# Teach-Back AI Chatbot

The repository implements the deterministic Teach-Back skeleton plus an
isolated, real hidden evaluator. The human teaches and the visible AI remains a
deterministic student. The product contract and architectural source of truth
are in [`cons.MD`](cons.MD).

## Development

```bash
uv sync --group dev
uv run ruff format --check .
uv run ruff check .
uv run mypy app tests
uv run pytest
```

Run the API locally with:

```bash
LLM_PROVIDER=ollama \
OLLAMA_BASE_URL=https://ollama.com \
OLLAMA_API_KEY=... \
EVALUATOR_MODEL=... \
uv run uvicorn app.main:app --reload
```

There is no hardcoded model and no implicit evaluator fallback. Copy
`.env.example` to your preferred environment-loading mechanism and explicitly
select Ollama, optional OpenAI, or fixture mode.

Ollama Cloud is used through its native `/api/chat` endpoint. Because Cloud
does not currently guarantee server-side structured outputs, the evaluator
always embeds the Pydantic JSON Schema in its prompt, requires JSON-only output,
and validates `message.content` locally. `OLLAMA_USE_FORMAT=false` is the safe
Cloud default; it can be enabled for Ollama runtimes that support the `format`
field.

The fixture evaluator remains available for deterministic tests. It only
recognizes exact messages declared in `tests/fixtures/evaluator_cases.yaml` and
does not attempt to imitate natural-language understanding.

## Evaluator regressions

The offline run validates the regression dataset, metric calculations, state
transitions, and false-completion safety without network access:

```bash
uv run python -m evals.runner --mode offline
```

Run the real evaluator separately when credentials and an explicit model are
available:

```bash
LLM_PROVIDER=ollama OLLAMA_API_KEY=... EVALUATOR_MODEL=... \
uv run python -m evals.runner --mode live
```

The initial metric thresholds are provisional engineering gates for this small
regression set. They are not evidence of general evaluator quality. False
completion risk must remain zero.
