"""Seed integrity tests: verify data is complete and consistent."""

from app.models import UserModel, SpotModel, NodeModel, StrategyModel
import json


def test_users_exist(db):
    count = db.query(UserModel).count()
    assert count >= 1


def test_spots_count(db):
    count = db.query(SpotModel).count()
    assert count == 43


def test_nodes_have_valid_spot(db):
    nodes = db.query(NodeModel).all()
    assert len(nodes) >= 100  # 20 spots x ~5-6 nodes
    spot_ids = {s.id for s in db.query(SpotModel).all()}
    for node in nodes:
        assert node.spot_id in spot_ids, f"Node {node.id} has invalid spot_id: {node.spot_id}"


def test_strategies_exist_for_all_nodes(db):
    nodes = db.query(NodeModel).all()
    strategies = db.query(StrategyModel).all()
    strat_ids = {s.node_id for s in strategies}
    for node in nodes:
        assert node.id in strat_ids, f"No strategy for node {node.id}"


def test_strategy_has_169_hands(db):
    strategies = db.query(StrategyModel).all()
    assert len(strategies) > 0
    for s in strategies:
        matrix = json.loads(s.matrix_json)
        assert len(matrix) == 169, f"Strategy {s.node_id} has {len(matrix)} hands, expected 169"


def test_strategy_frequencies_sum_to_one(db):
    strategies = db.query(StrategyModel).limit(5).all()
    for s in strategies:
        matrix = json.loads(s.matrix_json)
        for hand, freqs in matrix.items():
            total = sum(freqs.values())
            assert abs(total - 1.0) < 0.01, f"Strategy {s.node_id} hand {hand}: sum={total}"
            for action_id, f in freqs.items():
                assert 0 <= f <= 1, f"Freq out of range: {s.node_id}/{hand}/{action_id}={f}"
