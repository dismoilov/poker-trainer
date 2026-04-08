"""
Pydantic schemas for game session API.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class CreateSessionRequest(BaseModel):
    startingStack: float = 100.0
    heroPosition: str = "IP"       # IP or OOP


class SessionState(BaseModel):
    sessionId: str
    status: str                     # active, waiting_action, showdown, hand_complete, completed
    handsPlayed: int
    heroStack: float
    villainStack: float
    pot: float
    board: list[str]
    heroHand: list[str]
    villainHand: list[str]          # empty until showdown
    street: str
    currentPlayer: str              # IP or OOP
    legalActions: list[LegalAction]
    actionHistory: list[ActionEntry]
    lastResult: Optional[str] = None
    winningSummary: Optional[str] = None
    stateRecovered: bool = False    # True if live state was lost and re-dealt
    recoveryNote: Optional[str] = None  # explains what happened during recovery


class LegalAction(BaseModel):
    type: str        # fold, check, call, bet, raise, allin
    amount: float = 0.0
    label: str = ""


class ActionEntry(BaseModel):
    player: str      # IP or OOP
    type: str
    amount: float
    street: str


class TakeActionRequest(BaseModel):
    sessionId: str
    actionType: str
    amount: float = 0.0


class TakeActionResponse(BaseModel):
    state: SessionState
    villainAction: Optional[ActionEntry] = None   # if villain auto-acted


class HandRecord(BaseModel):
    id: str
    handNumber: int
    board: list[str]
    heroHand: list[str]
    villainHand: list[str]
    pot: float
    heroWon: float
    villainWon: float
    result: str
    actions: list[ActionEntry]


# Fix forward reference
SessionState.model_rebuild()
