from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from agentefinanciero.adapters.inbound.http.router import router
from agentefinanciero.application.ports.inbound import AnalyzeQueryUseCase
from agentefinanciero.config.container import build_use_case
from agentefinanciero.config.settings import Settings


def create_app(use_case: AnalyzeQueryUseCase | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if not hasattr(app.state, "use_case"):
            app.state.use_case = build_use_case(Settings())
        yield

    app = FastAPI(title="Agente de Análisis Financiero", lifespan=lifespan)
    if use_case is not None:
        app.state.use_case = use_case
    app.include_router(router)
    return app


app = create_app()
