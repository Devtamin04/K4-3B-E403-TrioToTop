from __future__ import annotations

from app.composition import build_evaluator, build_student
from app.config import EvaluatorSettings, StudentSettings
from app.factory import create_app

_evaluator_settings = EvaluatorSettings.from_env()

app = create_app(
    evaluator=build_evaluator(_evaluator_settings),
    student=build_student(StudentSettings.from_env(), _evaluator_settings),
)
