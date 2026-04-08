/// Phase 14: Parallel CFR+ traversal via Rayon.
///
/// Builds on Phase 13D (flop + turn + river traversal).
/// Adds per-iteration batch parallelism across matchups using Rayon.
///
/// PARALLELIZATION ARCHITECTURE:
///   1. Each iteration's matchups are processed in parallel via Rayon
///   2. Each thread-partition gets its own delta buffers (regret_deltas, strategy_deltas)
///   3. Strategy computation reads from GLOBAL regrets (frozen snapshot for the iteration)
///   4. Regret/strategy deltas accumulate into LOCAL per-thread buffers (no races)
///   5. After all matchups, thread deltas are reduced (summed)
///   6. Global arrays updated: regrets += deltas, then floor at 0 (CFR+)
///
/// This is the standard "simultaneous update" CFR+ variant.
/// It is mathematically correct and race-free, but produces slightly different
/// intermediate convergence values vs the serial "sequential update" variant
/// (which applies flooring after each matchup). Both converge to the same equilibrium.
///
/// Node types:
///   0 = action node
///   1 = fold_ip terminal
///   2 = fold_oop terminal
///   3 = showdown terminal
///   4 = chance_turn (flop→turn card dealing)
///   5 = chance_river (turn→river card dealing)

use rayon::prelude::*;

/// Read-only context for parallel traversal.
/// Shared across all threads within one iteration.
pub struct CfrReadContext<'a> {
    pub node_types: &'a [i32],
    pub node_players: &'a [i32],
    pub node_pots: &'a [f64],
    pub node_num_actions: &'a [i32],
    pub node_first_child: &'a [i32],
    pub children_ids: &'a [i32],
    pub node_chance_card_abs: &'a [i32],
    pub node_chance_equity_idx: &'a [i32],
    pub ip_hole_cards_abs: &'a [i32],
    pub oop_hole_cards_abs: &'a [i32],
    pub turn_idx_to_abs: &'a [i32],
    pub num_turn_cards: usize,
    pub num_river_cards: usize,
    pub info_map: &'a [i32],
    pub max_combos: usize,
    pub regrets: &'a [f64],  // READ-ONLY: frozen snapshot for strategy computation
    pub max_actions: usize,
    pub equity_tables: &'a [f64],
    pub num_oop: usize,
    pub num_ip: usize,
}

// CfrReadContext is safe to share across threads (all fields are immutable references)
unsafe impl<'a> Send for CfrReadContext<'a> {}
unsafe impl<'a> Sync for CfrReadContext<'a> {}

/// Mutable context for serial traversal (backward-compatible with Phase 13D).
pub struct CfrContext<'a> {
    pub node_types: &'a [i32],
    pub node_players: &'a [i32],
    pub node_pots: &'a [f64],
    pub node_num_actions: &'a [i32],
    pub node_first_child: &'a [i32],
    pub children_ids: &'a [i32],
    pub node_chance_card_abs: &'a [i32],
    pub node_chance_equity_idx: &'a [i32],
    pub ip_hole_cards_abs: &'a [i32],
    pub oop_hole_cards_abs: &'a [i32],
    pub turn_idx_to_abs: &'a [i32],
    pub num_turn_cards: usize,
    pub num_river_cards: usize,
    pub info_map: &'a [i32],
    pub max_combos: usize,
    pub regrets: &'a mut [f64],
    pub strategy_sums: &'a mut [f64],
    pub max_actions: usize,
    pub equity_tables: &'a [f64],
    pub num_oop: usize,
    pub num_ip: usize,
}

// ══════════════════════════════════════════════════════════════════
//  SERIAL TRAVERSAL (Phase 13D compatible — sequential update CFR+)
// ══════════════════════════════════════════════════════════════════

pub fn cfr_traverse(
    ctx: &mut CfrContext,
    node_id: usize,
    ip_combo_idx: usize,
    oop_combo_idx: usize,
    ip_reach: f64,
    oop_reach: f64,
    traversing_player: i32,
    active_turn_idx: usize,
    active_river_idx: usize,
) -> f64 {
    let node_type = ctx.node_types[node_id];

    if node_type >= 1 && node_type <= 3 {
        return terminal_value_read(
            ctx.node_pots, ctx.equity_tables, ctx.num_ip, ctx.num_oop,
            ctx.num_river_cards, node_id, node_type,
            ip_combo_idx, oop_combo_idx, traversing_player,
            active_turn_idx, active_river_idx,
        );
    }

    if node_type == 4 {
        return turn_chance_value_serial(ctx, node_id, ip_combo_idx, oop_combo_idx,
                                         ip_reach, oop_reach, traversing_player,
                                         active_turn_idx, active_river_idx);
    }
    if node_type == 5 {
        return river_chance_value_serial(ctx, node_id, ip_combo_idx, oop_combo_idx,
                                          ip_reach, oop_reach, traversing_player,
                                          active_turn_idx);
    }

    // Action node (type 0)
    let player = ctx.node_players[node_id];
    let is_ip = player == 0;
    let combo_idx = if is_ip { ip_combo_idx } else { oop_combo_idx };
    let num_actions = ctx.node_num_actions[node_id] as usize;

    if num_actions == 0 { return 0.0; }

    let info_idx = ctx.info_map[node_id * ctx.max_combos + combo_idx];
    if info_idx < 0 { return 0.0; }
    let info_idx = info_idx as usize;

    let base = info_idx * ctx.max_actions;
    let strategy = compute_strategy(ctx.regrets, base, num_actions);

    let first_child = ctx.node_first_child[node_id] as usize;

    if player == traversing_player {
        let mut action_values = [0.0f64; 16];
        let mut node_value = 0.0f64;

        for a_idx in 0..num_actions {
            let child_id = ctx.children_ids[first_child + a_idx] as usize;
            let s_a = strategy[a_idx];
            let child_val = if is_ip {
                cfr_traverse(ctx, child_id, ip_combo_idx, oop_combo_idx,
                             ip_reach * s_a, oop_reach, traversing_player,
                             active_turn_idx, active_river_idx)
            } else {
                cfr_traverse(ctx, child_id, ip_combo_idx, oop_combo_idx,
                             ip_reach, oop_reach * s_a, traversing_player,
                             active_turn_idx, active_river_idx)
            };
            action_values[a_idx] = child_val;
            node_value += s_a * child_val;
        }

        // Update regrets (CFR+: floor at 0)
        let opponent_reach = if is_ip { oop_reach } else { ip_reach };
        for a_idx in 0..num_actions {
            let regret = action_values[a_idx] - node_value;
            let new_r = ctx.regrets[base + a_idx] + opponent_reach * regret;
            ctx.regrets[base + a_idx] = if new_r > 0.0 { new_r } else { 0.0 };
        }

        node_value
    } else {
        // Opponent: accumulate strategy, then traverse
        let own_reach = if is_ip { ip_reach } else { oop_reach };
        for a_idx in 0..num_actions {
            ctx.strategy_sums[base + a_idx] += own_reach * strategy[a_idx];
        }

        let mut node_value = 0.0f64;
        for a_idx in 0..num_actions {
            let child_id = ctx.children_ids[first_child + a_idx] as usize;
            let s_a = strategy[a_idx];
            let child_val = if is_ip {
                cfr_traverse(ctx, child_id, ip_combo_idx, oop_combo_idx,
                             ip_reach * s_a, oop_reach, traversing_player,
                             active_turn_idx, active_river_idx)
            } else {
                cfr_traverse(ctx, child_id, ip_combo_idx, oop_combo_idx,
                             ip_reach, oop_reach * s_a, traversing_player,
                             active_turn_idx, active_river_idx)
            };
            node_value += s_a * child_val;
        }

        node_value
    }
}

// ══════════════════════════════════════════════════════════════════
//  PARALLEL TRAVERSAL (Phase 14 — simultaneous update CFR+)
// ══════════════════════════════════════════════════════════════════

/// Parallel traversal: reads strategy from global regrets (ctx.regrets),
/// writes regret/strategy deltas to local per-thread buffers.
fn cfr_traverse_delta(
    ctx: &CfrReadContext,
    regret_deltas: &mut [f64],
    strategy_deltas: &mut [f64],
    node_id: usize,
    ip_combo_idx: usize,
    oop_combo_idx: usize,
    ip_reach: f64,
    oop_reach: f64,
    traversing_player: i32,
    active_turn_idx: usize,
    active_river_idx: usize,
) -> f64 {
    let node_type = ctx.node_types[node_id];

    if node_type >= 1 && node_type <= 3 {
        return terminal_value_read(
            ctx.node_pots, ctx.equity_tables, ctx.num_ip, ctx.num_oop,
            ctx.num_river_cards, node_id, node_type,
            ip_combo_idx, oop_combo_idx, traversing_player,
            active_turn_idx, active_river_idx,
        );
    }

    if node_type == 4 {
        return turn_chance_value_delta(ctx, regret_deltas, strategy_deltas,
                                       node_id, ip_combo_idx, oop_combo_idx,
                                       ip_reach, oop_reach, traversing_player,
                                       active_turn_idx, active_river_idx);
    }
    if node_type == 5 {
        return river_chance_value_delta(ctx, regret_deltas, strategy_deltas,
                                        node_id, ip_combo_idx, oop_combo_idx,
                                        ip_reach, oop_reach, traversing_player,
                                        active_turn_idx);
    }

    // Action node (type 0)
    let player = ctx.node_players[node_id];
    let is_ip = player == 0;
    let combo_idx = if is_ip { ip_combo_idx } else { oop_combo_idx };
    let num_actions = ctx.node_num_actions[node_id] as usize;

    if num_actions == 0 { return 0.0; }

    let info_idx = ctx.info_map[node_id * ctx.max_combos + combo_idx];
    if info_idx < 0 { return 0.0; }
    let info_idx = info_idx as usize;

    let base = info_idx * ctx.max_actions;
    // Read strategy from GLOBAL regrets (frozen for this iteration)
    let strategy = compute_strategy(ctx.regrets, base, num_actions);

    let first_child = ctx.node_first_child[node_id] as usize;

    if player == traversing_player {
        let mut action_values = [0.0f64; 16];
        let mut node_value = 0.0f64;

        for a_idx in 0..num_actions {
            let child_id = ctx.children_ids[first_child + a_idx] as usize;
            let s_a = strategy[a_idx];
            let child_val = if is_ip {
                cfr_traverse_delta(ctx, regret_deltas, strategy_deltas,
                                   child_id, ip_combo_idx, oop_combo_idx,
                                   ip_reach * s_a, oop_reach, traversing_player,
                                   active_turn_idx, active_river_idx)
            } else {
                cfr_traverse_delta(ctx, regret_deltas, strategy_deltas,
                                   child_id, ip_combo_idx, oop_combo_idx,
                                   ip_reach, oop_reach * s_a, traversing_player,
                                   active_turn_idx, active_river_idx)
            };
            action_values[a_idx] = child_val;
            node_value += s_a * child_val;
        }

        // Accumulate regret DELTAS (no flooring here — deferred to merge step)
        let opponent_reach = if is_ip { oop_reach } else { ip_reach };
        for a_idx in 0..num_actions {
            let regret = action_values[a_idx] - node_value;
            regret_deltas[base + a_idx] += opponent_reach * regret;
        }

        node_value
    } else {
        // Opponent: accumulate strategy DELTAS
        let own_reach = if is_ip { ip_reach } else { oop_reach };
        for a_idx in 0..num_actions {
            strategy_deltas[base + a_idx] += own_reach * strategy[a_idx];
        }

        let mut node_value = 0.0f64;
        for a_idx in 0..num_actions {
            let child_id = ctx.children_ids[first_child + a_idx] as usize;
            let s_a = strategy[a_idx];
            let child_val = if is_ip {
                cfr_traverse_delta(ctx, regret_deltas, strategy_deltas,
                                   child_id, ip_combo_idx, oop_combo_idx,
                                   ip_reach * s_a, oop_reach, traversing_player,
                                   active_turn_idx, active_river_idx)
            } else {
                cfr_traverse_delta(ctx, regret_deltas, strategy_deltas,
                                   child_id, ip_combo_idx, oop_combo_idx,
                                   ip_reach, oop_reach * s_a, traversing_player,
                                   active_turn_idx, active_river_idx)
            };
            node_value += s_a * child_val;
        }

        node_value
    }
}

// ══════════════════════════════════════════════════════════════════
//  SHARED HELPERS
// ══════════════════════════════════════════════════════════════════

/// Compute current strategy via regret-matching+ from a regret array.
#[inline]
fn compute_strategy(regrets: &[f64], base: usize, num_actions: usize) -> [f64; 16] {
    let mut strategy = [0.0f64; 16];
    let mut total = 0.0f64;
    for a_idx in 0..num_actions {
        let r = regrets[base + a_idx];
        let v = if r > 0.0 { r } else { 0.0 };
        strategy[a_idx] = v;
        total += v;
    }
    if total > 0.0 {
        let inv = 1.0 / total;
        for a_idx in 0..num_actions {
            strategy[a_idx] *= inv;
        }
    } else {
        let uniform = 1.0 / (num_actions as f64);
        for a_idx in 0..num_actions {
            strategy[a_idx] = uniform;
        }
    }
    strategy
}

/// Compute terminal node value (shared by serial and parallel paths).
#[inline]
fn terminal_value_read(
    node_pots: &[f64],
    equity_tables: &[f64],
    num_ip: usize,
    num_oop: usize,
    num_river_cards: usize,
    node_id: usize,
    node_type: i32,
    ip_combo_idx: usize,
    oop_combo_idx: usize,
    traversing_player: i32,
    active_turn_idx: usize,
    active_river_idx: usize,
) -> f64 {
    let pot = node_pots[node_id];

    match node_type {
        1 => {
            if traversing_player == 0 { -pot / 2.0 } else { pot / 2.0 }
        }
        2 => {
            if traversing_player == 0 { pot / 2.0 } else { -pot / 2.0 }
        }
        _ => {
            let nr1 = num_river_cards + 1;
            let equity_key = active_turn_idx * nr1 + active_river_idx;
            let table_size = num_ip * num_oop;
            let offset = equity_key * table_size + ip_combo_idx * num_oop + oop_combo_idx;
            let equity = if offset < equity_tables.len() {
                equity_tables[offset]
            } else {
                0.5
            };
            let ip_ev = equity * pot - pot / 2.0;
            if traversing_player == 0 { ip_ev } else { -ip_ev }
        }
    }
}

// ── Chance node helpers (serial) ──

fn turn_chance_value_serial(
    ctx: &mut CfrContext,
    node_id: usize,
    ip_combo_idx: usize,
    oop_combo_idx: usize,
    ip_reach: f64,
    oop_reach: f64,
    traversing_player: i32,
    _active_turn_idx: usize,
    _active_river_idx: usize,
) -> f64 {
    let num_branches = ctx.node_num_actions[node_id] as usize;
    let first_child = ctx.node_first_child[node_id] as usize;
    if num_branches == 0 { return 0.0; }

    let ip0 = ctx.ip_hole_cards_abs[ip_combo_idx * 2];
    let ip1 = ctx.ip_hole_cards_abs[ip_combo_idx * 2 + 1];
    let oop0 = ctx.oop_hole_cards_abs[oop_combo_idx * 2];
    let oop1 = ctx.oop_hole_cards_abs[oop_combo_idx * 2 + 1];

    let mut total_value = 0.0f64;
    let mut valid_count = 0u32;

    for b_idx in 0..num_branches {
        let child_id = ctx.children_ids[first_child + b_idx] as usize;
        let card_abs = ctx.node_chance_card_abs[child_id];
        let eq_idx = ctx.node_chance_equity_idx[child_id];
        if card_abs < 0 || eq_idx < 0 { continue; }
        if card_abs == ip0 || card_abs == ip1 || card_abs == oop0 || card_abs == oop1 { continue; }

        let new_turn_idx = (eq_idx as usize) + 1;
        let child_val = cfr_traverse(ctx, child_id, ip_combo_idx, oop_combo_idx,
                                      ip_reach, oop_reach, traversing_player,
                                      new_turn_idx, 0);
        total_value += child_val;
        valid_count += 1;
    }

    if valid_count == 0 { 0.0 } else { total_value / (valid_count as f64) }
}

fn river_chance_value_serial(
    ctx: &mut CfrContext,
    node_id: usize,
    ip_combo_idx: usize,
    oop_combo_idx: usize,
    ip_reach: f64,
    oop_reach: f64,
    traversing_player: i32,
    active_turn_idx: usize,
) -> f64 {
    let num_branches = ctx.node_num_actions[node_id] as usize;
    let first_child = ctx.node_first_child[node_id] as usize;
    if num_branches == 0 { return 0.0; }

    let ip0 = ctx.ip_hole_cards_abs[ip_combo_idx * 2];
    let ip1 = ctx.ip_hole_cards_abs[ip_combo_idx * 2 + 1];
    let oop0 = ctx.oop_hole_cards_abs[oop_combo_idx * 2];
    let oop1 = ctx.oop_hole_cards_abs[oop_combo_idx * 2 + 1];

    let turn_card_abs = if active_turn_idx > 0 && active_turn_idx < ctx.turn_idx_to_abs.len() {
        ctx.turn_idx_to_abs[active_turn_idx]
    } else {
        -1
    };

    let mut total_value = 0.0f64;
    let mut valid_count = 0u32;

    for b_idx in 0..num_branches {
        let child_id = ctx.children_ids[first_child + b_idx] as usize;
        let card_abs = ctx.node_chance_card_abs[child_id];
        let eq_idx = ctx.node_chance_equity_idx[child_id];
        if card_abs < 0 || eq_idx < 0 { continue; }
        if card_abs == ip0 || card_abs == ip1 || card_abs == oop0 || card_abs == oop1 { continue; }
        if card_abs == turn_card_abs { continue; }

        let new_river_idx = (eq_idx as usize) + 1;
        let child_val = cfr_traverse(ctx, child_id, ip_combo_idx, oop_combo_idx,
                                      ip_reach, oop_reach, traversing_player,
                                      active_turn_idx, new_river_idx);
        total_value += child_val;
        valid_count += 1;
    }

    if valid_count == 0 { 0.0 } else { total_value / (valid_count as f64) }
}

// ── Chance node helpers (parallel delta) ──

fn turn_chance_value_delta(
    ctx: &CfrReadContext,
    regret_deltas: &mut [f64],
    strategy_deltas: &mut [f64],
    node_id: usize,
    ip_combo_idx: usize,
    oop_combo_idx: usize,
    ip_reach: f64,
    oop_reach: f64,
    traversing_player: i32,
    _active_turn_idx: usize,
    _active_river_idx: usize,
) -> f64 {
    let num_branches = ctx.node_num_actions[node_id] as usize;
    let first_child = ctx.node_first_child[node_id] as usize;
    if num_branches == 0 { return 0.0; }

    let ip0 = ctx.ip_hole_cards_abs[ip_combo_idx * 2];
    let ip1 = ctx.ip_hole_cards_abs[ip_combo_idx * 2 + 1];
    let oop0 = ctx.oop_hole_cards_abs[oop_combo_idx * 2];
    let oop1 = ctx.oop_hole_cards_abs[oop_combo_idx * 2 + 1];

    let mut total_value = 0.0f64;
    let mut valid_count = 0u32;

    for b_idx in 0..num_branches {
        let child_id = ctx.children_ids[first_child + b_idx] as usize;
        let card_abs = ctx.node_chance_card_abs[child_id];
        let eq_idx = ctx.node_chance_equity_idx[child_id];
        if card_abs < 0 || eq_idx < 0 { continue; }
        if card_abs == ip0 || card_abs == ip1 || card_abs == oop0 || card_abs == oop1 { continue; }

        let new_turn_idx = (eq_idx as usize) + 1;
        let child_val = cfr_traverse_delta(ctx, regret_deltas, strategy_deltas,
                                            child_id, ip_combo_idx, oop_combo_idx,
                                            ip_reach, oop_reach, traversing_player,
                                            new_turn_idx, 0);
        total_value += child_val;
        valid_count += 1;
    }

    if valid_count == 0 { 0.0 } else { total_value / (valid_count as f64) }
}

fn river_chance_value_delta(
    ctx: &CfrReadContext,
    regret_deltas: &mut [f64],
    strategy_deltas: &mut [f64],
    node_id: usize,
    ip_combo_idx: usize,
    oop_combo_idx: usize,
    ip_reach: f64,
    oop_reach: f64,
    traversing_player: i32,
    active_turn_idx: usize,
) -> f64 {
    let num_branches = ctx.node_num_actions[node_id] as usize;
    let first_child = ctx.node_first_child[node_id] as usize;
    if num_branches == 0 { return 0.0; }

    let ip0 = ctx.ip_hole_cards_abs[ip_combo_idx * 2];
    let ip1 = ctx.ip_hole_cards_abs[ip_combo_idx * 2 + 1];
    let oop0 = ctx.oop_hole_cards_abs[oop_combo_idx * 2];
    let oop1 = ctx.oop_hole_cards_abs[oop_combo_idx * 2 + 1];

    let turn_card_abs = if active_turn_idx > 0 && active_turn_idx < ctx.turn_idx_to_abs.len() {
        ctx.turn_idx_to_abs[active_turn_idx]
    } else {
        -1
    };

    let mut total_value = 0.0f64;
    let mut valid_count = 0u32;

    for b_idx in 0..num_branches {
        let child_id = ctx.children_ids[first_child + b_idx] as usize;
        let card_abs = ctx.node_chance_card_abs[child_id];
        let eq_idx = ctx.node_chance_equity_idx[child_id];
        if card_abs < 0 || eq_idx < 0 { continue; }
        if card_abs == ip0 || card_abs == ip1 || card_abs == oop0 || card_abs == oop1 { continue; }
        if card_abs == turn_card_abs { continue; }

        let new_river_idx = (eq_idx as usize) + 1;
        let child_val = cfr_traverse_delta(ctx, regret_deltas, strategy_deltas,
                                            child_id, ip_combo_idx, oop_combo_idx,
                                            ip_reach, oop_reach, traversing_player,
                                            active_turn_idx, new_river_idx);
        total_value += child_val;
        valid_count += 1;
    }

    if valid_count == 0 { 0.0 } else { total_value / (valid_count as f64) }
}

// ══════════════════════════════════════════════════════════════════
//  PUBLIC ENTRY POINTS
// ══════════════════════════════════════════════════════════════════

/// Serial CFR+ iteration loop (Phase 13D compatible, sequential update).
pub fn cfr_iterate(
    node_types: &[i32],
    node_players: &[i32],
    node_pots: &[f64],
    node_num_actions: &[i32],
    node_first_child: &[i32],
    children_ids: &[i32],
    node_chance_card_abs: &[i32],
    node_chance_equity_idx: &[i32],
    ip_hole_cards_abs: &[i32],
    oop_hole_cards_abs: &[i32],
    turn_idx_to_abs: &[i32],
    num_turn_cards: usize,
    num_river_cards: usize,
    info_map: &[i32],
    max_combos: usize,
    regrets: &mut [f64],
    strategy_sums: &mut [f64],
    max_actions: usize,
    equity_tables: &[f64],
    num_ip: usize,
    num_oop: usize,
    matchup_ip: &[i32],
    matchup_oop: &[i32],
    num_iterations: usize,
    root_node_id: usize,
) -> f64 {
    let num_matchups = matchup_ip.len();

    let mut ctx = CfrContext {
        node_types, node_players, node_pots, node_num_actions,
        node_first_child, children_ids,
        node_chance_card_abs, node_chance_equity_idx,
        ip_hole_cards_abs, oop_hole_cards_abs,
        turn_idx_to_abs, num_turn_cards, num_river_cards,
        info_map, max_combos,
        regrets, strategy_sums, max_actions,
        equity_tables, num_ip, num_oop,
    };

    for _iter in 0..num_iterations {
        for m in 0..num_matchups {
            let ip_idx = matchup_ip[m] as usize;
            let oop_idx = matchup_oop[m] as usize;
            cfr_traverse(&mut ctx, root_node_id, ip_idx, oop_idx, 1.0, 1.0, 0, 0, 0);
            cfr_traverse(&mut ctx, root_node_id, ip_idx, oop_idx, 1.0, 1.0, 1, 0, 0);
        }
    }

    compute_convergence(ctx.regrets, num_iterations)
}

/// Phase 15B: Serial CFR+ with progress reporting and cooperative cancellation.
///
/// Control array (i32, length >= 2):
///   control[0] = iterations_completed (Rust WRITES after each iteration)
///   control[1] = cancel_flag (Python WRITES 1 to request cancellation, Rust READS)
///
/// Returns: (convergence_metric, actual_iterations_completed)
///
/// Cancellation semantics:
///   - Checked BETWEEN iterations only (not mid-traversal)
///   - If cancelled, regrets/strategy arrays reflect all COMPLETED iterations
///   - No partial iteration corruption is possible
///   - Convergence metric computed over actual completed iterations
pub fn cfr_iterate_with_control(
    node_types: &[i32],
    node_players: &[i32],
    node_pots: &[f64],
    node_num_actions: &[i32],
    node_first_child: &[i32],
    children_ids: &[i32],
    node_chance_card_abs: &[i32],
    node_chance_equity_idx: &[i32],
    ip_hole_cards_abs: &[i32],
    oop_hole_cards_abs: &[i32],
    turn_idx_to_abs: &[i32],
    num_turn_cards: usize,
    num_river_cards: usize,
    info_map: &[i32],
    max_combos: usize,
    regrets: &mut [f64],
    strategy_sums: &mut [f64],
    max_actions: usize,
    equity_tables: &[f64],
    num_ip: usize,
    num_oop: usize,
    matchup_ip: &[i32],
    matchup_oop: &[i32],
    num_iterations: usize,
    root_node_id: usize,
    control: &mut [i32],  // [iterations_done, cancel_flag]
) -> (f64, usize) {
    let num_matchups = matchup_ip.len();

    let mut ctx = CfrContext {
        node_types, node_players, node_pots, node_num_actions,
        node_first_child, children_ids,
        node_chance_card_abs, node_chance_equity_idx,
        ip_hole_cards_abs, oop_hole_cards_abs,
        turn_idx_to_abs, num_turn_cards, num_river_cards,
        info_map, max_combos,
        regrets, strategy_sums, max_actions,
        equity_tables, num_ip, num_oop,
    };

    let mut completed = 0usize;

    for _iter in 0..num_iterations {
        // Check cancel flag BETWEEN iterations (cooperative cancellation)
        if control.len() > 1 && control[1] != 0 {
            break;
        }

        for m in 0..num_matchups {
            let ip_idx = matchup_ip[m] as usize;
            let oop_idx = matchup_oop[m] as usize;
            cfr_traverse(&mut ctx, root_node_id, ip_idx, oop_idx, 1.0, 1.0, 0, 0, 0);
            cfr_traverse(&mut ctx, root_node_id, ip_idx, oop_idx, 1.0, 1.0, 1, 0, 0);
        }

        completed += 1;
        // Write progress: iterations completed so far
        if !control.is_empty() {
            control[0] = completed as i32;
        }
    }

    let convergence = compute_convergence(ctx.regrets, completed.max(1));
    (convergence, completed)
}

/// Phase 14: Parallel CFR+ iteration loop (simultaneous update via Rayon).
///
/// Architecture:
///   1. For each iteration:
///      a. Freeze current regrets as read-only snapshot
///      b. Rayon `fold + reduce` across matchups → thread-local delta buffers
///      c. Apply merged deltas: regrets += delta, floor at 0; strategy_sums += delta
///   2. Return convergence metric
///
/// This produces slightly different intermediate values vs serial (sequential update)
/// because all matchups in one iteration use the same regret snapshot. Both variants
/// converge to the same Nash equilibrium.
pub fn cfr_iterate_parallel(
    node_types: &[i32],
    node_players: &[i32],
    node_pots: &[f64],
    node_num_actions: &[i32],
    node_first_child: &[i32],
    children_ids: &[i32],
    node_chance_card_abs: &[i32],
    node_chance_equity_idx: &[i32],
    ip_hole_cards_abs: &[i32],
    oop_hole_cards_abs: &[i32],
    turn_idx_to_abs: &[i32],
    num_turn_cards: usize,
    num_river_cards: usize,
    info_map: &[i32],
    max_combos: usize,
    regrets: &mut [f64],
    strategy_sums: &mut [f64],
    max_actions: usize,
    equity_tables: &[f64],
    num_ip: usize,
    num_oop: usize,
    matchup_ip: &[i32],
    matchup_oop: &[i32],
    num_iterations: usize,
    root_node_id: usize,
) -> f64 {
    let num_matchups = matchup_ip.len();
    let regret_size = regrets.len();
    let strategy_size = strategy_sums.len();

    for _iter in 0..num_iterations {
        // Build read-only context from current regret snapshot
        let ctx = CfrReadContext {
            node_types, node_players, node_pots, node_num_actions,
            node_first_child, children_ids,
            node_chance_card_abs, node_chance_equity_idx,
            ip_hole_cards_abs, oop_hole_cards_abs,
            turn_idx_to_abs, num_turn_cards, num_river_cards,
            info_map, max_combos,
            regrets: &*regrets,  // immutable borrow of current snapshot
            max_actions,
            equity_tables, num_ip, num_oop,
        };

        // Parallel fold+reduce: each thread partition gets local delta buffers
        let (regret_deltas, strategy_deltas) = (0..num_matchups)
            .into_par_iter()
            .fold(
                || (vec![0.0f64; regret_size], vec![0.0f64; strategy_size]),
                |mut acc, m| {
                    let ip_idx = matchup_ip[m] as usize;
                    let oop_idx = matchup_oop[m] as usize;

                    // IP traversal
                    cfr_traverse_delta(
                        &ctx, &mut acc.0, &mut acc.1,
                        root_node_id, ip_idx, oop_idx,
                        1.0, 1.0, 0, 0, 0,
                    );
                    // OOP traversal
                    cfr_traverse_delta(
                        &ctx, &mut acc.0, &mut acc.1,
                        root_node_id, ip_idx, oop_idx,
                        1.0, 1.0, 1, 0, 0,
                    );

                    acc
                },
            )
            .reduce(
                || (vec![0.0f64; regret_size], vec![0.0f64; strategy_size]),
                |(mut ra, mut sa), (rb, sb)| {
                    for i in 0..ra.len() { ra[i] += rb[i]; }
                    for i in 0..sa.len() { sa[i] += sb[i]; }
                    (ra, sa)
                },
            );

        // Apply merged deltas to global arrays
        for i in 0..regret_size {
            let new_r = regrets[i] + regret_deltas[i];
            regrets[i] = if new_r > 0.0 { new_r } else { 0.0 };
        }
        for i in 0..strategy_size {
            strategy_sums[i] += strategy_deltas[i];
        }
    }

    compute_convergence(regrets, num_iterations)
}

/// Shared convergence metric computation.
fn compute_convergence(regrets: &[f64], num_iterations: usize) -> f64 {
    let mut total_regret = 0.0f64;
    let mut count = 0usize;
    for &r in regrets.iter() {
        if r > 0.0 {
            total_regret += r;
            count += 1;
        }
    }
    if count == 0 {
        0.0
    } else {
        total_regret / (count as f64) / (num_iterations as f64).max(1.0)
    }
}

// ══════════════════════════════════════════════════════════════════
//  TESTS
// ══════════════════════════════════════════════════════════════════

#[cfg(test)]
mod tests {
    use super::*;

    // Helper to build a minimal test tree
    fn make_minimal_tree() -> (
        Vec<i32>, Vec<i32>, Vec<f64>, Vec<i32>, Vec<i32>, Vec<i32>,
        Vec<i32>, Vec<i32>, Vec<i32>, Vec<i32>, Vec<i32>,
    ) {
        (
            vec![0, 3, 2],        // node_types
            vec![1, 0, 0],        // node_players
            vec![10.0, 10.0, 20.0], // node_pots
            vec![2, 0, 0],        // node_num_actions
            vec![0, 0, 0],        // node_first_child
            vec![1, 2],           // children_ids
            vec![-1, -1, -1],     // node_chance_card_abs
            vec![-1, -1, -1],     // node_chance_equity_idx
            vec![50, 49],         // ip_hole_cards_abs (Ah, Ad)
            vec![46, 45],         // oop_hole_cards_abs (Kh, Kd)
            vec![-1],             // turn_idx_to_abs
        )
    }

    #[test]
    fn test_minimal_flop_traversal() {
        let (nt, np, npots, nna, nfc, ci, ncca, ncei, iha, oha, tia) = make_minimal_tree();
        let info_map = vec![0i32, -1, -1];
        let max_actions = 2;
        let mut regrets = vec![0.0; 1 * max_actions];
        let mut strategy_sums = vec![0.0; 1 * max_actions];
        let equity_tables = vec![0.5f64];
        let matchup_ip = vec![0i32];
        let matchup_oop = vec![0i32];

        let convergence = cfr_iterate(
            &nt, &np, &npots, &nna, &nfc, &ci,
            &ncca, &ncei, &iha, &oha, &tia, 0, 0,
            &info_map, 1,
            &mut regrets, &mut strategy_sums, max_actions,
            &equity_tables, 1, 1,
            &matchup_ip, &matchup_oop, 10, 0,
        );

        assert!(convergence >= 0.0);
        assert!(strategy_sums.iter().any(|&s| s > 0.0));
    }

    #[test]
    fn test_parallel_flop_traversal() {
        let (nt, np, npots, nna, nfc, ci, ncca, ncei, iha, oha, tia) = make_minimal_tree();
        let info_map = vec![0i32, -1, -1];
        let max_actions = 2;
        let mut regrets = vec![0.0; 1 * max_actions];
        let mut strategy_sums = vec![0.0; 1 * max_actions];
        let equity_tables = vec![0.5f64];
        let matchup_ip = vec![0i32];
        let matchup_oop = vec![0i32];

        let convergence = cfr_iterate_parallel(
            &nt, &np, &npots, &nna, &nfc, &ci,
            &ncca, &ncei, &iha, &oha, &tia, 0, 0,
            &info_map, 1,
            &mut regrets, &mut strategy_sums, max_actions,
            &equity_tables, 1, 1,
            &matchup_ip, &matchup_oop, 10, 0,
        );

        assert!(convergence >= 0.0);
        assert!(strategy_sums.iter().any(|&s| s > 0.0));
    }

    #[test]
    fn test_parallel_produces_valid_convergence() {
        // Serial and parallel should both produce non-negative convergence
        let (nt, np, npots, nna, nfc, ci, ncca, ncei, iha, oha, tia) = make_minimal_tree();
        let info_map = vec![0i32, -1, -1];
        let max_actions = 2;
        let equity_tables = vec![0.5f64];
        let matchup_ip = vec![0i32];
        let matchup_oop = vec![0i32];

        let mut reg_serial = vec![0.0; 2];
        let mut ss_serial = vec![0.0; 2];
        let conv_serial = cfr_iterate(
            &nt, &np, &npots, &nna, &nfc, &ci,
            &ncca, &ncei, &iha, &oha, &tia, 0, 0,
            &info_map, 1,
            &mut reg_serial, &mut ss_serial, max_actions,
            &equity_tables, 1, 1,
            &matchup_ip, &matchup_oop, 20, 0,
        );

        let mut reg_parallel = vec![0.0; 2];
        let mut ss_parallel = vec![0.0; 2];
        let conv_parallel = cfr_iterate_parallel(
            &nt, &np, &npots, &nna, &nfc, &ci,
            &ncca, &ncei, &iha, &oha, &tia, 0, 0,
            &info_map, 1,
            &mut reg_parallel, &mut ss_parallel, max_actions,
            &equity_tables, 1, 1,
            &matchup_ip, &matchup_oop, 20, 0,
        );

        assert!(conv_serial >= 0.0);
        assert!(conv_parallel >= 0.0);
        // Both should accumulate strategy sums
        assert!(ss_serial.iter().sum::<f64>() > 0.0);
        assert!(ss_parallel.iter().sum::<f64>() > 0.0);
    }

    #[test]
    fn test_turn_chance_traversal() {
        let node_types = vec![0, 4, 2, 0, 3, 0, 3];
        let node_players = vec![1, 0, 0, 1, 0, 1, 0];
        let node_pots = vec![10.0, 10.0, 20.0, 10.0, 10.0, 10.0, 10.0];
        let node_num_actions = vec![2, 2, 0, 1, 0, 1, 0];
        let node_first_child = vec![0, 2, 0, 4, 0, 5, 0];
        let children_ids = vec![1, 2, 3, 5, 4, 6];
        let node_chance_card_abs = vec![-1, -1, -1, 20, -1, 24, -1];
        let node_chance_equity_idx = vec![-1, -1, -1, 0, -1, 1, -1];
        let ip_hole_cards_abs = vec![50, 49];
        let oop_hole_cards_abs = vec![46, 45];
        let turn_idx_to_abs = vec![-1, 20, 24];
        let info_map = vec![0, -1, -1, 1, -1, 2, -1];
        let max_actions = 2;
        let mut regrets = vec![0.0; 3 * max_actions];
        let mut strategy_sums = vec![0.0; 3 * max_actions];
        let equity_tables = vec![0.5, 0.7, 0.3];
        let matchup_ip = vec![0i32];
        let matchup_oop = vec![0i32];

        let convergence = cfr_iterate(
            &node_types, &node_players, &node_pots, &node_num_actions,
            &node_first_child, &children_ids,
            &node_chance_card_abs, &node_chance_equity_idx,
            &ip_hole_cards_abs, &oop_hole_cards_abs,
            &turn_idx_to_abs, 2, 0,
            &info_map, 1,
            &mut regrets, &mut strategy_sums, max_actions,
            &equity_tables, 1, 1,
            &matchup_ip, &matchup_oop, 20, 0,
        );

        assert!(convergence >= 0.0);
        assert!(strategy_sums.iter().sum::<f64>() > 0.0);
    }

    #[test]
    fn test_river_chance_traversal() {
        let node_types = vec![0, 4, 2, 0, 5, 0, 3, 0, 3];
        let node_players = vec![1, 0, 0, 1, 0, 1, 0, 1, 0];
        let node_pots = vec![10.0, 10.0, 20.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0];
        let node_num_actions = vec![2, 1, 0, 1, 2, 1, 0, 1, 0];
        let node_first_child = vec![0, 2, 0, 3, 4, 6, 0, 7, 0];
        let children_ids = vec![1, 2, 3, 4, 5, 7, 6, 8];
        let node_chance_card_abs = vec![-1, -1, -1, 20, -1, 28, -1, 32, -1];
        let node_chance_equity_idx = vec![-1, -1, -1, 0, -1, 0, -1, 1, -1];
        let ip_hole_cards_abs = vec![50, 49];
        let oop_hole_cards_abs = vec![46, 45];
        let turn_idx_to_abs = vec![-1, 20];
        let info_map = vec![0, -1, -1, 1, -1, 2, -1, 3, -1];
        let max_actions = 2;
        let mut regrets = vec![0.0; 4 * max_actions];
        let mut strategy_sums = vec![0.0; 4 * max_actions];
        let equity_tables = vec![0.5, 0.5, 0.5, 0.5, 0.8, 0.2];
        let matchup_ip = vec![0i32];
        let matchup_oop = vec![0i32];

        let convergence = cfr_iterate(
            &node_types, &node_players, &node_pots, &node_num_actions,
            &node_first_child, &children_ids,
            &node_chance_card_abs, &node_chance_equity_idx,
            &ip_hole_cards_abs, &oop_hole_cards_abs,
            &turn_idx_to_abs, 1, 2,
            &info_map, 1,
            &mut regrets, &mut strategy_sums, max_actions,
            &equity_tables, 1, 1,
            &matchup_ip, &matchup_oop, 20, 0,
        );

        assert!(convergence >= 0.0);
        assert!(strategy_sums.iter().sum::<f64>() > 0.0);
    }

    #[test]
    fn test_river_blocker_skips_turn_card() {
        let node_types = vec![0, 4, 2, 0, 5, 0, 3, 0, 3];
        let node_players = vec![1, 0, 0, 1, 0, 1, 0, 1, 0];
        let node_pots = vec![10.0, 10.0, 20.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0];
        let node_num_actions = vec![2, 1, 0, 1, 2, 1, 0, 1, 0];
        let node_first_child = vec![0, 2, 0, 3, 4, 6, 0, 7, 0];
        let children_ids = vec![1, 2, 3, 4, 5, 7, 6, 8];
        let node_chance_card_abs = vec![-1, -1, -1, 20, -1, 20, -1, 32, -1]; // node 5 blocked
        let node_chance_equity_idx = vec![-1, -1, -1, 0, -1, 0, -1, 1, -1];
        let ip_hole_cards_abs = vec![50, 49];
        let oop_hole_cards_abs = vec![46, 45];
        let turn_idx_to_abs = vec![-1, 20];
        let info_map = vec![0, -1, -1, 1, -1, 2, -1, 3, -1];
        let max_actions = 2;
        let mut regrets = vec![0.0; 4 * max_actions];
        let mut strategy_sums = vec![0.0; 4 * max_actions];
        let equity_tables = vec![0.5, 0.5, 0.5, 0.5, 0.8, 0.2];
        let matchup_ip = vec![0i32];
        let matchup_oop = vec![0i32];

        cfr_iterate(
            &node_types, &node_players, &node_pots, &node_num_actions,
            &node_first_child, &children_ids,
            &node_chance_card_abs, &node_chance_equity_idx,
            &ip_hole_cards_abs, &oop_hole_cards_abs,
            &turn_idx_to_abs, 1, 2,
            &info_map, 1,
            &mut regrets, &mut strategy_sums, max_actions,
            &equity_tables, 1, 1,
            &matchup_ip, &matchup_oop, 20, 0,
        );

        assert_eq!(strategy_sums[4], 0.0, "Blocked river branch should not accumulate");
        assert_eq!(strategy_sums[5], 0.0, "Blocked river branch should not accumulate");
        assert!(strategy_sums[6] > 0.0 || strategy_sums[7] > 0.0,
                "Non-blocked river branch should accumulate");
    }

    #[test]
    fn test_parallel_turn_chance_traversal() {
        let node_types = vec![0, 4, 2, 0, 3, 0, 3];
        let node_players = vec![1, 0, 0, 1, 0, 1, 0];
        let node_pots = vec![10.0, 10.0, 20.0, 10.0, 10.0, 10.0, 10.0];
        let node_num_actions = vec![2, 2, 0, 1, 0, 1, 0];
        let node_first_child = vec![0, 2, 0, 4, 0, 5, 0];
        let children_ids = vec![1, 2, 3, 5, 4, 6];
        let node_chance_card_abs = vec![-1, -1, -1, 20, -1, 24, -1];
        let node_chance_equity_idx = vec![-1, -1, -1, 0, -1, 1, -1];
        let ip_hole_cards_abs = vec![50, 49];
        let oop_hole_cards_abs = vec![46, 45];
        let turn_idx_to_abs = vec![-1, 20, 24];
        let info_map = vec![0, -1, -1, 1, -1, 2, -1];
        let max_actions = 2;
        let mut regrets = vec![0.0; 3 * max_actions];
        let mut strategy_sums = vec![0.0; 3 * max_actions];
        let equity_tables = vec![0.5, 0.7, 0.3];
        let matchup_ip = vec![0i32];
        let matchup_oop = vec![0i32];

        let convergence = cfr_iterate_parallel(
            &node_types, &node_players, &node_pots, &node_num_actions,
            &node_first_child, &children_ids,
            &node_chance_card_abs, &node_chance_equity_idx,
            &ip_hole_cards_abs, &oop_hole_cards_abs,
            &turn_idx_to_abs, 2, 0,
            &info_map, 1,
            &mut regrets, &mut strategy_sums, max_actions,
            &equity_tables, 1, 1,
            &matchup_ip, &matchup_oop, 20, 0,
        );

        assert!(convergence >= 0.0);
        assert!(strategy_sums.iter().sum::<f64>() > 0.0);
    }

    #[test]
    fn test_parallel_river_chance_traversal() {
        let node_types = vec![0, 4, 2, 0, 5, 0, 3, 0, 3];
        let node_players = vec![1, 0, 0, 1, 0, 1, 0, 1, 0];
        let node_pots = vec![10.0, 10.0, 20.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0];
        let node_num_actions = vec![2, 1, 0, 1, 2, 1, 0, 1, 0];
        let node_first_child = vec![0, 2, 0, 3, 4, 6, 0, 7, 0];
        let children_ids = vec![1, 2, 3, 4, 5, 7, 6, 8];
        let node_chance_card_abs = vec![-1, -1, -1, 20, -1, 28, -1, 32, -1];
        let node_chance_equity_idx = vec![-1, -1, -1, 0, -1, 0, -1, 1, -1];
        let ip_hole_cards_abs = vec![50, 49];
        let oop_hole_cards_abs = vec![46, 45];
        let turn_idx_to_abs = vec![-1, 20];
        let info_map = vec![0, -1, -1, 1, -1, 2, -1, 3, -1];
        let max_actions = 2;
        let mut regrets = vec![0.0; 4 * max_actions];
        let mut strategy_sums = vec![0.0; 4 * max_actions];
        let equity_tables = vec![0.5, 0.5, 0.5, 0.5, 0.8, 0.2];
        let matchup_ip = vec![0i32];
        let matchup_oop = vec![0i32];

        let convergence = cfr_iterate_parallel(
            &node_types, &node_players, &node_pots, &node_num_actions,
            &node_first_child, &children_ids,
            &node_chance_card_abs, &node_chance_equity_idx,
            &ip_hole_cards_abs, &oop_hole_cards_abs,
            &turn_idx_to_abs, 1, 2,
            &info_map, 1,
            &mut regrets, &mut strategy_sums, max_actions,
            &equity_tables, 1, 1,
            &matchup_ip, &matchup_oop, 20, 0,
        );

        assert!(convergence >= 0.0);
        assert!(strategy_sums.iter().sum::<f64>() > 0.0);
    }
}
