from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.database import Base, engine
from app.routers import ai, auth, export, files, logs, plans, profile

app = FastAPI(
    title="Personal Learning Agent",
    description="A personal learning management AI Agent for logs, memory, planning, reminders, and tech news.",
    version="0.2.0",
)

Base.metadata.create_all(bind=engine)


def ensure_legacy_columns() -> None:
    with engine.begin() as connection:
        for table in ("learning_logs", "ai_messages"):
            columns = {
                row[1]
                for row in connection.execute(text(f"PRAGMA table_info({table})")).fetchall()
            }
            if "username" not in columns:
                connection.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN username VARCHAR(80) DEFAULT 'default'")
                )
        profile_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(user_profiles)")).fetchall()
        }
        for column in (
            "professional_identity",
            "research_direction",
            "goal_profile",
            "ability_status",
            "knowledge_mastery",
            "execution_habits",
            "time_constraints",
            "risk_preference",
            "memory_notes",
        ):
            if column not in profile_columns:
                connection.execute(text(f"ALTER TABLE user_profiles ADD COLUMN {column} TEXT DEFAULT ''"))


ensure_legacy_columns()


@app.get("/api/health")
def health_check():
    return {"message": "Personal Learning Agent is running"}


app.include_router(logs.router)
app.include_router(ai.router)
app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(files.router)
app.include_router(plans.router)
app.include_router(export.router)

app.mount("/assets", StaticFiles(directory="assets"), name="assets")
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
