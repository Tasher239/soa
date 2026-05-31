from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

import numpy as np

from cinema_shared.logging import get_logger
from cinema_shared.schemas.events import DeviceType, EventType, MovieEvent

from app.application.publish_event import PublishEventUseCase
from app.core.config import settings

logger = get_logger("producer.simulator")

_DEVICE_WEIGHTS = [
    (DeviceType.MOBILE, 0.45),
    (DeviceType.DESKTOP, 0.35),
    (DeviceType.TV, 0.15),
    (DeviceType.TABLET, 0.05),
]


def _pick_device() -> DeviceType:
    r = random.random()
    acc = 0.0
    for d, w in _DEVICE_WEIGHTS:
        acc += w
        if r <= acc:
            return d
    return DeviceType.MOBILE


@dataclass
class SimulatorState:
    running: bool = False
    task: asyncio.Task | None = None
    rps: int = 0
    concurrent_users: int = 0
    events_published: int = 0
    started_at: datetime | None = None


class SessionSimulator:
    SEARCH_TERMS = [
        "action 2026", "romantic comedy", "sci fi classics", "thriller tonight",
        "best animation", "family weekend", "documentary", "new releases",
    ]

    def __init__(self, publisher: PublishEventUseCase) -> None:
        self._publisher = publisher
        self._state = SimulatorState()
        self._rng = np.random.default_rng()
        pool = settings.generator_movie_pool
        self._movie_ids = [f"m_{i:04d}" for i in range(pool)]
        self._user_ids = [f"u_{i:05d}" for i in range(settings.generator_user_pool)]

    @property
    def status(self) -> dict:
        return {
            "running": self._state.running,
            "rps": self._state.rps,
            "concurrent_users": self._state.concurrent_users,
            "events_published": self._state.events_published,
            "started_at": self._state.started_at.isoformat() if self._state.started_at else None,
        }

    async def start(self, rps: int | None = None, users: int | None = None) -> None:
        if self._state.running:
            return
        self._state.rps = rps or settings.generator_rps
        self._state.concurrent_users = users or settings.generator_concurrent_users
        self._state.started_at = datetime.now(timezone.utc)
        self._state.events_published = 0
        self._state.running = True
        self._state.task = asyncio.create_task(self._run(), name="simulator-supervisor")
        logger.info(
            "simulator_started",
            rps=self._state.rps,
            users=self._state.concurrent_users,
            user_pool=len(self._user_ids),
            movie_pool=len(self._movie_ids),
        )

    async def stop(self) -> None:
        if not self._state.running:
            return
        self._state.running = False
        if self._state.task:
            self._state.task.cancel()
            try:
                await self._state.task
            except (asyncio.CancelledError, Exception):
                pass
        logger.info("simulator_stopped", total_events=self._state.events_published)

    async def _run(self) -> None:
        workers = [
            asyncio.create_task(self._worker(i), name=f"simulator-{i}")
            for i in range(self._state.concurrent_users)
        ]
        try:
            await asyncio.gather(*workers, return_exceptions=True)
        except asyncio.CancelledError:
            for w in workers:
                w.cancel()
            raise

    def _pick_movie(self) -> str:
        pool = len(self._movie_ids)
        a = settings.generator_zipf_a
        raw = self._rng.zipf(a)
        idx = min(pool - 1, max(0, int(raw) - 1))
        return self._movie_ids[idx]

    def _pick_user(self) -> str:
        return random.choice(self._user_ids)

    async def _maybe_throttle(self) -> None:
        per_worker_rps = max(1, self._state.rps // max(1, self._state.concurrent_users))
        jitter = random.uniform(0.5, 1.5)
        await asyncio.sleep(jitter / per_worker_rps)

    async def _emit(self, event: MovieEvent) -> None:
        try:
            await self._publisher(event)
            self._state.events_published += 1
        except Exception as exc:
            logger.warning("simulator_publish_failed", error=str(exc))

    async def _worker(self, wid: int) -> None:
        logger.debug("simulator_worker_started", wid=wid)
        while self._state.running:
            try:
                await self._run_session()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("simulator_session_error", wid=wid, error=str(exc))
                await asyncio.sleep(0.5)

    async def _run_session(self) -> None:
        user_id = self._pick_user()
        movie_id = self._pick_movie()
        device = _pick_device()
        session_id = uuid4().hex

        if random.random() < 0.05:
            await self._emit(self._make_event(
                user_id, movie_id, EventType.SEARCHED, device, session_id,
                progress=None, query=random.choice(self.SEARCH_TERMS),
            ))
            await self._maybe_throttle()

        await self._emit(self._make_event(
            user_id, movie_id, EventType.VIEW_STARTED, device, session_id, progress=0,
        ))
        await self._maybe_throttle()

        progress = 0
        target = random.randint(1200, 7200)
        pause_chance = 0.2

        while progress < target and self._state.running:
            step = random.randint(30, 180)
            progress = min(target, progress + step)

            if random.random() < pause_chance and progress < target - 30:
                await self._emit(self._make_event(
                    user_id, movie_id, EventType.VIEW_PAUSED, device, session_id, progress=progress,
                ))
                await self._maybe_throttle()
                await self._emit(self._make_event(
                    user_id, movie_id, EventType.VIEW_RESUMED, device, session_id, progress=progress,
                ))
                await self._maybe_throttle()

        await self._emit(self._make_event(
            user_id, movie_id, EventType.VIEW_FINISHED, device, session_id, progress=target,
        ))
        await self._maybe_throttle()

        if random.random() < 0.2:
            await self._emit(self._make_event(
                user_id, movie_id, EventType.LIKED, device, session_id, progress=None,
            ))
            await self._maybe_throttle()

    @staticmethod
    def _make_event(
        user_id: str,
        movie_id: str,
        event_type: EventType,
        device: DeviceType,
        session_id: str,
        progress: int | None,
        query: str | None = None,
    ) -> MovieEvent:
        return MovieEvent(
            event_id=uuid4(),
            user_id=user_id,
            movie_id=movie_id,
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            device_type=device,
            session_id=session_id,
            progress_seconds=progress,
            search_query=query,
            client_version="sim/1.0",
        )
