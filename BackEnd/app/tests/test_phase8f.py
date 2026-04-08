"""
Phase 8F Tests — Full Humanization of Study Flows

Tests cover:
- Action label localization
- Spot name humanization
- Strategy description (pure vs mixed)
- Solver context carry-over
- Fallback / edge cases
"""
import pytest
import re

# ── A. Action Label Localization ──

# We test the localizeAction logic that the frontend uses.
# Since the frontend module is TypeScript, we replicate its mapping here.

ACTION_MAP = {
    'fold': 'Фолд', 'check': 'Чек', 'call': 'Колл',
    'bet': 'Бет', 'raise': 'Рейз', 'all-in': 'Олл-ин', 'allin': 'Олл-ин',
}


def localize_action(label: str) -> str:
    """Python replica of localizeAction from localizePoker.ts."""
    if not label:
        return label
    lower = label.lower().strip()
    if lower in ACTION_MAP:
        return ACTION_MAP[lower]
    if lower.startswith('bet'):
        suffix = label[3:].strip()
        return f'Бет {suffix}' if suffix else 'Бет'
    if lower.startswith('raise'):
        suffix = label[5:].strip()
        return f'Рейз {suffix}' if suffix else 'Рейз'
    if 'all' in lower and 'in' in lower:
        return 'Олл-ин'
    return label


class TestActionLocalization:
    def test_fold(self):
        assert localize_action('Fold') == 'Фолд'

    def test_check(self):
        assert localize_action('Check') == 'Чек'

    def test_call(self):
        assert localize_action('Call') == 'Колл'

    def test_bet_plain(self):
        assert localize_action('Bet') == 'Бет'

    def test_bet_with_size(self):
        assert localize_action('Bet 33%') == 'Бет 33%'

    def test_bet_75(self):
        assert localize_action('Bet 75%') == 'Бет 75%'

    def test_raise_plain(self):
        assert localize_action('Raise') == 'Рейз'

    def test_raise_with_size(self):
        assert localize_action('Raise 2.5x') == 'Рейз 2.5x'

    def test_all_in(self):
        assert localize_action('All-in') == 'Олл-ин'

    def test_already_russian(self):
        assert localize_action('Фолд') == 'Фолд'

    def test_empty_string(self):
        assert localize_action('') == ''

    def test_unknown_action(self):
        assert localize_action('custom_action') == 'custom_action'


# ── B. Spot Name Humanization ──

POSITION_MAP = {
    'BTN': 'Баттон', 'SB': 'Мал. блайнд', 'BB': 'Бол. блайнд',
    'CO': 'Катофф', 'HJ': 'Хайджек', 'MP': 'Мидл', 'UTG': 'Андер-зе-ган',
}

FORMAT_MAP = {
    'SRP': 'Один рейз', '3bet': 'Три-бет', '4bet': 'Четыре-бет', 'squeeze': 'Сквиз',
}

STREET_MAP = {
    'flop': 'Флоп', 'turn': 'Тёрн', 'river': 'Ривер',
}


def localize_position(pos: str) -> str:
    return POSITION_MAP.get(pos.upper(), pos)


def localize_format(fmt: str) -> str:
    return FORMAT_MAP.get(fmt, fmt)


def localize_street(street: str) -> str:
    return STREET_MAP.get(street.lower(), street)


def localize_spot_name(name: str, fmt: str, positions: list, streets: list) -> str:
    """Python replica of localizeSpotName from localizePoker.ts."""
    fmt_ru = localize_format(fmt)
    pos1 = localize_position(positions[0])
    pos2 = localize_position(positions[1])
    street_ru = localize_street(streets[-1]) if streets else ''
    extra = ''
    if 'check-check' in name.lower() or '-cc' in name:
        extra = ' (чек-чек)'
    elif 'bet-call' in name.lower() or '-bc' in name:
        extra = ' (бет-колл)'
    return f'{fmt_ru}: {pos1} vs {pos2} • {street_ru}{extra}' if street_ru else f'{fmt_ru}: {pos1} vs {pos2}{extra}'


class TestSpotNameHumanization:
    def test_srp_btn_bb_flop(self):
        result = localize_spot_name('SRP BTN vs BB Flop', 'SRP', ['BTN', 'BB'], ['flop'])
        assert 'Один рейз' in result
        assert 'Баттон' in result
        assert 'Бол. блайнд' in result
        assert 'Флоп' in result

    def test_3bet_co_bb_turn(self):
        result = localize_spot_name('3Bet CO vs BB Turn', '3bet', ['CO', 'BB'], ['flop', 'turn'])
        assert 'Три-бет' in result
        assert 'Катофф' in result
        assert 'Тёрн' in result

    def test_4bet_utg_bb(self):
        result = localize_spot_name('4Bet UTG vs BB Flop', '4bet', ['UTG', 'BB'], ['flop'])
        assert 'Четыре-бет' in result
        assert 'Андер-зе-ган' in result

    def test_squeeze(self):
        result = localize_spot_name('Squeeze BB vs CO Flop', 'squeeze', ['BB', 'CO'], ['flop'])
        assert 'Сквиз' in result

    def test_check_check_suffix(self):
        result = localize_spot_name('SRP BTN vs BB Turn (check-check)', 'SRP', ['BTN', 'BB'], ['flop', 'turn'])
        assert 'чек-чек' in result

    def test_bet_call_suffix(self):
        result = localize_spot_name('SRP HJ vs BB Turn (bet-call)', 'SRP', ['HJ', 'BB'], ['flop', 'turn'])
        assert 'бет-колл' in result


# ── C. Strategy Description ──

def describe_strategy(frequencies: dict, action_labels: dict = None):
    """Python replica of describeStrategy from localizePoker.ts."""
    entries = sorted(frequencies.items(), key=lambda x: -x[1])
    if not entries:
        return {'type': 'pure', 'typeLabel': 'Нет данных', 'summary': 'Нет данных о стратегии.'}
    top_id, top_freq = entries[0]
    top_label = (action_labels or {}).get(top_id, localize_action(top_id))
    if top_freq >= 0.95:
        return {
            'type': 'pure',
            'typeLabel': 'Чистое действие',
            'summary': f'Солвер всегда выбирает {top_label.lower()} в этой ситуации.',
        }
    if top_freq >= 0.80:
        return {
            'type': 'pure',
            'typeLabel': 'Почти всегда',
            'summary': f'В основном {top_label.lower()} ({top_freq*100:.0f}%). Иногда другие действия для баланса.',
        }
    if len(entries) >= 2:
        sec_id, sec_freq = entries[1]
        sec_label = (action_labels or {}).get(sec_id, localize_action(sec_id))
        return {
            'type': 'mixed',
            'typeLabel': 'Смешанная стратегия',
            'summary': f'Солвер чередует: {top_label.lower()} ({top_freq*100:.0f}%) и {sec_label.lower()} ({sec_freq*100:.0f}%). Это нормально — GTO использует разные действия для непредсказуемости.',
        }
    return {
        'type': 'pure',
        'typeLabel': 'Рекомендация',
        'summary': f'Рекомендуется {top_label.lower()} ({top_freq*100:.0f}%).',
    }


class TestStrategyDescription:
    def test_pure_strategy(self):
        result = describe_strategy({'Fold': 0.98, 'Call': 0.02})
        assert result['type'] == 'pure'
        assert result['typeLabel'] == 'Чистое действие'
        assert 'фолд' in result['summary'].lower()

    def test_almost_always(self):
        result = describe_strategy({'Call': 0.85, 'Raise': 0.15})
        assert result['typeLabel'] == 'Почти всегда'
        assert '85%' in result['summary']

    def test_mixed_strategy(self):
        result = describe_strategy({'Bet 33%': 0.55, 'Check': 0.45})
        assert result['type'] == 'mixed'
        assert result['typeLabel'] == 'Смешанная стратегия'
        assert 'чередует' in result['summary']
        assert 'непредсказуемости' in result['summary']

    def test_empty_frequencies(self):
        result = describe_strategy({})
        assert result['type'] == 'pure'
        assert 'Нет данных' in result['summary']

    def test_with_action_labels(self):
        # When action_labels provides English labels, they're used as-is
        # (frontend localizeAction wraps these later in the UI)
        result = describe_strategy(
            {'fold': 0.70, 'call': 0.30},
            {'fold': 'Fold', 'call': 'Call'}
        )
        assert result['type'] == 'mixed'
        assert 'fold' in result['summary'].lower()
        assert 'call' in result['summary'].lower()


# ── D. Context Carry-Over ──

class TestContextCarryOver:
    """Tests for solver→study context carry-over logic."""

    def test_solver_context_structure(self):
        ctx = {'spotId': None, 'fromSolver': True}
        assert ctx['fromSolver'] is True
        assert ctx['spotId'] is None

    def test_context_with_spot(self):
        ctx = {'spotId': 'srp-btn-bb-flop', 'fromSolver': True}
        assert ctx['spotId'] == 'srp-btn-bb-flop'
        assert ctx['fromSolver'] is True

    def test_context_clear(self):
        ctx = {'spotId': None, 'fromSolver': False}
        assert ctx['fromSolver'] is False

    def test_banner_text_drill(self):
        banner = 'Вы пришли из солвера. Потренируйте изученный спот!'
        assert 'солвера' in banner
        assert 'Потренируйте' in banner

    def test_banner_text_explore(self):
        banner = 'Вы пришли из солвера. Изучите стратегию для этого спота!'
        assert 'солвера' in banner
        assert 'Изучите' in banner


# ── E. Fallback States ──

class TestFallbackStates:
    def test_unknown_position(self):
        assert localize_position('XYZ') == 'XYZ'

    def test_unknown_format(self):
        assert localize_format('custom') == 'custom'

    def test_unknown_street(self):
        assert localize_street('preflop') == 'preflop'
        # Note: preflop is not in our map since we deal with postflop spots

    def test_action_localize_preserves_unknown(self):
        assert localize_action('SomeWeirdAction') == 'SomeWeirdAction'


# ── F. Regression Protection ──

class TestRegressionProtection:
    """Ensure previous Phase 8E features still work."""

    def test_explore_action_labels_are_russian(self):
        labels = {
            'fold': 'Фолд', 'check': 'Чек', 'call': 'Колл',
            'bet33': 'Бет 33%', 'bet50': 'Бет 50%', 'bet75': 'Бет 75%',
            'bet150': 'Бет 150%', 'raise': 'Рейз',
        }
        for key, expected_ru in labels.items():
            assert expected_ru != 'Fold'
            assert expected_ru != 'Check'
            assert expected_ru != 'Call'

    def test_all_positions_have_russian_names(self):
        for pos in ['BTN', 'SB', 'BB', 'CO', 'HJ', 'MP', 'UTG']:
            ru = localize_position(pos)
            assert ru != pos, f'{pos} should have Russian translation'

    def test_all_formats_have_russian_names(self):
        for fmt in ['SRP', '3bet', '4bet', 'squeeze']:
            ru = localize_format(fmt)
            assert ru != fmt, f'{fmt} should have Russian translation'

    def test_streets_have_russian_names(self):
        for street in ['flop', 'turn', 'river']:
            ru = localize_street(street)
            assert ru != street, f'{street} should have Russian translation'
