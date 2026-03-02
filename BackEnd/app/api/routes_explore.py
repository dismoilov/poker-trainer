"""Explore API routes — nodes, strategy, and hand detail (auth-protected)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import TreeNode, HandDetail
from app.security import get_current_user
from app.models import UserModel
from app.services import nodes as nodes_service
from app.services.strategy import get_or_create_strategy
from app.services.gto_data import get_hand_tier, hand_connects_with_board, BOARD_TEXTURES
from app.services.explanations import generate_explanation

router = APIRouter(prefix="/api/explore", tags=["explore"])

TIER_LABELS = {
    1: "Premium (Top 3%)",
    2: "Strong (Top 8%)",
    3: "Good (Top 15%)",
    4: "Playable (Top 25%)",
    5: "Marginal (Top 35%)",
    6: "Speculative (Top 45%)",
    7: "Weak (Top 55%)",
    8: "Trash (Bottom 45%)",
}


@router.get("/nodes", response_model=list[TreeNode])
def get_nodes(
    spotId: str = Query(...),
    db: Session = Depends(get_db),
    _user: UserModel = Depends(get_current_user),
):
    return nodes_service.get_nodes_by_spot(db, spotId)


@router.get("/node", response_model=TreeNode)
def get_node(
    spotId: str = Query(...),
    nodeId: str = Query(...),
    db: Session = Depends(get_db),
    _user: UserModel = Depends(get_current_user),
):
    node = nodes_service.get_node_by_id(db, nodeId)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node not found: {nodeId}")
    return node


@router.get("/strategy")
def get_strategy(
    nodeId: str = Query(...),
    db: Session = Depends(get_db),
    _user: UserModel = Depends(get_current_user),
):
    node = nodes_service.get_node_by_id(db, nodeId)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node not found: {nodeId}")
    actions = [a.model_dump() for a in node.actions]
    return get_or_create_strategy(db, nodeId, actions)


@router.get("/hand-detail", response_model=HandDetail)
def get_hand_detail(
    nodeId: str = Query(...),
    hand: str = Query(...),
    db: Session = Depends(get_db),
    _user: UserModel = Depends(get_current_user),
):
    """Get detailed strategy breakdown for a specific hand in a node."""
    node = nodes_service.get_node_by_id(db, nodeId)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node not found: {nodeId}")

    actions = [a.model_dump() for a in node.actions]
    strategy = get_or_create_strategy(db, nodeId, actions)
    frequencies = strategy.get(hand, {})

    tier = get_hand_tier(hand)
    tier_label = TIER_LABELS.get(tier, f"Tier {tier}")

    # Use a sample board for connection analysis
    import random
    sample_board = random.choice(BOARD_TEXTURES)["board"]
    connection = hand_connects_with_board(hand, sample_board)

    # Find correct action
    correct_action = max(frequencies, key=frequencies.get) if frequencies else ""

    # Get spot format
    from app.models import SpotModel
    spot = db.query(SpotModel).filter(SpotModel.id == node.spotId).first()
    pot_type = spot.format if spot else "SRP"

    explanation = generate_explanation(
        hand=hand,
        board=sample_board,
        chosen_action=correct_action,
        correct_action=correct_action,
        frequencies=frequencies,
        position=node.player,
        line_description=node.lineDescription,
        pot_type=pot_type,
    )

    return HandDetail(
        hand=hand,
        tier=tier,
        tierLabel=tier_label,
        frequencies=frequencies,
        connection=connection,
        explanation=explanation,
    )
