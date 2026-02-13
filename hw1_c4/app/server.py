from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def healthcheck() -> dict:
    return {"status": "ok"}
