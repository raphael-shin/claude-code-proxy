from __future__ import annotations

from api.app import create_app
from api.dependencies import AppDependencies


def test_create_app_installs_default_dependencies() -> None:
    app = create_app()

    assert isinstance(app.state.dependencies, AppDependencies)


def test_create_app_keeps_injected_dependencies() -> None:
    dependencies = AppDependencies()

    app = create_app(dependencies)

    assert app.state.dependencies is dependencies

