from __future__ import annotations

from fastapi import FastAPI

from api.dependencies import AppDependencies


def create_app(dependencies: AppDependencies | None = None) -> FastAPI:
    app = FastAPI(title="Claude Code Proxy")
    app.state.dependencies = dependencies or AppDependencies()
    return app

