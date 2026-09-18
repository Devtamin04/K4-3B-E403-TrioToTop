class LlmError(Exception):
    """Provider-neutral base error."""


class LlmTransientError(LlmError):
    """A timeout, connection failure, rate limit, or retryable server error."""


class LlmPermanentError(LlmError):
    """A configuration, authentication, or non-retryable request error."""


class LlmInvalidOutputError(LlmError):
    """The provider did not return valid structured output."""


class LlmRefusalError(LlmError):
    """The provider declined to produce the requested evaluation."""
