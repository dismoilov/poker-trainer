"""Spots service — CRUD for spots, including custom spot creation."""

import uuid
from sqlalchemy.orm import Session
from app.models import SpotModel, NodeModel, StrategyModel
from app.schemas import Spot, SpotCreateRequest


# Standard pot sizes by format
POT_SIZES = {
    "SRP":     {"flop": 6.5, "turn": 12.0, "river": 24.0},
    "3bet":    {"flop": 13.5, "turn": 24.0, "river": 40.0},
    "4bet":    {"flop": 25.0, "turn": 45.0, "river": 80.0},
    "squeeze": {"flop": 20.0, "turn": 36.0, "river": 60.0},
}

# Action templates
CHECK_BET = [
    {"id": "check", "label": "Check", "type": "check"},
    {"id": "bet33", "label": "Bet 33%", "type": "bet", "size": 33},
    {"id": "bet75", "label": "Bet 75%", "type": "bet", "size": 75},
]

CHECK_BET_TURN = [
    {"id": "check", "label": "Check", "type": "check"},
    {"id": "bet50", "label": "Bet 50%", "type": "bet", "size": 50},
    {"id": "bet75", "label": "Bet 75%", "type": "bet", "size": 75},
]

CHECK_BET_RIVER = [
    {"id": "check", "label": "Check", "type": "check"},
    {"id": "bet75", "label": "Bet 75%", "type": "bet", "size": 75},
    {"id": "bet150", "label": "Bet 150%", "type": "bet", "size": 150},
]

FOLD_CALL_RAISE = [
    {"id": "fold", "label": "Fold", "type": "fold"},
    {"id": "call", "label": "Call", "type": "call"},
    {"id": "raise", "label": "Raise 2.5x", "type": "raise", "size": 2.5},
]

VALID_FORMATS = {"SRP", "3bet", "4bet", "squeeze"}
VALID_POSITIONS = {"UTG", "HJ", "MP", "CO", "BTN", "SB", "BB"}
VALID_STREETS = {"flop", "turn", "river"}


def _to_schema(m: SpotModel) -> Spot:
    return Spot(
        id=m.id,
        name=m.name,
        format=m.format,
        positions=m.positions,
        stack=m.stack,
        rakeProfile=m.rake_profile,
        streets=m.streets,
        tags=m.tags,
        solved=m.solved,
        nodeCount=m.node_count,
        isCustom=m.is_custom,
    )


def get_all_spots(db: Session) -> list[Spot]:
    rows = db.query(SpotModel).all()
    return [_to_schema(r) for r in rows]


def get_spot_by_id(db: Session, spot_id: str) -> Spot | None:
    row = db.query(SpotModel).filter(SpotModel.id == spot_id).first()
    return _to_schema(row) if row else None


def _make_node(spot_id, node_num, street, pot, player, actions, parent_id, line_desc, children, action_label):
    nid = f"{spot_id}__{'root' if parent_id is None else f'node-{node_num}'}"
    return NodeModel(
        id=nid,
        spot_id=spot_id,
        street=street,
        pot=pot,
        player=player,
        actions=actions,
        parent_id=parent_id,
        line_description=line_desc,
        children=children,
        action_label=action_label,
    )


def _generate_flop_nodes(spot_id: str, pos_ip: str, pos_oop: str, pot: float, fmt: str) -> list[NodeModel]:
    """Generate a standard 6-node flop tree."""
    root_id = f"{spot_id}__root"
    n2 = f"{spot_id}__node-2"
    n3 = f"{spot_id}__node-3"
    n4 = f"{spot_id}__node-4"
    n5 = f"{spot_id}__node-5"
    n6 = f"{spot_id}__node-6"

    bet33_pot = round(pot + pot * 0.33, 1)
    bet75_pot = round(pot + pot * 0.75, 1)

    if fmt == "squeeze":
        line = f"{pos_ip} open → cold call → {pos_oop} squeeze → {pos_ip} call"
    elif fmt == "3bet":
        line = f"{pos_ip} open → {pos_oop} 3bet → {pos_ip} call"
    elif fmt == "4bet":
        line = f"{pos_ip} open → {pos_oop} 3bet → {pos_ip} 4bet → {pos_oop} call"
    else:
        line = f"{pos_ip} open 2.5bb → {pos_oop} call"

    nodes = [
        _make_node(spot_id, 0, "flop", pot, pos_oop, CHECK_BET, None, line, [n2, n5, n6], "Root"),
        _make_node(spot_id, 2, "flop", pot, pos_ip, CHECK_BET, root_id,
                   f"{pos_oop} check", [n3, n4], f"{pos_oop} Check"),
        _make_node(spot_id, 3, "flop", bet33_pot, pos_oop, FOLD_CALL_RAISE, n2,
                   f"{pos_oop} check → {pos_ip} bet 33%", [], f"{pos_ip} Bet 33%"),
        _make_node(spot_id, 4, "flop", bet75_pot, pos_oop, FOLD_CALL_RAISE, n2,
                   f"{pos_oop} check → {pos_ip} bet 75%", [], f"{pos_ip} Bet 75%"),
        _make_node(spot_id, 5, "flop", bet33_pot, pos_ip, FOLD_CALL_RAISE, root_id,
                   f"{pos_oop} bet 33%", [], f"{pos_oop} Bet 33%"),
        _make_node(spot_id, 6, "flop", bet75_pot, pos_ip, FOLD_CALL_RAISE, root_id,
                   f"{pos_oop} bet 75%", [], f"{pos_oop} Bet 75%"),
    ]
    return nodes


def _generate_turn_nodes(spot_id: str, pos_ip: str, pos_oop: str, pot: float) -> list[NodeModel]:
    """Generate a standard 6-node turn tree."""
    root_id = f"{spot_id}__root"
    n2 = f"{spot_id}__node-2"
    n3 = f"{spot_id}__node-3"
    n4 = f"{spot_id}__node-4"
    n5 = f"{spot_id}__node-5"
    n6 = f"{spot_id}__node-6"

    bet50_pot = round(pot + pot * 0.50, 1)
    bet75_pot = round(pot + pot * 0.75, 1)

    nodes = [
        _make_node(spot_id, 0, "turn", pot, pos_oop, CHECK_BET_TURN, None,
                   f"Turn play — {pos_ip} vs {pos_oop}", [n2, n5, n6], "Root"),
        _make_node(spot_id, 2, "turn", pot, pos_ip, CHECK_BET_TURN, root_id,
                   f"Turn → {pos_oop} check", [n3, n4], f"{pos_oop} Check"),
        _make_node(spot_id, 3, "turn", bet50_pot, pos_oop, FOLD_CALL_RAISE, n2,
                   f"{pos_oop} check → {pos_ip} bet 50%", [], f"{pos_ip} Bet 50%"),
        _make_node(spot_id, 4, "turn", bet75_pot, pos_oop, FOLD_CALL_RAISE, n2,
                   f"{pos_oop} check → {pos_ip} bet 75%", [], f"{pos_ip} Bet 75%"),
        _make_node(spot_id, 5, "turn", bet50_pot, pos_ip, FOLD_CALL_RAISE, root_id,
                   f"{pos_oop} bet 50%", [], f"{pos_oop} Bet 50%"),
        _make_node(spot_id, 6, "turn", bet75_pot, pos_ip, FOLD_CALL_RAISE, root_id,
                   f"{pos_oop} bet 75%", [], f"{pos_oop} Bet 75%"),
    ]
    return nodes


def _generate_river_nodes(spot_id: str, pos_ip: str, pos_oop: str, pot: float) -> list[NodeModel]:
    """Generate a standard 5-node river tree."""
    root_id = f"{spot_id}__root"
    n2 = f"{spot_id}__node-2"
    n3 = f"{spot_id}__node-3"
    n4 = f"{spot_id}__node-4"
    n5 = f"{spot_id}__node-5"

    bet75_pot = round(pot + pot * 0.75, 1)
    bet150_pot = round(pot + pot * 1.50, 1)

    nodes = [
        _make_node(spot_id, 0, "river", pot, pos_oop, CHECK_BET_RIVER, None,
                   f"River play — {pos_ip} vs {pos_oop}", [n2, n3, n4], "Root"),
        _make_node(spot_id, 2, "river", pot, pos_ip, CHECK_BET_RIVER, root_id,
                   f"River → {pos_oop} check", [n5], f"{pos_oop} Check"),
        _make_node(spot_id, 3, "river", bet75_pot, pos_ip, FOLD_CALL_RAISE, root_id,
                   f"{pos_oop} bet 75%", [], f"{pos_oop} Bet 75%"),
        _make_node(spot_id, 4, "river", bet150_pot, pos_ip, FOLD_CALL_RAISE, root_id,
                   f"{pos_oop} bet 150% (overbet)", [], f"{pos_oop} Bet 150%"),
        _make_node(spot_id, 5, "river", bet75_pot, pos_oop, FOLD_CALL_RAISE, n2,
                   f"{pos_oop} check → {pos_ip} bet 75%", [], f"{pos_ip} Bet 75%"),
    ]
    return nodes


def create_custom_spot(db: Session, req: SpotCreateRequest) -> Spot:
    """Create a custom spot with auto-generated nodes (unsolved)."""
    fmt = req.format
    if fmt not in VALID_FORMATS:
        raise ValueError(f"Invalid format: {fmt}. Must be one of {VALID_FORMATS}")
    if len(req.positions) != 2:
        raise ValueError("Exactly 2 positions required: [IP, OOP]")
    for pos in req.positions:
        if pos not in VALID_POSITIONS:
            raise ValueError(f"Invalid position: {pos}. Must be one of {VALID_POSITIONS}")
    if req.street not in VALID_STREETS:
        raise ValueError(f"Invalid street: {req.street}. Must be one of {VALID_STREETS}")

    pos_ip, pos_oop = req.positions
    street = req.street
    uid = uuid.uuid4().hex[:8]
    spot_id = f"custom-{fmt}-{pos_ip.lower()}-{pos_oop.lower()}-{street}-{uid}"

    # Build name
    fmt_label = {"SRP": "SRP", "3bet": "3Bet", "4bet": "4Bet", "squeeze": "Squeeze"}[fmt]
    name = f"{fmt_label} {pos_ip} vs {pos_oop} {street.capitalize()} (custom)"

    # Determine pot and streets list
    pot = POT_SIZES.get(fmt, POT_SIZES["SRP"]).get(street, 6.5)

    if street == "flop":
        streets_list = ["flop"]
    elif street == "turn":
        streets_list = ["flop", "turn"]
    else:
        streets_list = ["flop", "turn", "river"]

    # Generate nodes
    if street == "flop":
        nodes = _generate_flop_nodes(spot_id, pos_ip, pos_oop, pot, fmt)
    elif street == "turn":
        nodes = _generate_turn_nodes(spot_id, pos_ip, pos_oop, pot)
    else:
        nodes = _generate_river_nodes(spot_id, pos_ip, pos_oop, pot)

    # Create spot
    spot = SpotModel(
        id=spot_id,
        name=name,
        format=fmt,
        positions=[pos_ip, pos_oop],
        stack=req.stack,
        rake_profile="low",
        streets=streets_list,
        tags=[fmt, street, "custom"],
        solved=False,
        node_count=len(nodes),
        is_custom=True,
    )
    db.add(spot)
    for node in nodes:
        db.add(node)
    db.commit()
    db.refresh(spot)

    return _to_schema(spot)


def delete_spot(db: Session, spot_id: str) -> bool:
    """Delete a custom spot and its associated nodes and strategies."""
    spot = db.query(SpotModel).filter(SpotModel.id == spot_id).first()
    if not spot:
        raise ValueError(f"Spot not found: {spot_id}")
    if not spot.is_custom:
        raise ValueError("Cannot delete built-in spots")

    # Delete strategies for this spot's nodes
    node_ids = [n.id for n in db.query(NodeModel.id).filter(NodeModel.spot_id == spot_id).all()]
    if node_ids:
        db.query(StrategyModel).filter(StrategyModel.node_id.in_(node_ids)).delete(synchronize_session=False)

    # Delete nodes
    db.query(NodeModel).filter(NodeModel.spot_id == spot_id).delete(synchronize_session=False)

    # Delete spot
    db.delete(spot)
    db.commit()
    return True
