from fastapi import FastAPI

app = FastAPI(
    title="Raidian API",
    version="0.1.0"
)


@app.get("/")
def root():
    return {
        "application": "Raidian",
        "status": "running",
        "version": "0.1.0"
    }