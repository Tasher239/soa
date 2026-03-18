import asyncio
import logging

import grpc

logger = logging.getLogger(__name__)

RETRYABLE_CODES = {grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED}
BACKOFFS = [0.1, 0.2, 0.4]


class RetryInterceptor(grpc.aio.UnaryUnaryClientInterceptor):
    async def intercept_unary_unary(self, continuation, client_call_details, request):
        last_exception = None
        for attempt, delay in enumerate(BACKOFFS + [None]):
            try:
                return await continuation(client_call_details, request)
            except grpc.aio.AioRpcError as e:
                last_exception = e
                if e.code() not in RETRYABLE_CODES or delay is None:
                    raise
                logger.warning(
                    f"gRPC call failed (attempt {attempt + 1}/{len(BACKOFFS) + 1}): "
                    f"code={e.code()}, retrying in {delay}s"
                )
                await asyncio.sleep(delay)
        raise last_exception
