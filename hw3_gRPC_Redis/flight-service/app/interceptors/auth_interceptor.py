import logging

import grpc
import grpc.aio

from app.core.config import settings

logger = logging.getLogger(__name__)


class ApiKeyInterceptor(grpc.aio.ServerInterceptor):
    async def intercept_service(self, continuation, handler_call_details):
        metadata = dict(handler_call_details.invocation_metadata)
        api_key = metadata.get("x-api-key")
        if api_key != settings.FLIGHT_SERVICE_API_KEY:
            logger.warning("Unauthorized gRPC call: missing or invalid API key")

            async def abort_handler(request, context):
                await context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid or missing API key")

            return grpc.unary_unary_rpc_method_handler(abort_handler)
        return await continuation(handler_call_details)
