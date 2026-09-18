class TeachBackError(Exception):
    """Base class for expected application errors."""


class NotFoundError(TeachBackError):
    pass


class SessionNotActiveError(TeachBackError):
    pass


class InvalidEvaluationError(TeachBackError):
    pass


class EvaluationFailedError(TeachBackError):
    pass
