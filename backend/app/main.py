from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.interpretation import router as interpretation_router
from app.api.reading import router as reading_router

app = FastAPI(
    title="Raidian API",
    version="0.1.0"
)

app.include_router(auth_router)
app.include_router(reading_router)
app.include_router(interpretation_router)


@app.get("/")
def root():
    return {
        "application": "Raidian",
        "status": "running",
        "version": "0.1.0"
    }