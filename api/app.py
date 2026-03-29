from __future__ import annotations

from fastapi import FastAPI

from api.admin_budget_policies import router as admin_budget_policies_router
from api.admin_model_mappings import router as admin_model_mappings_router
from api.admin_usage import router as admin_usage_router
from api.admin_users import router as admin_users_router
from api.admin_virtual_keys import router as admin_virtual_keys_router
from api.dependencies import AppDependencies
from api.health_router import router as health_router
from api.internal_ops import router as internal_ops_router
from api.proxy_router import router as proxy_router


def create_app(dependencies: AppDependencies | None = None) -> FastAPI:
    app = FastAPI(title="Claude Code Proxy")
    app.state.dependencies = dependencies or AppDependencies()
    app.include_router(proxy_router)
    app.include_router(admin_users_router)
    app.include_router(admin_budget_policies_router)
    app.include_router(admin_virtual_keys_router)
    app.include_router(admin_model_mappings_router)
    app.include_router(admin_usage_router)
    app.include_router(internal_ops_router)
    app.include_router(health_router)
    return app
