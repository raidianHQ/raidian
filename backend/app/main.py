from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.ai_narrative import router as ai_narrative_router
from app.api.auth import router as auth_router
from app.api.interpretation import router as interpretation_router
from app.api.journal import router as journal_router
from app.api.reading import router as reading_router
from app.api.reference_data import router as reference_data_router
from app.api.scripture import router as scripture_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Raidian API",
    version="0.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth_router)
app.include_router(reading_router)
app.include_router(interpretation_router)
app.include_router(reference_data_router)
app.include_router(scripture_router)
app.include_router(ai_narrative_router)
app.include_router(journal_router)


@app.get("/")
def root():
    return {
        "application": "Raidian",
        "status": "running",
        "version": "0.2.0"
    }