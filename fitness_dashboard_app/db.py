from __future__ import annotations
from sqlmodel import SQLModel, create_engine, Session
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "fitness.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, connect_args={"check_same_thread": False})

def init_db():
    from models import User, DailyMetric, Measurement, Wellbeing, Adherence, Photo, Week  # ensure tables imported
    SQLModel.metadata.create_all(engine)

def get_session() -> Session:
    return Session(engine)
