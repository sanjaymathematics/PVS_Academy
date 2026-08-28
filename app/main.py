import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import models
from .database import engine
from .routers import auth_router, materials, quizzes, answer_sheets

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Slate — teaching platform API",
    description="Materials, quizzes with auto-grading, and answer-sheet review.",
    version="0.1.0",
)

app.include_router(auth_router.router)
app.include_router(materials.router)
app.include_router(quizzes.router)
app.include_router(answer_sheets.router)


@app.get("/api/status")
def status():
    return {"status": "ok", "docs": "/docs"}


# Serve the frontend from the same origin as the API — no CORS needed.
# Visit http://localhost:8000/app/ once the server is running.
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
