"""Application entrypoint for RKAA."""

import logging

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from rkaa.core.config import load_settings
from rkaa.core.error_handlers import register_error_handlers
from rkaa.core.exceptions import NotFoundError
from rkaa.core.logging import configure_logging, new_correlation_id, set_correlation_id
from rkaa.presentation.api.baseline import router as baseline_router
from rkaa.presentation.api.data_quality_report import router as data_quality_report_router
from rkaa.presentation.api.impact import router as impact_router
from rkaa.presentation.api.impact_analysis import router as impact_analysis_router
from rkaa.presentation.api.knowledge import router as knowledge_router
from rkaa.presentation.api.kpi_import import router as kpi_import_router

settings = load_settings()
configure_logging(settings.logging.level)

logger = logging.getLogger("rkaa.app")
app = FastAPI(title=settings.app.name)
app.state.settings = settings
register_error_handlers(app)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID", new_correlation_id())
        set_correlation_id(correlation_id)

        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response


app.add_middleware(CorrelationIdMiddleware)
app.include_router(kpi_import_router)
app.include_router(data_quality_report_router)
app.include_router(baseline_router)
app.include_router(impact_router)
app.include_router(impact_analysis_router)
app.include_router(knowledge_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Simple health endpoint for bootstrapping."""
    logger.info("health check ok")
    return {"status": "ok"}


@app.get("/test/items/{item_id}")
def get_test_item(item_id: int) -> dict[str, int]:
    return {"item_id": item_id}


@app.get("/test/not-found")
def get_not_found() -> None:
    raise NotFoundError()


@app.get("/test/crash")
def get_crash() -> None:
    raise RuntimeError("boom")
