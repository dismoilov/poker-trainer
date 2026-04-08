"""
Tests for the range parser module.
"""

import pytest
from app.poker_engine.ranges import (
    parse_range, validate_range, ParsedRange,
    RANK_CHARS, ALL_HANDS, ALL_HANDS_SET,
)


class TestSingleHands:
    def test_pair(self):
        r = parse_range("AA")
        assert r.count == 1
        assert "AA" in r.hands
        assert r.combos == 6

    def test_suited(self):
        r = parse_range("AKs")
        assert r.count == 1
        assert "AKs" in r.hands
        assert r.combos == 4

    def test_offsuit(self):
        r = parse_range("AKo")
        assert r.count == 1
        assert "AKo" in r.hands
        assert r.combos == 12

    def test_no_suit_means_both(self):
        r = parse_range("AK")
        assert r.count == 2
        assert "AKs" in r.hands
        assert "AKo" in r.hands
        assert r.combos == 16

    def test_multiple_singles(self):
        r = parse_range("AA,KK,QQ")
        assert r.count == 3
        assert r.combos == 18


class TestPlusNotation:
    def test_pair_plus(self):
        r = parse_range("TT+")
        assert "TT" in r.hands
        assert "JJ" in r.hands
        assert "QQ" in r.hands
        assert "KK" in r.hands
        assert "AA" in r.hands
        assert r.count == 5
        assert r.combos == 30

    def test_aa_plus(self):
        r = parse_range("AA+")
        assert r.count == 1
        assert "AA" in r.hands

    def test_suited_plus(self):
        r = parse_range("ATs+")
        assert "ATs" in r.hands
        assert "AJs" in r.hands
        assert "AQs" in r.hands
        assert "AKs" in r.hands
        assert r.count == 4

    def test_offsuit_plus(self):
        r = parse_range("ATo+")
        assert "ATo" in r.hands
        assert "AJo" in r.hands
        assert "AQo" in r.hands
        assert "AKo" in r.hands
        assert r.count == 4


class TestDashNotation:
    def test_pair_dash(self):
        r = parse_range("TT-77")
        assert "TT" in r.hands
        assert "99" in r.hands
        assert "88" in r.hands
        assert "77" in r.hands
        assert r.count == 4

    def test_suited_dash(self):
        r = parse_range("76s-54s")
        assert "76s" in r.hands
        assert "65s" in r.hands
        assert "54s" in r.hands
        assert r.count == 3


class TestComplexRanges:
    def test_mixed(self):
        r = parse_range("AA,KK,AKs,AQs+,TT-88")
        assert "AA" in r.hands
        assert "KK" in r.hands
        assert "AKs" in r.hands
        assert "AQs" in r.hands
        assert "TT" in r.hands
        assert "99" in r.hands
        assert "88" in r.hands

    def test_whitespace_tolerance(self):
        r = parse_range("AA, KK, QQ")
        assert r.count == 3

    def test_empty_string(self):
        r = parse_range("")
        assert r.count == 0
        assert r.combos == 0

    def test_percentage(self):
        r = parse_range("AA")
        assert 0 < r.pct < 1  # AA is ~0.45% of range


class TestValidation:
    def test_valid(self):
        valid, err = validate_range("AA,KK")
        assert valid
        assert err == ""

    def test_invalid_token(self):
        valid, err = validate_range("XY")
        assert not valid

    def test_empty(self):
        valid, err = validate_range("")
        assert not valid

    def test_contains(self):
        r = parse_range("TT+")
        assert r.contains("AA")
        assert r.contains("TT")
        assert not r.contains("99")

    def test_to_string(self):
        r = parse_range("AA,KK")
        s = r.to_string()
        assert "AA" in s
        assert "KK" in s


class TestAllHands:
    def test_all_hands_count(self):
        """There should be 169 canonical hand labels."""
        assert len(ALL_HANDS) == 169

    def test_pair_count(self):
        pairs = [h for h in ALL_HANDS if len(h) == 2]
        assert len(pairs) == 13

    def test_suited_count(self):
        suited = [h for h in ALL_HANDS if h.endswith('s')]
        assert len(suited) == 78

    def test_offsuit_count(self):
        offsuit = [h for h in ALL_HANDS if h.endswith('o')]
        assert len(offsuit) == 78
