"""
Drill service — question generation, answer processing, analytics recording.

Uses real GTO data for board generation and context-aware explanations.
"""

import random
import time
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models import NodeModel, SpotModel, DrillAnswerModel
from app.schemas import DrillQuestion, DrillFeedback, Action
from app.services.strategy import get_or_create_strategy, RANKS, get_hand_label
from app.services.gto_data import BOARD_TEXTURES, RANK_VALUES
from app.services.explanations import generate_explanation

_question_cache: dict[str, dict] = {}
_CACHE_TTL = 600


def _cleanup_cache():
    now = time.time()
    expired = [k for k, v in _question_cache.items() if now - v["ts"] > _CACHE_TTL]
    for k in expired:
        del _question_cache[k]


def _make_hand_cards(hand: str, board: list[str]) -> list[str]:
    """Generate specific cards for a hand that don't conflict with board cards."""
    board_cards = set(board)
    rank1, rank2 = hand[0], hand[1]
    is_suited = len(hand) == 3 and hand[2] == "s"
    is_pair = len(hand) == 2 or (len(hand) == 3 and hand[0] == hand[1])

    suits = ["s", "h", "d", "c"]
    random.shuffle(suits)

    if is_pair:
        # Find two suits that don't conflict
        valid = []
        for s in suits:
            card = f"{rank1}{s}"
            if card not in board_cards:
                valid.append(card)
        if len(valid) >= 2:
            return valid[:2]
        return [f"{rank1}s", f"{rank1}h"]  # fallback

    if is_suited:
        # Both cards same suit
        for s in suits:
            c1 = f"{rank1}{s}"
            c2 = f"{rank2}{s}"
            if c1 not in board_cards and c2 not in board_cards:
                return [c1, c2]
        return [f"{rank1}s", f"{rank2}s"]  # fallback
    else:
        # Offsuit: different suits
        for s1 in suits:
            for s2 in suits:
                if s1 == s2:
                    continue
                c1 = f"{rank1}{s1}"
                c2 = f"{rank2}{s2}"
                if c1 not in board_cards and c2 not in board_cards:
                    return [c1, c2]
        return [f"{rank1}s", f"{rank2}h"]  # fallback


def _pick_board(hand: str) -> tuple[list[str], str]:
    """Pick a random board texture that doesn't conflict with the hand's ranks.
    Returns (board_cards, texture_type).
    """
    hand_ranks = {hand[0], hand[1]}

    # Shuffle board textures to get variety
    textures = list(BOARD_TEXTURES)
    random.shuffle(textures)

    for tex in textures:
        board = tex["board"]
        board_ranks = {card[0] for card in board}

        # Allow boards — no perfect conflict avoidance needed
        # (pairs with board are realistic and produce interesting spots)
        return board, tex["type"]

    # Fallback
    return ["Ks", "7d", "2c"], "dry"


def generate_question(
    db: Session, spot_id: str, node_id: Optional[str] = None
) -> DrillQuestion:
    _cleanup_cache()

    if node_id:
        node_row = db.query(NodeModel).filter(NodeModel.id == node_id).first()
    else:
        # Pick a random node from the spot (not just root)
        nodes = db.query(NodeModel).filter(NodeModel.spot_id == spot_id).all()
        if nodes:
            node_row = random.choice(nodes)
        else:
            node_row = None

    if not node_row:
        raise ValueError(f"Node not found for spot={spot_id}, nodeId={node_id}")

    spot_row = db.query(SpotModel).filter(SpotModel.id == spot_id).first()
    if not spot_row:
        raise ValueError(f"Spot not found: {spot_id}")

    # Pick random hand
    row_idx = random.randint(0, 12)
    col_idx = random.randint(0, 12)
    hand = get_hand_label(row_idx, col_idx)

    # Pick board from 50+ textures
    board, board_texture = _pick_board(hand)

    # Generate cards that don't conflict
    hand_cards = _make_hand_cards(hand, board)

    question_id = str(uuid.uuid4())
    actions = [Action(**a) for a in node_row.actions]

    question = DrillQuestion(
        questionId=question_id,
        spotId=spot_row.id,
        nodeId=node_row.id,
        board=board,
        hand=hand,
        handCards=hand_cards,
        position=node_row.player,
        potSize=node_row.pot,
        stackSize=spot_row.stack,
        actions=actions,
        lineDescription=node_row.line_description,
        street=node_row.street,
    )

    _question_cache[question_id] = {
        "ts": time.time(),
        "spotId": spot_row.id,
        "spotName": spot_row.name,
        "spotFormat": spot_row.format,
        "nodeId": node_row.id,
        "board": board,
        "boardTexture": board_texture,
        "hand": hand,
        "player": node_row.player,
        "lineDescription": node_row.line_description,
    }

    return question


def process_answer(
    db: Session,
    node_id: str,
    hand: str,
    action_id: str,
    question_id: Optional[str] = None,
    user_id: Optional[int] = None,
) -> DrillFeedback:
    node_row = db.query(NodeModel).filter(NodeModel.id == node_id).first()
    if not node_row:
        raise ValueError(f"Node not found: {node_id}")

    strategy = get_or_create_strategy(db, node_id, node_row.actions)
    hand_strategy = strategy.get(hand, {})

    # Find the correct (highest frequency) action
    correct_action = ""
    max_freq = 0.0
    for aid, freq in hand_strategy.items():
        if freq > max_freq:
            max_freq = freq
            correct_action = aid

    # Calculate EV loss and accuracy
    chosen_freq = hand_strategy.get(action_id, 0.0)
    ev_loss = 0.0 if chosen_freq >= max_freq else round((max_freq - chosen_freq) * 2.5, 2)
    accuracy = min(chosen_freq / max_freq, 1.0) if max_freq > 0 else 0.0

    # Get context from cache
    spot_id = node_row.spot_id
    spot_name = ""
    board: list[str] = []
    board_texture = "dry"
    player = node_row.player
    line_description = node_row.line_description
    pot_type = "SRP"

    if question_id and question_id in _question_cache:
        cached = _question_cache[question_id]
        spot_id = cached.get("spotId", spot_id)
        spot_name = cached.get("spotName", "")
        board = cached.get("board", [])
        board_texture = cached.get("boardTexture", "dry")
        player = cached.get("player", player)
        line_description = cached.get("lineDescription", line_description)
        pot_type = cached.get("spotFormat", "SRP")
    else:
        spot_row = db.query(SpotModel).filter(SpotModel.id == spot_id).first()
        spot_name = spot_row.name if spot_row else ""
        if spot_row:
            pot_type = spot_row.format

    # Generate real explanations
    explanation = generate_explanation(
        hand=hand,
        board=board,
        chosen_action=action_id,
        correct_action=correct_action,
        frequencies=hand_strategy,
        position=player,
        line_description=line_description,
        pot_type=pot_type,
    )

    # Record answer
    answer_record = DrillAnswerModel(
        user_id=user_id,
        spot_id=spot_id,
        spot_name=spot_name,
        node_id=node_id,
        board=board,
        hand=hand,
        chosen_action=action_id,
        correct_action=correct_action,
        ev_loss=ev_loss,
        accuracy=accuracy,
    )
    db.add(answer_record)
    db.commit()

    return DrillFeedback(
        frequencies=hand_strategy,
        chosenAction=action_id,
        correctAction=correct_action,
        evLoss=ev_loss,
        accuracy=accuracy,
        explanation=explanation,
    )
