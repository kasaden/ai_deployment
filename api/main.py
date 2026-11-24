"""API FastAPI : expose le modèle NER entraîné (output/model-best).

Lancement local : uvicorn api.main:app --port 8000
"""

import os
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import spacy
from fastapi import FastAPI, Request
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool

from api.monitoring import EsRequestLogger, RequestLogger
from api.schemas import MAX_CHARS, Entity, ExtractRequest, ExtractResponse, HealthResponse
from ner_core.entities import FIELD, group_entities

__all__ = ["MAX_CHARS", "app", "create_app"]

ROOT = Path(__file__).resolve().parent.parent


def create_app(model_path: Path, request_logger: RequestLogger | None) -> FastAPI:
    nlp = spacy.load(model_path)
    model_id = f"{nlp.meta.get('lang')}_{nlp.meta.get('name')}-{nlp.meta.get('version')}"
    labels = list(nlp.get_pipe("ner").labels)

    @asynccontextmanager
    async def lifespan(_app):
        if request_logger is not None:
            request_logger.ensure_index()
        yield

    app = FastAPI(
        title="TASS NER API",
        description="Repère armes (WEAPON), unités (MIL_UNIT) et organisations militaires "
        "(MIL_ORG) dans un texte anglais.",
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def monitor(request: Request, call_next):
        start = time.perf_counter()
        watched = request_logger is not None and request.url.path == "/extract"

        def record(status):
            rec = {
                "@timestamp": datetime.now(UTC).isoformat(),
                "route": request.url.path,
                "status": status,
                "latency_ms": round((time.perf_counter() - start) * 1000, 2),
                "model": model_id,
            }
            rec.update(getattr(request.state, "prediction", {}))
            return rec

        try:
            response = await call_next(request)
        except Exception:
            # Erreur serveur : on la journalise (statut 500) avant de la laisser remonter.
            if watched:
                await run_in_threadpool(request_logger.log, record(500))
            raise
        if watched:
            response.background = BackgroundTask(request_logger.log, record(response.status_code))
        return response

    @app.get("/health", response_model=HealthResponse)
    def health():
        return HealthResponse(status="ok", model=model_id, labels=labels)

    @app.post("/extract", response_model=ExtractResponse)
    def extract(body: ExtractRequest, request: Request):
        start = time.perf_counter()
        doc = nlp(body.text)
        groups = group_entities(doc)
        entities = [
            Entity(text=e.text, label=e.label_, start=e.start_char, end=e.end_char)
            for e in doc.ents
            if e.label_ in FIELD
        ]
        request.state.prediction = {
            "n_chars": len(body.text),
            **{f"n_{field}": len(values) for field, values in groups.items()},
        }
        return ExtractResponse(
            entities=entities,
            model=model_id,
            latency_ms=round((time.perf_counter() - start) * 1000, 2),
            **groups,
        )

    return app


app = create_app(
    Path(os.environ.get("MODEL_PATH", ROOT / "output" / "model-best")),
    EsRequestLogger.from_env(),
)
