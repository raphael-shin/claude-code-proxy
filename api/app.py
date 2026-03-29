from __future__ import annotations

from fastapi import FastAPI

from api.dependencies import AppDependencies
from api.health_router import router as health_router
from api.proxy_router import router as proxy_router


def create_app(dependencies: AppDependencies | None = None) -> FastAPI:
    app = FastAPI(title="Claude Code Proxy")
    app.state.dependencies = dependencies or AppDependencies()
    app.include_router(proxy_router)
    app.include_router(health_router)
    return app
