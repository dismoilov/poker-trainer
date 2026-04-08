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


class SolveResultModel(Base):
    """
    Persisted solver result — stores summaries and metadata,
    NOT the full per-combo strategy matrix (too large for SQLite).
    
    HONEST NOTE: This stores summary data only. Full per-combo strategies
    are only available in-memory during the solve session. After server
    restart, only summaries are available.
    """
    __tablename__ = "solve_results"

    id = Column(String, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())

    # Input config
    config_json = Column(JSON, nullable=False, default={})

    # Results
    iterations = Column(Integer, nullable=False, default=0)
    convergence_metric = Column(Float, nullable=False, default=0.0)
    elapsed_seconds = Column(Float, nullable=False, default=0.0)
    tree_nodes = Column(Integer, nullable=False, default=0)
    ip_combos = Column(Integer, nullable=False, default=0)
    oop_combos = Column(Integer, nullable=False, default=0)
    matchups = Column(Integer, nullable=False, default=0)
    converged = Column(Boolean, nullable=False, default=False)
    solved_node_count = Column(Integer, nullable=False, default=0)

    # Metadata & validation
    algorithm_metadata_json = Column(JSON, nullable=False, default={})
    validation_json = Column(JSON, nullable=False, default={})

    # Root strategy summary (action averages, not per-combo)
    root_strategy_summary_json = Column(JSON, nullable=False, default={})

    # Selected node summaries (action averages for key nodes, not full combos)
    node_summaries_json = Column(JSON, nullable=False, default={})

    # Whether full per-combo data was available at persist time
    full_strategies_available = Column(Boolean, nullable=False, default=False)

    # Phase 4A: Exploitability and trust grading
    exploitability_mbb = Column(Float, nullable=True)
    exploitability_exact = Column(Boolean, nullable=True)
    trust_grade = Column(String, nullable=True)
    trust_grade_json = Column(JSON, nullable=True)
    benchmark_summary_json = Column(JSON, nullable=True)
    exploitability_json = Column(JSON, nullable=True)

    # Phase 4B: Combo-level strategy persistence (constrained subset)
    combo_strategies_json = Column(JSON, nullable=True)
    combo_storage_note = Column(Text, nullable=True)

    # Phase 6A: Street depth metadata
    street_depth = Column(String, nullable=True, default="flop_only")
    turn_cards_explored = Column(Integer, nullable=True, default=0)

    # Phase 7A: Solver correctness metadata
    correctness_json = Column(JSON, nullable=True)
    correctness_notes = Column(Text, nullable=True)

    error = Column(Text, nullable=True)

