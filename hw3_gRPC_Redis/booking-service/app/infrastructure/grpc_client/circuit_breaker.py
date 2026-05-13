import asyncio
import logging
import time
from enum import Enum

import grpc

from app.domain.exceptions import ServiceUnavailableError

logger = logging.getLogger(__name__)

RETRYABLE_CODES = {grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED}
BACKOFFS = [0.1, 0.2, 0.4]


class State(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, timeout: int = 30):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.state = State.CLOSED
        self.failure_count = 0
        self.last_failure_time: float = 0.0

    async def call(self, func, *args, **kwargs):
        if self.state == State.OPEN:
            if time.time() - self.last_failure_time > self.timeout:
                self._transition(State.HALF_OPEN)
            else:
                raise ServiceUnavailableError("Circuit breaker is OPEN — flight service unavailable")

        last_exception = None
        for attempt, delay in enumerate(BACKOFFS + [None]):
            try:
                result = await func(*args, **kwargs)
                self._on_success()
                return result
            except grpc.aio.AioRpcError as e:
                last_exception = e
                if e.code() not in RETRYABLE_CODES or delay is None:
                    break
                logger.warning(
                    f"gRPC call failed (attempt {attempt + 1}/{len(BACKOFFS) + 1}): "
                    f"code={e.code()}, retrying in {delay}s"
                )
                await asyncio.sleep(delay)
            except Exception as e:
                last_exception = e
                break

        self._on_failure()
        raise ServiceUnavailableError(str(last_exception)) from last_exception

    def _on_success(self):
        if self.state == State.HALF_OPEN:
            self._transition(State.CLOSED)
        self.failure_count = 0

    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.state == State.HALF_OPEN or self.failure_count >= self.failure_threshold:
            self._transition(State.OPEN)

    def _transition(self, new_state: State):
        logger.info(f"Circuit Breaker: {self.state.value} → {new_state.value}")
        self.state = new_state
        if new_state == State.CLOSED:
            self.failure_count = 0
