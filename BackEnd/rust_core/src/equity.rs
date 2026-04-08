/// Batch showdown equity engine — Phase 13A.
///
/// Computes showdown equity for multiple matchups in a single call,
/// avoiding Python↔Rust round-trip overhead per matchup.

use crate::hand_eval::evaluate_best;

/// Compute IP equity for a single matchup.
/// Returns 1.0 (IP win), 0.0 (OOP win), or 0.5 (tie).
#[inline]
pub fn compute_equity(
    ip_hole: (u8, u8),
    oop_hole: (u8, u8),
    board: &[u8],
) -> f64 {
    // Build 7-card hands (or 5/6 for flop/turn)
    let n = 2 + board.len();
    let mut ip_cards = Vec::with_capacity(n);
    ip_cards.push(ip_hole.0);
    ip_cards.push(ip_hole.1);
    ip_cards.extend_from_slice(board);

    let mut oop_cards = Vec::with_capacity(n);
    oop_cards.push(oop_hole.0);
    oop_cards.push(oop_hole.1);
    oop_cards.extend_from_slice(board);

    let ip_rank = evaluate_best(&ip_cards);
    let oop_rank = evaluate_best(&oop_cards);

    if ip_rank > oop_rank {
        1.0
    } else if ip_rank < oop_rank {
        0.0
    } else {
        0.5
    }
}

/// Batch compute equity for multiple matchups on the same board.
///
/// Arguments:
///   ip_hands:  Vec of (card1, card2) for IP hands
///   oop_hands: Vec of (card1, card2) for OOP hands
///   board:     Board cards (3-5 cards)
///   matchups:  Vec of (ip_idx, oop_idx) pairs
///
/// Returns: Vec<f64> with equity for each matchup (same order as matchups)
pub fn batch_equity(
    ip_hands: &[(u8, u8)],
    oop_hands: &[(u8, u8)],
    board: &[u8],
    matchups: &[(usize, usize)],
) -> Vec<f64> {
    let mut results = Vec::with_capacity(matchups.len());

    for &(ip_idx, oop_idx) in matchups {
        let ip_hole = ip_hands[ip_idx];
        let oop_hole = oop_hands[oop_idx];
        results.push(compute_equity(ip_hole, oop_hole, board));
    }

    results
}

/// Batch compute equity for matchups across multiple boards.
/// Used for turn/river precomputation where each board variant gets its own set.
///
/// Arguments:
///   ip_hands:  Vec of (card1, card2) for IP hands
///   oop_hands: Vec of (card1, card2) for OOP hands
///   boards:    Vec of board variants (each is a Vec<u8> of 3-5 cards)
///   matchups_per_board: For each board, a Vec of (ip_idx, oop_idx) pairs
///
/// Returns: Vec<(board_idx, ip_idx, oop_idx, equity)>
pub fn batch_equity_multi_board(
    ip_hands: &[(u8, u8)],
    oop_hands: &[(u8, u8)],
    boards: &[Vec<u8>],
    matchups_per_board: &[Vec<(usize, usize)>],
) -> Vec<(usize, usize, usize, f64)> {
    let total: usize = matchups_per_board.iter().map(|m| m.len()).sum();
    let mut results = Vec::with_capacity(total);

    for (board_idx, (board, matchups)) in boards.iter().zip(matchups_per_board.iter()).enumerate() {
        for &(ip_idx, oop_idx) in matchups {
            let equity = compute_equity(ip_hands[ip_idx], oop_hands[oop_idx], board);
            results.push((board_idx, ip_idx, oop_idx, equity));
        }
    }

    results
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_card(rank: u8, suit: u8) -> u8 {
        rank * 4 + suit
    }

    #[test]
    fn test_single_equity_aa_vs_kk() {
        let ip = (make_card(12, 2), make_card(12, 1));  // Ah Ad
        let oop = (make_card(11, 2), make_card(11, 1)); // Kh Kd
        let board = vec![
            make_card(7, 3),  // 9s
            make_card(5, 1),  // 7d
            make_card(0, 0),  // 2c
        ];
        let equity = compute_equity(ip, oop, &board);
        assert!((equity - 1.0).abs() < 0.01, "AA should beat KK");
    }

    #[test]
    fn test_single_equity_tie() {
        let ip = (make_card(12, 2), make_card(12, 1));  // Ah Ad
        let oop = (make_card(12, 0), make_card(12, 3)); // Ac As
        let board = vec![
            make_card(7, 3),  // 9s
            make_card(5, 1),  // 7d
            make_card(0, 0),  // 2c
        ];
        let equity = compute_equity(ip, oop, &board);
        assert!((equity - 0.5).abs() < 0.01, "AA vs AA should tie");
    }

    #[test]
    fn test_batch() {
        let ip_hands = vec![
            (make_card(12, 2), make_card(12, 1)),  // AA
            (make_card(11, 2), make_card(11, 1)),  // KK
        ];
        let oop_hands = vec![
            (make_card(10, 2), make_card(10, 1)),  // QQ
        ];
        let board = vec![
            make_card(7, 3),  // 9s
            make_card(5, 1),  // 7d
            make_card(0, 0),  // 2c
        ];
        let matchups = vec![(0, 0), (1, 0)]; // AA vs QQ, KK vs QQ

        let results = batch_equity(&ip_hands, &oop_hands, &board, &matchups);
        assert_eq!(results.len(), 2);
        assert!((results[0] - 1.0).abs() < 0.01); // AA beats QQ
        assert!((results[1] - 1.0).abs() < 0.01); // KK beats QQ
    }
}
