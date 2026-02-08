from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def healthcheck(name: str) -> str:
    return f'Hello, {name}!'
