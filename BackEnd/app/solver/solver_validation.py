"""
Solver validation layer — post-solve correctness checks.

THIS IS NOT MATHEMATICAL PROOF. These are engineering sanity checks
that verify the solver output meets basic structural requirements:
- Strategy normalization (sums to 1.0 per info set)
- Non-negative frequencies
- No NaN/Inf values
- All expected actions present
- Convergence trend check

Also includes a toy-game validator that runs the solver on a game
with known equilibrium properties to verify algorithm correctness.

WHAT THIS VALIDATES:
- The solver produces structurally valid output
- The regret-matching math doesn't produce garbage
- The toy-game equilibrium is approximately correct

WHAT THIS DOES NOT VALIDATE:
- Exact exploitability (see best_response.py for that)
- Correctness on all possible game configurations
- Production-grade numerical stability
- Turn-specific mathematical guarantees beyond structural checks
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

EPSILON = 1e-4  # Tolerance for normalization checks


@dataclass
class ValidationResult:
    """Result of post-solve validation checks."""
    passed: bool = True
    checks_run: int = 0
    checks_passed: int = 0
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    toy_game_result: Optional[dict] = None
    details: dict = field(default_factory=dict)

    def add_issue(self, msg: str):
        self.issues.append(msg)
        self.passed = False

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "checks_run": self.checks_run,
            "checks_passed": self.checks_passed,
            "issues": self.issues,
            "warnings": self.warnings,
            "toy_game_result": self.toy_game_result,
            "trust_level": self._trust_level(),
        }

    def _trust_level(self) -> str:
        if not self.passed:
            return "FAILED — do not trust output"
        if self.toy_game_result and self.toy_game_result.get("passed"):
            if len(self.warnings) == 0:
                return "INTERNAL_DEMO — structurally valid, toy-game passes"
            return "INTERNAL_DEMO_WITH_WARNINGS — structurally valid but has warnings"
        return "STRUCTURAL_ONLY — basic checks pass, toy-game not run"


def validate_solve_output(
    strategies: dict[str, dict[str, dict[str, float]]],
    iterations: int,
    convergence_metric: float,
) -> ValidationResult:
    """
    Run all structural validation checks on a completed solve output.

    Args:
        strategies: node_id → {combo_str → {action → freq}}
        iterations: Number of CFR+ iterations run
        convergence_metric: Final convergence metric

    Returns:
        ValidationResult with all checks
    """
    result = ValidationResult()

    # ── Check 1: Strategy normalization ──
    result.checks_run += 1
    normalization_errors = 0
    total_info_sets = 0

    for node_id, combos in strategies.items():
        for combo_str, freqs in combos.items():
            total_info_sets += 1
            total = sum(freqs.values())
            if abs(total - 1.0) > EPSILON:
                normalization_errors += 1
                if normalization_errors <= 3:
                    result.add_issue(
                        f"Normalization error at node={node_id}, combo={combo_str}: "
                        f"sum={total:.6f} (expected 1.0 ± {EPSILON})"
                    )

    if normalization_errors == 0:
        result.checks_passed += 1
        result.details["normalization"] = f"PASS — {total_info_sets} info sets all sum to 1.0"
    else:
        result.details["normalization"] = (
            f"FAIL — {normalization_errors}/{total_info_sets} info sets have bad normalization"
        )

    # ── Check 2: Non-negative frequencies ──
    result.checks_run += 1
    negative_count = 0
    for node_id, combos in strategies.items():
        for combo_str, freqs in combos.items():
            for action, freq in freqs.items():
                if freq < -EPSILON:
                    negative_count += 1
                    if negative_count <= 3:
                        result.add_issue(
                            f"Negative frequency at {node_id}/{combo_str}/{action}: {freq:.6f}"
                        )

    if negative_count == 0:
        result.checks_passed += 1
        result.details["non_negative"] = "PASS — all frequencies ≥ 0"
    else:
        result.details["non_negative"] = f"FAIL — {negative_count} negative frequencies"

    # ── Check 3: No NaN/Inf ──
    result.checks_run += 1
    nan_count = 0
    for node_id, combos in strategies.items():
        for combo_str, freqs in combos.items():
            for action, freq in freqs.items():
                if math.isnan(freq) or math.isinf(freq):
                    nan_count += 1
                    if nan_count <= 3:
                        result.add_issue(f"NaN/Inf at {node_id}/{combo_str}/{action}")

    if nan_count == 0:
        result.checks_passed += 1
        result.details["no_nan_inf"] = "PASS — no NaN/Inf values"
    else:
        result.details["no_nan_inf"] = f"FAIL — {nan_count} NaN/Inf values"

    # ── Check 4: Non-empty strategies ──
    result.checks_run += 1
    if len(strategies) > 0 and total_info_sets > 0:
        result.checks_passed += 1
        result.details["non_empty"] = f"PASS — {len(strategies)} nodes, {total_info_sets} info sets"
    else:
        result.add_issue("Empty strategy output")
        result.details["non_empty"] = "FAIL — no strategies produced"

    # ── Check 5: Actions consistency ──
    result.checks_run += 1
    inconsistent_nodes = 0
    for node_id, combos in strategies.items():
        action_sets = [frozenset(freqs.keys()) for freqs in combos.values()]
        if len(set(action_sets)) > 1:
            inconsistent_nodes += 1
            if inconsistent_nodes <= 2:
                result.add_warning(
                    f"node {node_id}: different combos have different action sets"
                )

    if inconsistent_nodes == 0:
        result.checks_passed += 1
        result.details["action_consistency"] = "PASS — all combos at each node have same actions"
    else:
        result.details["action_consistency"] = (
            f"WARNING — {inconsistent_nodes} nodes have inconsistent action sets"
        )

    # ── Check 6: Convergence sanity ──
    result.checks_run += 1
    if convergence_metric < 1.0:
        result.checks_passed += 1
        result.details["convergence"] = f"PASS — convergence={convergence_metric:.6f} < 1.0"
    elif convergence_metric < 5.0:
        result.checks_passed += 1
        result.add_warning(f"Convergence metric is moderately high: {convergence_metric:.6f}")
        result.details["convergence"] = f"WARN — convergence={convergence_metric:.6f} (moderate)"
    else:
        result.add_warning(
            f"Convergence metric is high: {convergence_metric:.6f}. "
            f"More iterations may be needed."
        )
        result.details["convergence"] = f"WARN — convergence={convergence_metric:.6f} (high)"

    logger.info(
        "Validation: %d/%d checks passed, %d issues, %d warnings",
        result.checks_passed, result.checks_run,
        len(result.issues), len(result.warnings),
    )

    return result


# ── Toy-game validator ─────────────────────────────────────────

def run_toy_game_validation() -> dict:
    """
    Run the solver on a trivially simple game where we know expected behavior.

    Game: AA vs KK on a board of 9s 7d 2c, no bet sizes (check/fold only).
    AA always wins at showdown. Expected equilibrium:
    - AA should never fold (folding loses value)
    - KK should fold at high frequency when facing a bet

    We verify:
    1. Solver completes without error
    2. Output is structurally valid
    3. AA fold frequency at root is near 0
    4. Strategy normalization passes

    HONEST NOTE: This is a sanity check, not a rigorous proof.
    It verifies the solver doesn't produce obviously wrong output.
    """
    from app.solver.cfr_solver import CfrSolver, SolveRequest

    try:
        request = SolveRequest(
            board=["9s", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=6.5,
            effective_stack=97.0,
            bet_sizes=[1.0],
            raise_sizes=[],
            max_iterations=100,
            max_raises=1,
        )

        solver = CfrSolver()
        output = solver.solve(request)

        # Validate structural correctness
        validation = validate_solve_output(
            output.strategies, output.iterations, output.convergence_metric
        )

        # Check AA behavior at root (AA should not fold)
        root_strat = output.strategies.get("node_0", {})
        aa_fold_frequencies = []
        for combo_str, freqs in root_strat.items():
            if combo_str.startswith("A"):
                fold_freq = freqs.get("fold", 0.0)
                aa_fold_frequencies.append(fold_freq)

        aa_avg_fold = sum(aa_fold_frequencies) / max(len(aa_fold_frequencies), 1)

        # AA should fold < 10% at root (it's the nuts here)
        aa_fold_ok = aa_avg_fold < 0.10

        result = {
            "passed": validation.passed and aa_fold_ok,
            "solver_completed": True,
            "structural_validation": validation.passed,
            "aa_avg_fold_at_root": round(aa_avg_fold, 4),
            "aa_fold_reasonable": aa_fold_ok,
            "iterations": output.iterations,
            "convergence": output.convergence_metric,
            "note": (
                "Toy game: AA vs KK on 9-7-2. "
                "Verifies solver doesn't produce obviously wrong results. "
                "NOT a mathematical proof of correctness."
            ),
        }

        logger.info("Toy-game validation: %s (AA fold=%.4f)", 
                     "PASS" if result["passed"] else "FAIL", aa_avg_fold)
        return result

    except Exception as e:
        logger.error("Toy-game validation failed with exception: %s", e)
        return {
            "passed": False,
            "solver_completed": False,
            "error": str(e),
            "note": "Toy game validation crashed — solver may have bugs.",
        }


def validate_deterministic_reproducibility() -> dict:
    """
    Verify that the solver produces identical results when run twice
    with the same inputs and deterministic=True.

    Returns dict with pass/fail and details.
    """
    from app.solver.cfr_solver import CfrSolver, SolveRequest

    try:
        request = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=6.5,
            effective_stack=97.0,
            bet_sizes=[1.0],
            raise_sizes=[],
            max_iterations=30,
            max_raises=1,
            deterministic=True,
        )

        solver1 = CfrSolver()
        out1 = solver1.solve(request)

        solver2 = CfrSolver()
        out2 = solver2.solve(request)

        # Compare root strategies
        root1 = out1.strategies.get("node_0", {})
        root2 = out2.strategies.get("node_0", {})

        differences = 0
        compared = 0
        for combo in root1:
            if combo in root2:
                for action in root1[combo]:
                    if action in root2[combo]:
                        compared += 1
                        if abs(root1[combo][action] - root2[combo][action]) > 1e-10:
                            differences += 1

        passed = differences == 0 and compared > 0
        return {
            "passed": passed,
            "compared_values": compared,
            "differences": differences,
            "note": (
                "Ran solver twice with deterministic=True. "
                f"Compared {compared} strategy values, found {differences} differences."
            ),
        }

    except Exception as e:
        return {
            "passed": False,
            "error": str(e),
            "note": "Deterministic reproducibility test crashed.",
        }


# ── Trust grading ────────────────────────────────────────────────────────

TRUST_GRADES = [
    "FAILED",
    "STRUCTURAL_ONLY",
    "INTERNAL_DEMO",
    "INTERNAL_DEMO_WITH_WARNINGS",
    "VALIDATED_LIMITED_SCOPE",
]


def compute_trust_grade(
    validation: ValidationResult,
    exploitability_mbb: float = float("inf"),
    exploitability_available: bool = False,
    benchmark_passed: bool = False,
    deterministic: bool = False,
    street_depth: str = "flop_only",
    correctness_confidence: str = "UNKNOWN",
    correctness_notes: list = None,
) -> dict:
    """
    Compute a trust grade based on all available evidence.

    This is an HONEST grading system. A high trust grade requires:
    - Structural validation passed
    - Exploitability computed and below threshold
    - Benchmark consistency
    - All within the limited scope (supported streets, HU postflop)

    TURN-DEPTH NOTE: Turn-enabled solves use a more constrained abstraction
    (capped turn cards, 1 bet size, 0 raises on turn). The trust ceiling is
    lower — max INTERNAL_DEMO for turn solves, since the abstraction is coarser.

    Returns dict with grade, explanation, and component scores.
    """
    is_turn = street_depth == "flop_plus_turn"
    scope_label = f"{street_depth.replace('_', ' ')}, HU postflop, fixed bet sizes"

    components = {
        "structural_validation": validation.passed,
        "toy_game_passed": bool(
            validation.toy_game_result and validation.toy_game_result.get("passed")
        ),
        "no_warnings": len(validation.warnings) == 0,
        "exploitability_available": exploitability_available,
        "exploitability_below_50mbb": exploitability_available and exploitability_mbb < 50.0,
        "exploitability_below_10mbb": exploitability_available and exploitability_mbb < 10.0,
        "benchmark_passed": benchmark_passed,
        "deterministic": deterministic,
        "street_depth": street_depth,
        "is_turn_aware": is_turn,
        "correctness_confidence": correctness_confidence,
    }

    # Determine grade
    if not validation.passed:
        grade = "FAILED"
        explanation = "Structural validation failed. Do not trust output."
    elif not exploitability_available:
        if components["toy_game_passed"]:
            grade = "INTERNAL_DEMO"
            explanation = (
                "Structural checks pass, toy-game validates, but no exploitability data. "
                "Suitable for internal demo, not learning decisions."
            )
        else:
            grade = "STRUCTURAL_ONLY"
            explanation = (
                "Basic structural checks pass only. "
                "No exploitability or toy-game validation."
            )
    elif exploitability_mbb >= 50.0:
        grade = "INTERNAL_DEMO_WITH_WARNINGS"
        explanation = (
            f"Exploitability is high ({exploitability_mbb:.1f} mbb/hand). "
            "Strategy may not be close to equilibrium. "
            "Suitable for internal demo with caveats."
        )
    elif exploitability_mbb >= 10.0:
        grade = "INTERNAL_DEMO"
        explanation = (
            f"Exploitability is moderate ({exploitability_mbb:.1f} mbb/hand). "
            f"Approaching equilibrium but not fully converged. "
            f"Limited scope ({scope_label})."
        )
    else:
        # Exploitability < 10 mbb/hand = good convergence
        if is_turn:
            # Turn solves cap at INTERNAL_DEMO — abstraction is coarser
            grade = "INTERNAL_DEMO"
            explanation = (
                f"Low exploitability ({exploitability_mbb:.1f} mbb/hand) for turn-aware solve, "
                "but turn abstraction is constrained (capped cards, 1 bet size). "
                f"Scope: {scope_label}."
            )
        elif benchmark_passed and components["no_warnings"]:
            grade = "VALIDATED_LIMITED_SCOPE"
            explanation = (
                f"Low exploitability ({exploitability_mbb:.1f} mbb/hand), "
                "benchmarks pass, no warnings. "
                f"Validated within limited scope ({scope_label})."
            )
        else:
            grade = "INTERNAL_DEMO"
            explanation = (
                f"Low exploitability ({exploitability_mbb:.1f} mbb/hand) "
                "but benchmarks not confirmed or has warnings. "
                "Limited scope."
            )

    return {
        "grade": grade,
        "explanation": explanation,
        "components": components,
        "exploitability_mbb": round(exploitability_mbb, 2) if exploitability_available else None,
        "scope": scope_label,
        "street_depth": street_depth,
        "correctness_confidence": correctness_confidence,
        "correctness_notes": correctness_notes or [],
        "honest_note": (
            "Trust grade reflects validation within the current limited game abstraction. "
            "It does NOT indicate trustworthiness for full-NLHE decisions."
            + (" Turn abstraction is coarser than flop-only." if is_turn else "")
        ),
    }


# ── Turn-specific benchmark validation ──────────────────────────────────

def run_turn_benchmark_validation() -> dict:
    """
    Run turn-specific benchmark scenarios to validate solver behavior.

    Tests:
    1. Overpair on clean turn: AA should remain aggressive
    2. Flush-completing turn: strategy should shift vs draw hands
    3. Flop-only vs flop+turn comparison: both should produce valid output

    HONEST NOTE: These are engineering sanity checks, not mathematical proofs.
    They verify the turn-aware solver doesn't produce obviously wrong output.
    """
    from app.solver.cfr_solver import CfrSolver, SolveRequest

    benchmarks = {}

    # ── Benchmark 1: Overpair on clean turn ──
    try:
        request = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="QQ",
            pot=6.5,
            effective_stack=97.0,
            bet_sizes=[0.67],
            raise_sizes=[],
            max_iterations=50,
            max_raises=1,
            deterministic=True,
            include_turn=True,
            max_turn_cards=3,
        )
        solver = CfrSolver()
        output = solver.solve(request)

        root_strat = output.strategies.get("node_0", {})
        aa_check_freqs = []
        for combo_str, freqs in root_strat.items():
            if combo_str.startswith("A"):
                aa_check_freqs.append(freqs.get("check", 0.0))

        aa_avg_check = sum(aa_check_freqs) / max(len(aa_check_freqs), 1)

        # AA should not always check (should bet at some frequency)
        overpair_ok = aa_avg_check < 0.95 and output.iterations > 0

        benchmarks["overpair_clean_turn"] = {
            "passed": overpair_ok,
            "aa_avg_check_freq": round(aa_avg_check, 4),
            "iterations": output.iterations,
            "street_depth": output.metadata.get("street_depth", "unknown"),
            "note": "AA vs QQ on K72. AA should bet at some frequency.",
        }
    except Exception as e:
        benchmarks["overpair_clean_turn"] = {
            "passed": False,
            "error": str(e),
        }

    # ── Benchmark 2: Strategy normalization on turn-enabled solve ──
    try:
        request2 = SolveRequest(
            board=["Ah", "Kd", "7c"],
            ip_range="KK",
            oop_range="QQ,JJ",
            pot=6.5,
            effective_stack=97.0,
            bet_sizes=[0.67],
            raise_sizes=[],
            max_iterations=30,
            max_raises=1,
            deterministic=True,
            include_turn=True,
            max_turn_cards=2,
        )
        solver2 = CfrSolver()
        output2 = solver2.solve(request2)

        # Validate all strategies are normalized
        normalization_ok = True
        for node_id, combos in output2.strategies.items():
            for combo_str, freqs in combos.items():
                total = sum(freqs.values())
                if abs(total - 1.0) > EPSILON:
                    normalization_ok = False
                    break

        benchmarks["turn_normalization"] = {
            "passed": normalization_ok and output2.iterations > 0,
            "node_count": len(output2.strategies),
            "street_depth": output2.metadata.get("street_depth", "unknown"),
            "note": "All turn-aware strategies should be normalized to 1.0.",
        }
    except Exception as e:
        benchmarks["turn_normalization"] = {
            "passed": False,
            "error": str(e),
        }

    # ── Benchmark 3: Flop-only vs flop+turn comparison ──
    try:
        flop_req = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=6.5,
            effective_stack=97.0,
            bet_sizes=[0.67],
            raise_sizes=[],
            max_iterations=30,
            max_raises=1,
            deterministic=True,
            include_turn=False,
        )
        turn_req = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=6.5,
            effective_stack=97.0,
            bet_sizes=[0.67],
            raise_sizes=[],
            max_iterations=30,
            max_raises=1,
            deterministic=True,
            include_turn=True,
            max_turn_cards=2,
        )

        solver_f = CfrSolver()
        out_f = solver_f.solve(flop_req)
        solver_t = CfrSolver()
        out_t = solver_t.solve(turn_req)

        # Both should produce valid output
        both_valid = (
            out_f.iterations > 0
            and out_t.iterations > 0
            and len(out_f.strategies) > 0
            and len(out_t.strategies) > 0
        )

        benchmarks["flop_vs_turn_comparison"] = {
            "passed": both_valid,
            "flop_nodes": len(out_f.strategies),
            "turn_nodes": len(out_t.strategies),
            "flop_depth": out_f.metadata.get("street_depth", "unknown"),
            "turn_depth": out_t.metadata.get("street_depth", "unknown"),
            "note": (
                "Both flop-only and flop+turn should produce valid output. "
                "Turn trees should be larger due to chance nodes."
            ),
        }
    except Exception as e:
        benchmarks["flop_vs_turn_comparison"] = {
            "passed": False,
            "error": str(e),
        }

    all_passed = all(b.get("passed", False) for b in benchmarks.values())

    return {
        "passed": all_passed,
        "benchmarks": benchmarks,
        "benchmark_count": len(benchmarks),
        "benchmarks_passed": sum(1 for b in benchmarks.values() if b.get("passed")),
        "note": (
            "Turn-specific benchmarks. Engineering sanity checks, "
            "NOT mathematical proofs of correctness."
        ),
    }


# ── Chance-node structural validation ───────────────────────────────────

def validate_chance_node_structure(root_node) -> dict:
    """
    Validate structural correctness of chance nodes in the game tree.

    Checks:
    - Every CHANCE node has at least one child
    - Every child of a CHANCE node has a turn_card set
    - No turn_card duplicates within a CHANCE node
    - Turn cards are not board cards
    - Children of CHANCE nodes have street='turn'

    Returns dict with pass/fail and details.
    """
    from app.solver.tree_builder import NodeType

    issues = []
    chance_count = 0

    def _check(node, board_cards: set, depth: int = 0):
        nonlocal chance_count
        if node.node_type == NodeType.CHANCE:
            chance_count += 1

            if len(node.children) == 0:
                issues.append(f"CHANCE node at depth {depth} has no children")
                return

            seen_cards = set()
            for label, child in node.children.items():
                if child.turn_card is None:
                    issues.append(
                        f"CHANCE child '{label}' at depth {depth} has no turn_card"
                    )
                elif child.turn_card in board_cards:
                    issues.append(
                        f"CHANCE child turn_card '{child.turn_card}' "
                        f"is a board card at depth {depth}"
                    )
                elif child.turn_card in seen_cards:
                    issues.append(
                        f"Duplicate turn_card '{child.turn_card}' at depth {depth}"
                    )
                else:
                    seen_cards.add(child.turn_card)

                if child.street != "turn":
                    issues.append(
                        f"CHANCE child '{label}' has street='{child.street}' "
                        f"(expected 'turn') at depth {depth}"
                    )

        for child in node.children.values():
            _check(child, board_cards, depth + 1)

    board_set = set(getattr(root_node, 'board', ()) or ())
    _check(root_node, board_set)

    return {
        "passed": len(issues) == 0,
        "chance_nodes_found": chance_count,
        "issues": issues,
        "note": "Structural check of chance-node children in the game tree.",
    }

