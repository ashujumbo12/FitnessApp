# models.py
from typing import Optional, List
from datetime import date
from sqlmodel import Field, SQLModel, Relationship

class User(SQLModel, table=True):
    __tablename__ = "user"                       # ⬅️ back to original table name
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: Optional[str] = None
    height_cm: Optional[float] = None
    goal_weight_kg: Optional[float] = None
    units: str = "metric"  # metric/imperial

    # one-to-many
    weeks: List["Week"] = Relationship(back_populates="user")

class Week(SQLModel, table=True):
    __tablename__ = "week"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    week_number: int
    start_date: date

    # many-to-one
    user: Optional[User] = Relationship(back_populates="weeks")

    # one-to-many
    dailies: List["DailyMetric"] = Relationship(back_populates="week")
    photos: List["Photo"] = Relationship(back_populates="week")

    # one-to-one
    measurement: Optional["Measurement"] = Relationship(back_populates="week")
    wellbeing: Optional["Wellbeing"] = Relationship(back_populates="week")
    adherence: Optional["Adherence"] = Relationship(back_populates="week")

class DailyMetric(SQLModel, table=True):
    __tablename__ = "dailymetric"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    date: date
    week_id: Optional[int] = Field(default=None, foreign_key="week.id")
    weight_kg: Optional[float] = None
    steps: Optional[int] = None
    run_km: Optional[float] = None

    week: Optional[Week] = Relationship(back_populates="dailies")

class Measurement(SQLModel, table=True):
    __tablename__ = "measurement"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    week_id: int = Field(foreign_key="week.id", unique=True)

    r_biceps_in: Optional[float] = None
    l_biceps_in: Optional[float] = None
    chest_in: Optional[float] = None
    r_thigh_in: Optional[float] = None
    l_thigh_in: Optional[float] = None
    waist_navel_in: Optional[float] = None

    week: Optional[Week] = Relationship(back_populates="measurement")

class Wellbeing(SQLModel, table=True):
    __tablename__ = "wellbeing"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    week_id: int = Field(foreign_key="week.id", unique=True)

    sleep_issues: Optional[int] = None  # 0-5
    hunger_issues: Optional[int] = None  # 0-5
    stress_issues: Optional[int] = None  # 0-5

    week: Optional[Week] = Relationship(back_populates="wellbeing")

class Adherence(SQLModel, table=True):
    __tablename__ = "adherence"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    week_id: int = Field(foreign_key="week.id", unique=True)

    diet_score: Optional[int] = None  # 0-10
    workout_score: Optional[int] = None  # 0-10

    week: Optional[Week] = Relationship(back_populates="adherence")

class Photo(SQLModel, table=True):
    __tablename__ = "photo"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    week_id: int = Field(foreign_key="week.id")
    pose: str  # front / back / side / most-muscular
    path: str

    week: Optional[Week] = Relationship(back_populates="photos")
    
# --- NEW: track health expenses ---------------------------------------------
class Expense(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    date: date
    amount: float = 0.0
    category: str = "Other"     # e.g., Supplements, Coaching, Gym, Physio, Equipment, Tests, Other
    note: Optional[str] = None