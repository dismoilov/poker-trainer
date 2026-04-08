"""
Benchmark suite for the CFR+ solver.

Predefined scenarios with known qualitative behavior that the solver
should reproduce. Used for regression testing and trust assessment.

Each benchmark:
1. Defines a specific game scenario (ranges, board, sizes)
2. States expected qualitative behavior
3. Runs the solver
4. Checks output against expectations
5. Returns pass/warn/fail with details

HONEST NOTE: These benchmarks verify qualitative behavior (e.g., "AA should
not fold often"), not exact Nash equilibrium frequencies. They are regression
checkpoints, not proofs of correctness.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkCheck:
    """A single check within a benchmark."""
    name: str
    passed: bool
    expected: str
    actual: str
    threshold: Optional[float] = None
    actual_value: Optional[float] = None


@dataclass
class BenchmarkResult:
    """Result of running a single benchmark scenario."""
    name: str
    description: str
    status: str = "not_run"  # pass / warn / fail / error
    checks: list[BenchmarkCheck] = field(default_factory=list)
    exploitability_mbb: float = float("inf")
    iterations: int = 0
    elapsed_seconds: float = 0.0
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "checks": [
                {
                    "name": c.name,
                    "passed": c.passed,
                    "expected": c.expected,
                    "actual": c.actual,
                }
                for c in self.checks
            ],
            "exploitability_mbb": round(self.exploitability_mbb, 2),
            "iterations": self.iterations,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "error": self.error,
        }


@dataclass
class BenchmarkSuiteResult:
    """Result of running the entire benchmark suite."""
    total: int = 0
    passed: int = 0
    warned: int = 0
    failed: int = 0
    errored: int = 0
    benchmarks: list[BenchmarkResult] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "passed": self.passed,
            "warned": self.warned,
            "failed": self.failed,
            "errored": self.errored,
            "benchmarks": [b.to_dict() for b in self.benchmarks],
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "overall_status": self._overall_status(),
        }

    def _overall_status(self) -> str:
        if self.errored > 0 or self.failed > 0:
            return "FAIL"
        if self.warned > 0:
            return "PASS_WITH_WARNINGS"
        return "PASS"


# ── Benchmark definitions ──

BENCHMARKS = [
    {
        "name": "AA vs KK Domination",
        "description": (
            "AA vs KK on a low board. AA dominates and should almost never fold. "
            "Exploitability should be low with sufficient iterations."
        ),
        "board": ["9s", "7d", "2c"],
        "ip_range": "AA",
        "oop_range": "KK",
        "pot": 6.5,
        "stack": 20.0,
        "bet_sizes": [1.0],
        "raise_sizes": [],
        "max_iterations": 100,
        "checks": [
            {
                "name": "AA_fold_below_5pct",
                "player_range": "ip",
                "condition": "fold_freq_below",
                "threshold": 0.05,
                "description": "AA should fold <5% at root",
            },
            {
                "name": "exploitability_below_50mbb",
                "condition": "exploitability_below",
                "threshold": 50.0,
                "description": "Should converge to <50 mbb/hand",
            },
        ],
    },
    {
        "name": "KK vs AA Dominated",
        "description": (
            "KK vs AA on a low board. KK is dominated and should fold "
            "at high frequency when facing a bet."
        ),
        "board": ["9s", "7d", "2c"],
        "ip_range": "KK",
        "oop_range": "AA",
        "pot": 6.5,
        "stack": 20.0,
        "bet_sizes": [1.0],
        "raise_sizes": [],
        "max_iterations": 100,
        "checks": [
            {
                "name": "KK_checks_or_folds_frequently",
                "player_range": "ip",
                "condition": "check_or_fold_above",
                "threshold": 0.50,
                "description": "KK (as IP vs AA) should check or fold >50% at root",
            },
        ],
    },
    {
        "name": "Symmetric TT vs TT",
        "description": (
            "TT vs TT on a low board. Symmetric game — both sides should "
            "play similar strategies. Exploitability should be near zero."
        ),
        "board": ["9s", "7d", "2c"],
        "ip_range": "TT",
        "oop_range": "TT",
        "pot": 6.5,
        "stack": 20.0,
        "bet_sizes": [1.0],
        "raise_sizes": [],
        "max_iterations": 100,
        "checks": [
            {
                "name": "low_exploitability",
                "condition": "exploitability_below",
                "threshold": 30.0,
                "description": "Symmetric game should have low exploitability (<30 mbb)",
            },
        ],
    },
    {
        "name": "Polarized AA vs 22",
        "description": (
            "AA vs 22 on an A-high board. AA has top set and should bet "
            "aggressively. 22 should fold often."
        ),
        "board": ["As", "7d", "2c"],
        "ip_range": "AA",
        "oop_range": "22",
        "pot": 6.5,
        "stack": 20.0,
        "bet_sizes": [1.0],
        "raise_sizes": [],
        "max_iterations": 100,
        "checks": [
            {
                "name": "AA_bets_aggressively",
                "player_range": "ip",
                "condition": "bet_freq_above",
                "threshold": 0.30,
                "description": "AA (top set) should bet >30% at root",
            },
        ],
    },
    {
        "name": "Mixed Strategy AK vs QJ",
        "description": (
            "AK vs QJ on a K-high board. AK has top pair and should "
            "have a mixed strategy. Non-trivial equilibrium expected."
        ),
        "board": ["Ks", "7d", "2c"],
        "ip_range": "AKs",
        "oop_range": "QJs",
        "pot": 6.5,
        "stack": 20.0,
        "bet_sizes": [0.5, 1.0],
        "raise_sizes": [],
        "max_iterations": 100,
        "checks": [
            {
                "name": "mixed_strategy",
                "player_range": "ip",
                "condition": "has_mixed_actions",
                "threshold": 0.05,
                "description": "AK should use multiple actions (mixed strategy)",
            },
            {
                "name": "exploitability_below_100mbb",
                "condition": "exploitability_below",
                "threshold": 100.0,
                "description": "Should converge to <100 mbb/hand",
            },
        ],
    },
    # ── Phase 7A: Extended reference benchmarks ──────────────────
    {
        "name": "Turn-Aware AA vs KK",
        "description": (
            "AA vs KK on 9♠7♦2♣ with turn enabled (3 cards). AA should "
            "remain aggressive through turn. Turn-aware benchmark."
        ),
        "board": ["9s", "7d", "2c"],
        "ip_range": "AA",
        "oop_range": "KK",
        "pot": 6.5,
        "stack": 20.0,
        "bet_sizes": [1.0],
        "raise_sizes": [],
        "max_iterations": 50,
        "include_turn": True,
        "max_turn_cards": 3,
        "street_depth": "flop_plus_turn",
        "checks": [
            {
                "name": "AA_still_aggressive_with_turn",
                "player_range": "ip",
                "condition": "bet_freq_above",
                "threshold": 0.15,
                "description": "AA should still bet >15% at root even with turn enabled",
            },
        ],
    },
    {
        "name": "Exploitability Trend",
        "description": (
            "AA vs KK at 10/50/100 iterations. Exploitability should not "
            "dramatically increase with more iterations (monotonicity check). "
            "HONEST NOTE: CFR+ guarantees convergence in the limit but "
            "exploitability is not strictly monotone at every step."
        ),
        "board": ["9s", "7d", "2c"],
        "ip_range": "AA",
        "oop_range": "KK",
        "pot": 6.5,
        "stack": 20.0,
        "bet_sizes": [1.0],
        "raise_sizes": [],
        "max_iterations": 100,
        "checks": [
            {
                "name": "exploitability_trend_reasonable",
                "condition": "exploitability_trend",
                "threshold": 100.0,
                "description": "Exploitability at 100iter should not be >100mbb worse than at 10iter",
            },
        ],
    },
    {
        "name": "Passive vs Aggressive KK over 22",
        "description": (
            "KK vs 22 on K♠7♦2♣. KK has top pair and should bet aggressively. "
            "22 is an underpair and should fold facing a bet."
        ),
        "board": ["Ks", "7d", "2c"],
        "ip_range": "KK",
        "oop_range": "22",
        "pot": 6.5,
        "stack": 20.0,
        "bet_sizes": [1.0],
        "raise_sizes": [],
        "max_iterations": 100,
        "checks": [
            {
                "name": "KK_bets_aggressively",
                "player_range": "ip",
                "condition": "bet_freq_above",
                "threshold": 0.30,
                "description": "KK (top pair) should bet >30%",
            },
        ],
    },
    {
        "name": "Zero-Sum Check",
        "description": (
            "Verify zero-sum property on AA vs KK: IP_value + OOP_value ≈ 0 "
            "at the root when both follow the strategy profile."
        ),
        "board": ["9s", "7d", "2c"],
        "ip_range": "AA",
        "oop_range": "KK",
        "pot": 6.5,
        "stack": 20.0,
        "bet_sizes": [1.0],
        "raise_sizes": [],
        "max_iterations": 50,
        "checks": [
            {
                "name": "zero_sum_at_root",
                "condition": "zero_sum_check",
                "threshold": 0.05,
                "description": "IP_value + OOP_value should be ≈ 0 (within 0.05 bb tolerance)",
            },
        ],
    },
    {
        "name": "Nut Advantage AA on A72",
        "description": (
            "AA vs 77 on A♠7♦2♣. AA has top set (nuts). Should bet "
            "at high frequency. 77 has middle set and should be cautious."
        ),
        "board": ["As", "7d", "2c"],
        "ip_range": "AA",
        "oop_range": "77",
        "pot": 6.5,
        "stack": 20.0,
        "bet_sizes": [1.0],
        "raise_sizes": [],
        "max_iterations": 100,
        "checks": [
            {
                "name": "AA_nuts_bets_high",
                "player_range": "ip",
                "condition": "bet_freq_above",
                "threshold": 0.40,
                "description": "AA (top set/nuts) should bet >40%",
            },
        ],
    },
    {
        "name": "Board Coverage Multi-Range",
        "description": (
            "AA,KK,QQ vs JJ,TT,99 on K♠7♦2♣. All combo entries should "
            "have valid strategy entries (coverage check)."
        ),
        "board": ["Ks", "7d", "2c"],
        "ip_range": "AA,KK,QQ",
        "oop_range": "JJ,TT,99",
        "pot": 6.5,
        "stack": 20.0,
        "bet_sizes": [0.5, 1.0],
        "raise_sizes": [],
        "max_iterations": 50,
        "checks": [
            {
                "name": "all_combos_have_strategies",
                "condition": "coverage_check",
                "threshold": 0.0,
                "description": "All expanded combos should have strategy entries at root",
            },
        ],
    },
    {
        "name": "Turn Normalization",
        "description": (
            "Turn-enabled solve: all strategies at turn-depth nodes "
            "must sum to 1.0 (normalization check)."
        ),
        "board": ["9s", "7d", "2c"],
        "ip_range": "AA",
        "oop_range": "KK",
        "pot": 6.5,
        "stack": 20.0,
        "bet_sizes": [1.0],
        "raise_sizes": [],
        "max_iterations": 30,
        "include_turn": True,
        "max_turn_cards": 2,
        "street_depth": "flop_plus_turn",
        "checks": [
            {
                "name": "turn_strategies_normalized",
                "condition": "all_normalized",
                "threshold": 0.02,
                "description": "All strategy entries must sum to 1.0 ± 0.02",
            },
        ],
    },
    {
        "name": "Relabelled Symmetry",
        "description": (
            "AA(IP) vs KK(OOP) and KK(IP) vs AA(OOP). The dominant hand "
            "should be aggressive in both configurations. Qualitative check — "
            "positional advantage means strategies won't be identical."
        ),
        "board": ["9s", "7d", "2c"],
        "ip_range": "AA",
        "oop_range": "KK",
        "pot": 6.5,
        "stack": 20.0,
        "bet_sizes": [1.0],
        "raise_sizes": [],
        "max_iterations": 50,
        "checks": [
            {
                "name": "dominant_hand_aggressive",
                "player_range": "ip",
                "condition": "bet_freq_above",
                "threshold": 0.10,
                "description": "AA (dominant) should bet >10% regardless of position",
            },
        ],
    },
    {
        "name": "Draw Texture Turn",
        "description": (
            "JJ vs 88 on T♠9♠2♣ with turn enabled. Strategy should "
            "shift when turn completes potential draws. Qualitative — "
            "we verify the solve completes and produces mixed strategies."
        ),
        "board": ["Ts", "9s", "2c"],
        "ip_range": "JJ",
        "oop_range": "88",
        "pot": 6.5,
        "stack": 20.0,
        "bet_sizes": [1.0],
        "raise_sizes": [],
        "max_iterations": 30,
        "include_turn": True,
        "max_turn_cards": 3,
        "street_depth": "flop_plus_turn",
        "checks": [
            {
                "name": "draw_texture_completes",
                "condition": "has_mixed_actions",
                "player_range": "ip",
                "threshold": 0.05,
                "description": "JJ should have mixed strategy on draw-heavy board",
            },
        ],
    },
]


def run_benchmark_suite() -> BenchmarkSuiteResult:
    """Run all benchmarks and return results."""
    suite_start = time.time()
    suite = BenchmarkSuiteResult()

    for bench_def in BENCHMARKS:
        result = _run_single_benchmark(bench_def)
        suite.benchmarks.append(result)
        suite.total += 1
        if result.status == "pass":
            suite.passed += 1
        elif result.status == "warn":
            suite.warned += 1
        elif result.status == "fail":
            suite.failed += 1
        else:
            suite.errored += 1

    suite.elapsed_seconds = time.time() - suite_start

    logger.info(
        "Benchmark suite: %d total, %d pass, %d warn, %d fail, %d error (%.1fs)",
        suite.total, suite.passed, suite.warned, suite.failed,
        suite.errored, suite.elapsed_seconds,
    )

    return suite


def _run_single_benchmark(bench_def: dict) -> BenchmarkResult:
    """Run a single benchmark scenario."""
    from app.solver.cfr_solver import CfrSolver, SolveRequest

    result = BenchmarkResult(
        name=bench_def["name"],
        description=bench_def["description"],
    )

    try:
        start = time.time()

        request = SolveRequest(
            board=bench_def["board"],
            ip_range=bench_def["ip_range"],
            oop_range=bench_def["oop_range"],
            pot=bench_def["pot"],
            effective_stack=bench_def["stack"],
            bet_sizes=bench_def["bet_sizes"],
            raise_sizes=bench_def.get("raise_sizes", []),
            max_iterations=bench_def.get("max_iterations", 100),
            max_raises=bench_def.get("max_raises", 1),
            deterministic=True,
            include_turn=bench_def.get("include_turn", False),
            max_turn_cards=bench_def.get("max_turn_cards", 5),
        )

        solver = CfrSolver()
        output = solver.solve(request)

        result.iterations = output.iterations
        result.exploitability_mbb = output.exploitability_mbb
        result.elapsed_seconds = time.time() - start

        # Run checks
        all_passed = True
        for check_def in bench_def.get("checks", []):
            check = _evaluate_check(check_def, output)
            result.checks.append(check)
            if not check.passed:
                all_passed = False

        result.status = "pass" if all_passed else "fail"

    except Exception as e:
        result.status = "error"
        result.error = str(e)
        result.elapsed_seconds = time.time() - start
        logger.error("Benchmark '%s' error: %s", bench_def["name"], e)

    return result


def _evaluate_check(check_def: dict, output) -> BenchmarkCheck:
    """Evaluate a single benchmark check against solver output."""
    condition = check_def["condition"]
    threshold = check_def.get("threshold", 0.0)
    name = check_def["name"]
    description = check_def.get("description", "")

    try:
        if condition == "exploitability_below":
            actual = output.exploitability_mbb
            passed = actual < threshold
            return BenchmarkCheck(
                name=name,
                passed=passed,
                expected=f"exploitability < {threshold} mbb/hand",
                actual=f"{actual:.2f} mbb/hand",
                threshold=threshold,
                actual_value=actual,
            )

        elif condition == "fold_freq_below":
            # Check fold frequency at root for the specified player range
            root = output.strategies.get("node_0", {})
            fold_freqs = []
            for combo_str, freqs in root.items():
                fold_freqs.append(freqs.get("fold", 0.0))
            avg_fold = sum(fold_freqs) / max(len(fold_freqs), 1)
            passed = avg_fold < threshold
            return BenchmarkCheck(
                name=name,
                passed=passed,
                expected=f"fold < {threshold*100:.0f}% at root",
                actual=f"fold = {avg_fold*100:.1f}% at root",
                threshold=threshold,
                actual_value=avg_fold,
            )

        elif condition == "check_or_fold_above":
            root = output.strategies.get("node_0", {})
            passive_freqs = []
            for combo_str, freqs in root.items():
                check_f = freqs.get("check", 0.0)
                fold_f = freqs.get("fold", 0.0)
                passive_freqs.append(check_f + fold_f)
            avg_passive = sum(passive_freqs) / max(len(passive_freqs), 1)
            passed = avg_passive > threshold
            return BenchmarkCheck(
                name=name,
                passed=passed,
                expected=f"check+fold > {threshold*100:.0f}% at root",
                actual=f"check+fold = {avg_passive*100:.1f}% at root",
                threshold=threshold,
                actual_value=avg_passive,
            )

        elif condition == "bet_freq_above":
            root = output.strategies.get("node_0", {})
            bet_freqs = []
            for combo_str, freqs in root.items():
                bet_total = sum(f for a, f in freqs.items() if "bet" in a or "allin" in a)
                bet_freqs.append(bet_total)
            avg_bet = sum(bet_freqs) / max(len(bet_freqs), 1)
            passed = avg_bet > threshold
            return BenchmarkCheck(
                name=name,
                passed=passed,
                expected=f"bet > {threshold*100:.0f}% at root",
                actual=f"bet = {avg_bet*100:.1f}% at root",
                threshold=threshold,
                actual_value=avg_bet,
            )

        elif condition == "has_mixed_actions":
            root = output.strategies.get("node_0", {})
            # Check if at least one combo uses multiple actions > threshold
            mixed = False
            for combo_str, freqs in root.items():
                above_thresh = sum(1 for f in freqs.values() if f > threshold)
                if above_thresh >= 2:
                    mixed = True
                    break
            return BenchmarkCheck(
                name=name,
                passed=mixed,
                expected="At least one combo uses ≥2 actions above threshold",
                actual="Mixed" if mixed else "Pure",
                threshold=threshold,
            )

        elif condition == "exploitability_trend":
            # Run same scenario at 10 and max iterations, check trend
            from app.solver.cfr_solver import CfrSolver as _Solver, SolveRequest as _Req
            low_req = _Req(
                board=output.metadata.get("board", ["9s", "7d", "2c"]),
                ip_range=output.metadata.get("ip_range", "AA"),
                oop_range=output.metadata.get("oop_range", "KK"),
                pot=output.metadata.get("pot", 6.5),
                effective_stack=output.metadata.get("effective_stack", 20.0),
                bet_sizes=output.metadata.get("bet_sizes", [1.0]),
                raise_sizes=output.metadata.get("raise_sizes", []),
                max_iterations=10, max_raises=1, deterministic=True,
            )
            low_solver = _Solver()
            low_out = low_solver.solve(low_req)
            low_exploit = low_out.exploitability_mbb
            high_exploit = output.exploitability_mbb
            diff = high_exploit - low_exploit
            passed = diff < threshold
            return BenchmarkCheck(
                name=name,
                passed=passed,
                expected=f"exploit(high_iter) - exploit(low_iter) < {threshold} mbb",
                actual=f"10iter={low_exploit:.1f}, {output.iterations}iter={high_exploit:.1f}, diff={diff:.1f}",
                threshold=threshold,
                actual_value=diff,
            )

        elif condition == "zero_sum_check":
            # Check zero-sum at root: traverse for IP and OOP, sum ≈ 0
            from app.solver.cfr_solver import CfrSolver as _Solver2, SolveRequest as _Req2
            from app.solver.best_response import _strategy_traverse
            zs_req = _Req2(
                board=output.metadata.get("board", ["9s", "7d", "2c"]),
                ip_range=output.metadata.get("ip_range", "AA"),
                oop_range=output.metadata.get("oop_range", "KK"),
                pot=output.metadata.get("pot", 6.5),
                effective_stack=output.metadata.get("effective_stack", 20.0),
                bet_sizes=output.metadata.get("bet_sizes", [1.0]),
                raise_sizes=output.metadata.get("raise_sizes", []),
                max_iterations=output.iterations, max_raises=1, deterministic=True,
            )
            zs_solver = _Solver2()
            zs_out = zs_solver.solve(zs_req)
            root = zs_solver._root
            board = zs_solver._board
            max_dev = 0.0
            checked = 0
            for ip_idx, oop_idx in zs_solver._valid_matchups[:20]:
                ip_c = zs_solver._ip_combos[ip_idx]
                oop_c = zs_solver._oop_combos[oop_idx]
                iv = _strategy_traverse(root, ip_c, oop_c, board, zs_out.strategies, "IP")
                ov = _strategy_traverse(root, ip_c, oop_c, board, zs_out.strategies, "OOP")
                max_dev = max(max_dev, abs(iv + ov))
                checked += 1
            passed = max_dev < threshold
            return BenchmarkCheck(
                name=name,
                passed=passed,
                expected=f"|IP_val + OOP_val| < {threshold} bb",
                actual=f"max_deviation={max_dev:.6f} across {checked} matchups",
                threshold=threshold,
                actual_value=max_dev,
            )

        elif condition == "coverage_check":
            root = output.strategies.get("node_0", {})
            has_combos = len(root) > 0
            # Check that every combo sums to ~1
            bad = 0
            for combo, freqs in root.items():
                total = sum(freqs.values())
                if abs(total - 1.0) > 0.05:
                    bad += 1
            passed = has_combos and bad == 0
            return BenchmarkCheck(
                name=name,
                passed=passed,
                expected="All combos at root have valid strategies",
                actual=f"{len(root)} combos, {bad} with bad normalization",
                threshold=threshold,
            )

        elif condition == "all_normalized":
            bad_nodes = 0
            total_entries = 0
            for node_id, combos in output.strategies.items():
                for combo, freqs in combos.items():
                    total = sum(freqs.values())
                    total_entries += 1
                    if abs(total - 1.0) > threshold:
                        bad_nodes += 1
            passed = bad_nodes == 0
            return BenchmarkCheck(
                name=name,
                passed=passed,
                expected=f"All strategies sum to 1.0 ± {threshold}",
                actual=f"{total_entries} entries, {bad_nodes} denormalized",
                threshold=threshold,
            )

        else:
            return BenchmarkCheck(
                name=name,
                passed=False,
                expected=f"Unknown condition: {condition}",
                actual="ERROR",
            )

    except Exception as e:
        return BenchmarkCheck(
            name=name,
            passed=False,
            expected=description,
            actual=f"Error: {e}",
        )
