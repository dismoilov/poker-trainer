"""
SQLAlchemy models for live game sessions and hand history.
"""

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, JSON,
    ForeignKey, func,
)
from app.db import Base


class GameSessionModel(Base):
    """A live poker session between hero and villain."""
    __tablename__ = "game_sessions"

    id = Column(String, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    hero_position = Column(String, nullable=False, default="IP")
    villain_position = Column(String, nullable=False, default="OOP")
    starting_stack = Column(Float, nullable=False, default=100.0)
    hero_stack = Column(Float, nullable=False, default=100.0)
    villain_stack = Column(Float, nullable=False, default=100.0)
    hands_played = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False, default="active")  # active, completed
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class HandRecordModel(Base):
    """Record of a single hand within a session."""
    __tablename__ = "hand_records"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("game_sessions.id"), nullable=False)
    hand_number = Column(Integer, nullable=False)
    board = Column(JSON, nullable=False, default=[])      # list of card strings
    hero_hand = Column(JSON, nullable=False, default=[])   # hero hole cards
    villain_hand = Column(JSON, nullable=False, default=[]) # villain hole cards
    pot = Column(Float, nullable=False, default=0.0)
    hero_won = Column(Float, nullable=False, default=0.0)
    villain_won = Column(Float, nullable=False, default=0.0)
    result = Column(String, nullable=False, default="")    # "hero_win", "villain_win", "split", "fold"
    actions_json = Column(JSON, nullable=False, default=[]) # list of action records
    created_at = Column(DateTime, nullable=False, server_default=func.now())
