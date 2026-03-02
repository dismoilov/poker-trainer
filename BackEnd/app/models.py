"""SQLAlchemy ORM models."""

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, JSON,
    ForeignKey, func,
)
from app.db import Base


class UserModel(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    is_admin = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class SpotModel(Base):
    __tablename__ = "spots"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    format = Column(String, nullable=False)
    positions = Column(JSON, nullable=False)
    stack = Column(Integer, nullable=False, default=100)
    rake_profile = Column(String, nullable=False, default="low")
    streets = Column(JSON, nullable=False)
    tags = Column(JSON, nullable=False, default=[])
    solved = Column(Boolean, nullable=False, default=False)
    node_count = Column(Integer, nullable=False, default=0)
    is_custom = Column(Boolean, nullable=False, default=False)


class NodeModel(Base):
    __tablename__ = "nodes"

    id = Column(String, primary_key=True)
    spot_id = Column(String, ForeignKey("spots.id"), nullable=False)
    street = Column(String, nullable=False)
    pot = Column(Float, nullable=False)
    player = Column(String, nullable=False)
    actions = Column(JSON, nullable=False)
    parent_id = Column(String, nullable=True)
    line_description = Column(String, nullable=False)
    children = Column(JSON, nullable=False, default=[])
    action_label = Column(String, nullable=True)


class StrategyModel(Base):
    __tablename__ = "strategies"

    node_id = Column(String, primary_key=True)
    matrix_json = Column(Text, nullable=False)
    updated_at = Column(DateTime, nullable=False, server_default=func.now())


class JobModel(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    type = Column(String, nullable=False, default="solve")
    spot_id = Column(String, nullable=True)
    spot_name = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending")
    progress = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())


class JobLogModel(Base):
    __tablename__ = "job_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False)
    ts = Column(DateTime, nullable=False, server_default=func.now())
    message = Column(String, nullable=False)


class DrillAnswerModel(Base):
    __tablename__ = "drill_answers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    spot_id = Column(String, nullable=False)
    spot_name = Column(String, nullable=False, default="")
    node_id = Column(String, nullable=False)
    board = Column(JSON, nullable=False, default=[])
    hand = Column(String, nullable=False)
    chosen_action = Column(String, nullable=False)
    correct_action = Column(String, nullable=False)
    ev_loss = Column(Float, nullable=False, default=0.0)
    accuracy = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
