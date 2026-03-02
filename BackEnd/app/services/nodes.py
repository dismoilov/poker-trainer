"""Nodes service — CRUD for tree nodes."""

from sqlalchemy.orm import Session
from app.models import NodeModel
from app.schemas import TreeNode, Action


def _to_schema(m: NodeModel) -> TreeNode:
    actions = [Action(**a) for a in m.actions]
    return TreeNode(
        id=m.id,
        spotId=m.spot_id,
        street=m.street,
        pot=m.pot,
        player=m.player,
        actions=actions,
        parentId=m.parent_id,
        lineDescription=m.line_description,
        children=m.children,
        actionLabel=m.action_label,
    )


def get_nodes_by_spot(db: Session, spot_id: str) -> list[TreeNode]:
    rows = db.query(NodeModel).filter(NodeModel.spot_id == spot_id).all()
    return [_to_schema(r) for r in rows]


def get_node_by_id(db: Session, node_id: str) -> TreeNode | None:
    row = db.query(NodeModel).filter(NodeModel.id == node_id).first()
    return _to_schema(row) if row else None


def get_root_node(db: Session, spot_id: str) -> TreeNode | None:
    row = (
        db.query(NodeModel)
        .filter(NodeModel.spot_id == spot_id, NodeModel.parent_id.is_(None))
        .first()
    )
    return _to_schema(row) if row else None
