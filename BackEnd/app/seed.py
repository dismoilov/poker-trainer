"""Seed database: admin user, spots, nodes, strategies only. No demo data."""

import json
import logging
import sys

from sqlalchemy.orm import Session

from app.core.config import SPOTPACK_PATH
from app.models import UserModel, SpotModel, NodeModel
from app.security import hash_password
from app.services.strategy import generate_strategy, save_strategy

logger = logging.getLogger(__name__)


def seed_database(db: Session) -> None:
    """Seed: admin user + spots + nodes + strategies. No demo data."""

    # 1) Default user
    existing_user = db.query(UserModel).first()
    if not existing_user:
        user = UserModel(
            username="admin",
            password_hash=hash_password("admin123"),
            is_active=True,
            is_admin=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("Created default user: admin / admin123")

    # 2) Spots + nodes
    existing_spot = db.query(SpotModel).first()
    if existing_spot:
        logger.info("Database already seeded, skipping.")
        return

    if not SPOTPACK_PATH.exists():
        logger.warning("spotpack.json not found at %s", SPOTPACK_PATH)
        return

    with open(SPOTPACK_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    for s in data.get("spots", []):
        db.add(SpotModel(
            id=s["id"], name=s["name"], format=s["format"],
            positions=s["positions"], stack=s["stack"],
            rake_profile=s.get("rakeProfile", "low"),
            streets=s["streets"], tags=s.get("tags", []),
            solved=s.get("solved", False),
            node_count=s.get("nodeCount", 0),
        ))

    for n in data.get("nodes", []):
        db.add(NodeModel(
            id=n["id"], spot_id=n["spotId"], street=n["street"],
            pot=n["pot"], player=n["player"], actions=n["actions"],
            parent_id=n.get("parentId"),
            line_description=n["lineDescription"],
            children=n.get("children", []),
            action_label=n.get("actionLabel"),
        ))

    db.commit()
    spot_count = len(data.get("spots", []))
    node_count = len(data.get("nodes", []))
    logger.info("Seeded %d spots and %d nodes.", spot_count, node_count)

    # 3) Pre-generate strategies for all nodes
    nodes = db.query(NodeModel).all()
    for node in nodes:
        strategy = generate_strategy(node.id, node.actions)
        save_strategy(db, node.id, strategy)
    logger.info("Generated strategies for %d nodes.", len(nodes))


def reset_and_seed():
    """CLI: drop all tables, recreate, and seed."""
    from app.db import Base, engine, SessionLocal
    logger.info("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    logger.info("Creating all tables...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
    logger.info("Reset and seed complete.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if "--reset" in sys.argv or "reset" in sys.argv:
        reset_and_seed()
    else:
        from app.db import create_tables, SessionLocal
        create_tables()
        db = SessionLocal()
        try:
            seed_database(db)
        finally:
            db.close()
