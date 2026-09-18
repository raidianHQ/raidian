from fastapi import FastAPI

from app.api.interpretation import router as interpretation_router

app = FastAPI(
    title="Raidian API",
    version="0.1.0"
)

app.include_router(interpretation_router)


@app.get("/")
def root():
    return {
        "application": "Raidian",
        "status": "running",
        "version": "0.1.0"
    }