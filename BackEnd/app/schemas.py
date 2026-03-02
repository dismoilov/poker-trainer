"""Pydantic schemas — must match FrontEnd/src/types/index.ts exactly."""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


# ─── Auth ───
class LoginRequest(BaseModel):
    username: str
    password: str


class UserInfo(BaseModel):
    id: int
    username: str


class LoginResponse(BaseModel):
    accessToken: str
    user: UserInfo


# ─── Action ───
class Action(BaseModel):
    id: str
    label: str
    type: str
    size: Optional[float] = None


# ─── Spot ───
class Spot(BaseModel):
    id: str
    name: str
    format: str
    positions: list[str]
    stack: int
    rakeProfile: str
    streets: list[str]
    tags: list[str]
    solved: bool
    nodeCount: int
    isCustom: bool = False


class SpotCreateRequest(BaseModel):
    format: str          # SRP, 3bet, 4bet, squeeze
    positions: list[str] # [IP_pos, OOP_pos]
    street: str          # flop, turn, river
    stack: int = 100     # stack in bb


# ─── TreeNode ───
class TreeNode(BaseModel):
    id: str
    spotId: str
    street: str
    pot: float
    player: str
    actions: list[Action]
    parentId: Optional[str] = None
    lineDescription: str
    children: list[str]
    actionLabel: Optional[str] = None


# ─── Drill ───
class DrillNextRequest(BaseModel):
    spotId: str
    nodeId: Optional[str] = None


class DrillQuestion(BaseModel):
    questionId: str
    spotId: str
    nodeId: str
    board: list[str]
    hand: str
    handCards: list[str]
    position: str
    potSize: float
    stackSize: int
    actions: list[Action]
    lineDescription: str
    street: str


class DrillAnswerRequest(BaseModel):
    nodeId: str
    hand: str
    actionId: str
    questionId: Optional[str] = None


class DrillFeedback(BaseModel):
    frequencies: dict[str, float]
    chosenAction: str
    correctAction: str
    evLoss: float
    accuracy: float
    explanation: list[str]


# ─── Jobs ───
class JobCreateRequest(BaseModel):
    spotId: str


class Job(BaseModel):
    id: str
    type: str
    spotId: Optional[str] = None
    spotName: Optional[str] = None
    status: str
    progress: int
    createdAt: str
    log: list[str]


# ─── Analytics ───
class AnalyticsSummary(BaseModel):
    totalSessions: int
    totalQuestions: int
    avgEvLoss: float
    accuracy: float


class AnalyticsRow(BaseModel):
    date: str
    evLoss: float
    accuracy: float
    questions: int


class AnalyticsQuestion(BaseModel):
    id: str
    spotName: str
    spotId: str
    nodeId: str
    board: list[str]
    hand: str
    position: str
    chosenAction: str
    correctAction: str
    evLoss: float
    accuracy: float
    lineDescription: str
    date: str


class GameDetail(BaseModel):
    id: str
    spotName: str
    spotId: str
    nodeId: str
    board: list[str]
    hand: str
    position: str
    chosenAction: str
    correctAction: str
    evLoss: float
    accuracy: float
    lineDescription: str
    date: str
    frequencies: dict[str, float]
    explanation: list[str]


class HandDetail(BaseModel):
    hand: str
    tier: int
    tierLabel: str
    frequencies: dict[str, float]
    connection: str
    explanation: list[str]
