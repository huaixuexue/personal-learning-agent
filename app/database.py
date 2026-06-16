from sqlalchemy import create_engine
from pathlib import Path

from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./data/learning_agent.db"

Path("data").mkdir(exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)  #创建数据库会话类
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
