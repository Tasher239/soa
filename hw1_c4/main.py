from server import router as healthcheck_router
from fastapi import FastAPI

app = FastAPI()
app.include_router(healthcheck_router)