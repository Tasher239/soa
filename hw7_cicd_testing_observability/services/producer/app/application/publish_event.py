from __future__ import annotations

from uuid import UUID

from cinema_shared.schemas.events import MovieEvent, MovieEventIn

from app.infra.kafka_producer import AvroKafkaProducer


class PublishEventUseCase:
    def __init__(self, producer: AvroKafkaProducer) -> None:
        self._producer = producer

    async def __call__(self, payload: MovieEventIn | MovieEvent) -> UUID:
        event = payload if isinstance(payload, MovieEvent) else payload.materialize()
        await self._producer.publish(event)
        return event.event_id
