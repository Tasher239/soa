import asyncio
import logging

import grpc

from app.core.config import settings
from app.generated import flight_pb2_grpc
from app.interceptors.auth_interceptor import ApiKeyInterceptor
from app.servicer import FlightServiceServicer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def serve():
    server = grpc.aio.server(interceptors=[ApiKeyInterceptor()])
    flight_pb2_grpc.add_FlightServiceServicer_to_server(FlightServiceServicer(), server)
    listen_addr = f"0.0.0.0:{settings.GRPC_PORT}"
    server.add_insecure_port(listen_addr)
    logger.info(f"Flight gRPC service starting on {listen_addr}")
    await server.start()
    await server.wait_for_termination()


if __name__ == "__main__":
    asyncio.run(serve())
