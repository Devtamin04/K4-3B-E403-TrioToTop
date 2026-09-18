from __future__ import annotations

from app.composition import build_evaluator
from app.config import EvaluatorSettings
from app.factory import create_app

app = create_app(evaluator=build_evaluator(EvaluatorSettings.from_env()))
