from fastapi import APIRouter, FastAPI

from app.config import settings

app = FastAPI(title="LedgerLens API", version=settings.app_version)

api_router = APIRouter(prefix="/api")


def health_response() -> dict[str, str]:
    return {"status": "ok", "version": settings.app_version}


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return health_response()


@api_router.get("/health", tags=["health"])
def api_health() -> dict[str, str]:
    return health_response()


app.include_router(api_router)
