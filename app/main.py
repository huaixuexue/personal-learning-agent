from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.routers import logs

app = FastAPI(
    title="Personal Learning Agent",
    description="A personal learning management AI Agent for logs, memory, planning, reminders, and tech news.",
    version="0.2.0",
)

Base.metadata.create_all(bind=engine)


@app.get("/api/health")
def health_check():
    return {"message": "Personal Learning Agent is running"}


app.include_router(logs.router)

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
