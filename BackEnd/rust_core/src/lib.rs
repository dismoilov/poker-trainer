/// poker_core — Phase 14: Parallel CFR+ via Rayon.
///
/// Phase 13A: Hand evaluation and batch showdown equity computation.
/// Phase 13B: CFR+ traversal inner loop on flat arrays (flop-only).
/// Phase 13C: Extended CFR+ to support turn chance nodes with blockers.
/// Phase 13D: Extended CFR+ to support river chance nodes — full double-street.
/// Phase 14:  Rayon-based parallel CFR+ iterations.
///
/// Exposed to Python via PyO3.

use pyo3::prelude::*;
use numpy::{PyReadonlyArray1, PyReadwriteArray1};

mod hand_eval;
mod equity;
mod cfr;

/// Evaluate the best 5-card hand from a list of card integers.
#[pyfunction]
fn evaluate_hand(cards: Vec<u8>) -> u32 {
    hand_eval::evaluate_best(&cards)
}

/// Compute showdown equity for a single matchup.
#[pyfunction]
fn compute_equity(ip_cards: (u8, u8), oop_cards: (u8, u8), board: Vec<u8>) -> f64 {
    equity::compute_equity(ip_cards, oop_cards, &board)
}

/// Batch compute showdown equity for multiple matchups on the same board.
#[pyfunction]
fn batch_compute_equity(
    ip_hands: Vec<(u8, u8)>,
    oop_hands: Vec<(u8, u8)>,
    board: Vec<u8>,
    matchups: Vec<(usize, usize)>,
) -> Vec<f64> {
    equity::batch_equity(&ip_hands, &oop_hands, &board, &matchups)
}

/// Batch compute equity across multiple board variants.
#[pyfunction]
fn batch_compute_equity_multi_board(
    ip_hands: Vec<(u8, u8)>,
    oop_hands: Vec<(u8, u8)>,
    boards: Vec<Vec<u8>>,
    matchups_per_board: Vec<Vec<(usize, usize)>>,
) -> Vec<(usize, usize, usize, f64)> {
    equity::batch_equity_multi_board(&ip_hands, &oop_hands, &boards, &matchups_per_board)
}

/// Phase 14: Run N iterations of CFR+ traversal on flat arrays.
///
/// Supports both serial and parallel modes:
///   parallel=false: sequential update CFR+ (Phase 13D compatible)
///   parallel=true:  simultaneous update CFR+ via Rayon (Phase 14)
///
/// IMPORTANT: When parallel=true, the GIL is released to allow Rayon threads
/// to execute concurrently. All numpy array data is borrowed as raw slices
/// before GIL release.
///
/// Returns: convergence metric (float)
#[pyfunction]
fn cfr_iterate<'py>(
    py: Python<'py>,
    node_types: PyReadonlyArray1<'py, i32>,
    node_players: PyReadonlyArray1<'py, i32>,
    node_pots: PyReadonlyArray1<'py, f64>,
    node_num_actions: PyReadonlyArray1<'py, i32>,
    node_first_child: PyReadonlyArray1<'py, i32>,
    children_ids: PyReadonlyArray1<'py, i32>,
    node_chance_card_abs: PyReadonlyArray1<'py, i32>,
    node_chance_equity_idx: PyReadonlyArray1<'py, i32>,
    ip_hole_cards_abs: PyReadonlyArray1<'py, i32>,
    oop_hole_cards_abs: PyReadonlyArray1<'py, i32>,
    turn_idx_to_abs: PyReadonlyArray1<'py, i32>,
    num_turn_cards: usize,
    num_river_cards: usize,
    info_map: PyReadonlyArray1<'py, i32>,
    max_combos: usize,
    mut regrets: PyReadwriteArray1<'py, f64>,
    mut strategy_sums: PyReadwriteArray1<'py, f64>,
    max_actions: usize,
    equity_tables: PyReadonlyArray1<'py, f64>,
    num_ip: usize,
    num_oop: usize,
    matchup_ip: PyReadonlyArray1<'py, i32>,
    matchup_oop: PyReadonlyArray1<'py, i32>,
    num_iterations: usize,
    root_node_id: usize,
    parallel: bool,
) -> PyResult<f64> {
    let node_types_s = node_types.as_slice()?;
    let node_players_s = node_players.as_slice()?;
    let node_pots_s = node_pots.as_slice()?;
    let node_num_actions_s = node_num_actions.as_slice()?;
    let node_first_child_s = node_first_child.as_slice()?;
    let children_ids_s = children_ids.as_slice()?;
    let node_chance_card_abs_s = node_chance_card_abs.as_slice()?;
    let node_chance_equity_idx_s = node_chance_equity_idx.as_slice()?;
    let ip_hole_cards_abs_s = ip_hole_cards_abs.as_slice()?;
    let oop_hole_cards_abs_s = oop_hole_cards_abs.as_slice()?;
    let turn_idx_to_abs_s = turn_idx_to_abs.as_slice()?;
    let info_map_s = info_map.as_slice()?;
    let equity_tables_s = equity_tables.as_slice()?;
    let matchup_ip_s = matchup_ip.as_slice()?;
    let matchup_oop_s = matchup_oop.as_slice()?;
    let regrets_s = regrets.as_slice_mut()?;
    let strategy_sums_s = strategy_sums.as_slice_mut()?;

    // Release the GIL so Rayon threads can run concurrently
    let convergence = py.allow_threads(|| {
        if parallel {
            cfr::cfr_iterate_parallel(
                node_types_s, node_players_s, node_pots_s, node_num_actions_s,
                node_first_child_s, children_ids_s,
                node_chance_card_abs_s, node_chance_equity_idx_s,
                ip_hole_cards_abs_s, oop_hole_cards_abs_s,
                turn_idx_to_abs_s, num_turn_cards, num_river_cards,
                info_map_s, max_combos,
                regrets_s, strategy_sums_s, max_actions,
                equity_tables_s, num_ip, num_oop,
                matchup_ip_s, matchup_oop_s,
                num_iterations, root_node_id,
            )
        } else {
            cfr::cfr_iterate(
                node_types_s, node_players_s, node_pots_s, node_num_actions_s,
                node_first_child_s, children_ids_s,
                node_chance_card_abs_s, node_chance_equity_idx_s,
                ip_hole_cards_abs_s, oop_hole_cards_abs_s,
                turn_idx_to_abs_s, num_turn_cards, num_river_cards,
                info_map_s, max_combos,
                regrets_s, strategy_sums_s, max_actions,
                equity_tables_s, num_ip, num_oop,
                matchup_ip_s, matchup_oop_s,
                num_iterations, root_node_id,
            )
        }
    });

    Ok(convergence)
}

/// Phase 15B: Run N iterations of CFR+ with progress reporting and cooperative cancellation.
///
/// Same as cfr_iterate but with a shared control array:
///   control[0]: iterations completed (Rust writes)
///   control[1]: cancel flag (Python writes 1 to cancel, Rust reads between iterations)
///
/// Returns: (convergence_metric, actual_iterations_completed)
#[pyfunction]
fn cfr_iterate_with_control<'py>(
    py: Python<'py>,
    node_types: PyReadonlyArray1<'py, i32>,
    node_players: PyReadonlyArray1<'py, i32>,
    node_pots: PyReadonlyArray1<'py, f64>,
    node_num_actions: PyReadonlyArray1<'py, i32>,
    node_first_child: PyReadonlyArray1<'py, i32>,
    children_ids: PyReadonlyArray1<'py, i32>,
    node_chance_card_abs: PyReadonlyArray1<'py, i32>,
    node_chance_equity_idx: PyReadonlyArray1<'py, i32>,
    ip_hole_cards_abs: PyReadonlyArray1<'py, i32>,
    oop_hole_cards_abs: PyReadonlyArray1<'py, i32>,
    turn_idx_to_abs: PyReadonlyArray1<'py, i32>,
    num_turn_cards: usize,
    num_river_cards: usize,
    info_map: PyReadonlyArray1<'py, i32>,
    max_combos: usize,
    mut regrets: PyReadwriteArray1<'py, f64>,
    mut strategy_sums: PyReadwriteArray1<'py, f64>,
    max_actions: usize,
    equity_tables: PyReadonlyArray1<'py, f64>,
    num_ip: usize,
    num_oop: usize,
    matchup_ip: PyReadonlyArray1<'py, i32>,
    matchup_oop: PyReadonlyArray1<'py, i32>,
    num_iterations: usize,
    root_node_id: usize,
    mut control: PyReadwriteArray1<'py, i32>,
) -> PyResult<(f64, usize)> {
    let node_types_s = node_types.as_slice()?;
    let node_players_s = node_players.as_slice()?;
    let node_pots_s = node_pots.as_slice()?;
    let node_num_actions_s = node_num_actions.as_slice()?;
    let node_first_child_s = node_first_child.as_slice()?;
    let children_ids_s = children_ids.as_slice()?;
    let node_chance_card_abs_s = node_chance_card_abs.as_slice()?;
    let node_chance_equity_idx_s = node_chance_equity_idx.as_slice()?;
    let ip_hole_cards_abs_s = ip_hole_cards_abs.as_slice()?;
    let oop_hole_cards_abs_s = oop_hole_cards_abs.as_slice()?;
    let turn_idx_to_abs_s = turn_idx_to_abs.as_slice()?;
    let info_map_s = info_map.as_slice()?;
    let equity_tables_s = equity_tables.as_slice()?;
    let matchup_ip_s = matchup_ip.as_slice()?;
    let matchup_oop_s = matchup_oop.as_slice()?;
    let regrets_s = regrets.as_slice_mut()?;
    let strategy_sums_s = strategy_sums.as_slice_mut()?;
    let control_s = control.as_slice_mut()?;

    // Release the GIL so Python can poll progress / set cancel flag
    let result = py.allow_threads(|| {
        cfr::cfr_iterate_with_control(
            node_types_s, node_players_s, node_pots_s, node_num_actions_s,
            node_first_child_s, children_ids_s,
            node_chance_card_abs_s, node_chance_equity_idx_s,
            ip_hole_cards_abs_s, oop_hole_cards_abs_s,
            turn_idx_to_abs_s, num_turn_cards, num_river_cards,
            info_map_s, max_combos,
            regrets_s, strategy_sums_s, max_actions,
            equity_tables_s, num_ip, num_oop,
            matchup_ip_s, matchup_oop_s,
            num_iterations, root_node_id,
            control_s,
        )
    });

    Ok(result)
}

/// Return version info for diagnostics.
#[pyfunction]
fn version() -> String {
    "poker_core 0.6.0 (Phase 15B: progress/cancel control)".to_string()
}

/// Python module definition
#[pymodule]
fn poker_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(evaluate_hand, m)?)?;
    m.add_function(wrap_pyfunction!(compute_equity, m)?)?;
    m.add_function(wrap_pyfunction!(batch_compute_equity, m)?)?;
    m.add_function(wrap_pyfunction!(batch_compute_equity_multi_board, m)?)?;
    m.add_function(wrap_pyfunction!(cfr_iterate, m)?)?;
    m.add_function(wrap_pyfunction!(cfr_iterate_with_control, m)?)?;
    m.add_function(wrap_pyfunction!(version, m)?)?;
    Ok(())
}
