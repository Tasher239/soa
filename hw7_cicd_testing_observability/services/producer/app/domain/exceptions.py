from __future__ import annotations


class ProducerError(Exception):
    error_code: str = "PRODUCER_ERROR"
    http_status: int = 500

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class PublishFailed(ProducerError):
    error_code = "PUBLISH_FAILED"
    http_status = 503


class GeneratorAlreadyRunning(ProducerError):
    error_code = "GENERATOR_ALREADY_RUNNING"
    http_status = 409


class GeneratorNotRunning(ProducerError):
    error_code = "GENERATOR_NOT_RUNNING"
    http_status = 409
