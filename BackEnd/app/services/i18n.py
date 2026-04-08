"""
Russian localization for solver-generated text — Phase 8C.

Generates user-facing Russian text for recommendation summaries,
deviation descriptions, quality labels, and node context.
"""

from __future__ import annotations

# ── Action labels ──

ACTION_LABELS_RU: dict[str, str] = {
    "fold": "фолд",
    "check": "чек",
    "call": "колл",
    "bet33": "бет 33%",
    "bet_33": "бет 33%",
    "bet50": "бет 50%",
    "bet_50": "бет 50%",
    "bet75": "бет 75%",
    "bet_75": "бет 75%",
    "bet100": "бет 100%",
    "bet_100": "бет 100%",
    "bet150": "бет 150%",
    "bet_150": "бет 150%",
    "raise": "рейз",
    "allin": "олл-ин",
}


def action_ru(action_id: str) -> str:
    return ACTION_LABELS_RU.get(action_id, action_id.replace("_", " "))


# ── Recommendation Summary (Russian) ──

def generate_recommendation_summary_ru(frequencies: dict[str, float]) -> str:
    """Generate a human-readable Russian recommendation summary."""
    if not frequencies:
        return "Нет данных солвера для этого спота."

    sorted_actions = sorted(frequencies.items(), key=lambda x: x[1], reverse=True)
    top_action, top_freq = sorted_actions[0]
    top_label = action_ru(top_action)

    if top_freq >= 0.80:
        parts = [f"В основном {top_label} ({top_freq*100:.0f}%)."]
        for action, freq in sorted_actions[1:]:
            if freq >= 0.05:
                parts.append(f"Иногда {action_ru(action)}.")
        return " ".join(parts)

    if top_freq >= 0.60:
        parts = [f"Преимущественно {top_label} ({top_freq*100:.0f}%)."]
        if len(sorted_actions) > 1:
            sec_action, sec_freq = sorted_actions[1]
            if sec_freq >= 0.15:
                parts.append(f"Иногда {action_ru(sec_action)} ({sec_freq*100:.0f}%).")
        return " ".join(parts)

    if top_freq >= 0.40:
        secondary = [a for a, f in sorted_actions[1:] if f >= 0.20]
        if secondary:
            labels = [top_label] + [action_ru(a) for a in secondary]
            return f"Смешанная стратегия: {' и '.join(labels)}."
        return f"Склоняется к {top_label} ({top_freq*100:.0f}%), но стратегия смешанная."

    significant = [(a, f) for a, f in sorted_actions if f >= 0.15]
    if len(significant) >= 3:
        labels = [f"{action_ru(a)} {f*100:.0f}%" for a, f in significant]
        return f"Распределение: {', '.join(labels)}."
    elif len(significant) == 2:
        a1, f1 = significant[0]
        a2, f2 = significant[1]
        return f"Смешанная: {action_ru(a1)} ({f1*100:.0f}%) и {action_ru(a2)} ({f2*100:.0f}%)."
    return f"Небольшой перевес в сторону {top_label} ({top_freq*100:.0f}%)."


# ── Deviation Classification (Russian) — Phase 8J: 5-level severity ──

def _detect_is_mixed(frequencies: dict[str, float]) -> bool:
    """Detect if this is a genuinely mixed spot (no dominant action)."""
    if not frequencies:
        return False
    sorted_f = sorted(frequencies.values(), reverse=True)
    if len(sorted_f) < 2:
        return False
    return sorted_f[0] < 0.65 and sorted_f[1] >= 0.15


def _coaching_message(
    severity_level: int,
    user_label: str,
    best_label: str,
    user_freq: float,
    best_freq: float,
    is_mixed: bool,
) -> str:
    """Generate a plain-Russian coaching explanation based on severity."""
    if severity_level == 1:
        return "Вы выбрали именно то действие, которое солвер считает лучшим. Так держать!"
    if severity_level == 2:
        if is_mixed:
            return (
                f"Здесь солвер смешивает стратегию, и ваш {user_label} — "
                f"вполне разумный вариант. Оба действия допустимы."
            )
        return (
            f"Ваш {user_label} — хороший выбор. Солвер немного чаще "
            f"выбирает {best_label}, но разница невелика."
        )
    if severity_level == 3:
        if is_mixed:
            return (
                f"Солвер использует ваш {user_label} как часть смешанной стратегии, "
                f"но основная линия — {best_label}. Небольшая неточность."
            )
        return (
            f"Ваш {user_label} — не основная линия солвера. "
            f"Предпочтительнее {best_label} ({best_freq*100:.0f}%). "
            f"Подумайте, какое преимущество даёт {best_label} в этом споте."
        )
    if severity_level == 4:
        return (
            f"Солверу редко нравится {user_label} здесь (всего {user_freq*100:.0f}%). "
            f"Основное действие — {best_label} ({best_freq*100:.0f}%). "
            f"Стоит разобраться, почему {best_label} выгоднее."
        )
    # severity 5
    return (
        f"Солвер практически никогда не выбирает {user_label} в этом споте. "
        f"Правильное действие — {best_label} ({best_freq*100:.0f}%). "
        f"Это важное место для изучения."
    )


def classify_deviation_ru(user_action: str, frequencies: dict[str, float]) -> dict:
    """Classify deviation with 5-level severity and coaching message."""
    if not frequencies:
        return {
            "label": "unknown",
            "severity_level": 0,
            "description": "Нет данных солвера для сравнения.",
            "coaching_message": "Для этого спота нет расчёта — невозможно оценить ваше решение.",
            "accuracy_pct": 0.0,
            "user_freq": 0.0,
            "best_action": "",
            "best_freq": 0.0,
            "is_mixed_spot": False,
        }

    best_action = max(frequencies, key=frequencies.get)
    best_freq = frequencies[best_action]
    user_freq = frequencies.get(user_action, 0.0)

    # Normalize action names
    if user_freq == 0.0:
        normalized = user_action.replace("_", "")
        for k, v in frequencies.items():
            if k.replace("_", "") == normalized:
                user_freq = v
                break

    accuracy_pct = round(user_freq / best_freq * 100, 1) if best_freq > 0 else 0.0
    is_mixed = _detect_is_mixed(frequencies)

    best_label = action_ru(best_action)
    user_label = action_ru(user_action)

    # ── 5-level severity ──
    if user_action == best_action or user_freq == best_freq:
        severity_level = 1
        label = "perfect"
        description = f"Отлично! {user_label.capitalize()} — лучшее действие по солверу."
    elif user_freq >= 0.30:
        severity_level = 2
        label = "good"
        description = (
            f"Хорошо. {user_label.capitalize()} ({user_freq*100:.0f}%) — "
            f"вполне обоснованный выбор. "
            f"Солвер чуть чаще делает {best_label} ({best_freq*100:.0f}%)."
        )
    elif user_freq >= 0.10:
        severity_level = 3
        label = "slight"
        description = (
            f"Небольшое отклонение. {user_label.capitalize()} ({user_freq*100:.0f}%) — "
            f"часть стратегии, но не основная линия. "
            f"Предпочтительнее {best_label} ({best_freq*100:.0f}%)."
        )
    elif user_freq >= 0.02:
        severity_level = 4
        label = "notable"
        description = (
            f"Заметное отклонение. {user_label.capitalize()} встречается "
            f"у солвера редко ({user_freq*100:.0f}%). "
            f"Основное действие — {best_label} ({best_freq*100:.0f}%)."
        )
    else:
        severity_level = 5
        label = "major"
        description = (
            f"Серьёзная ошибка. Солвер почти никогда не выбирает "
            f"{user_label} здесь ({user_freq*100:.0f}%). "
            f"Правильное действие — {best_label} ({best_freq*100:.0f}%)."
        )

    coaching = _coaching_message(
        severity_level, user_label, best_label, user_freq, best_freq, is_mixed,
    )

    return {
        "label": label,
        "severity_level": severity_level,
        "description": description,
        "coaching_message": coaching,
        "accuracy_pct": accuracy_pct,
        "user_freq": round(user_freq, 4),
        "best_action": best_action,
        "best_freq": round(best_freq, 4),
        "is_mixed_spot": is_mixed,
    }


# ── Quality Labels (Russian) — Phase 8J: 5-level ──

QUALITY_LABELS_RU = {
    "perfect": {"emoji": "🎯", "text": "Идеально", "color": "emerald"},
    "good": {"emoji": "✅", "text": "Хороший выбор", "color": "green"},
    "slight": {"emoji": "🔶", "text": "Небольшое отклонение", "color": "amber"},
    "notable": {"emoji": "⚠️", "text": "Заметное отклонение", "color": "orange"},
    "major": {"emoji": "❌", "text": "Серьёзная ошибка", "color": "red"},
    # Legacy compatibility
    "close_to_solver": {"emoji": "✅", "text": "Хороший выбор", "color": "green"},
    "acceptable_deviation": {"emoji": "🔶", "text": "Небольшое отклонение", "color": "amber"},
    "clear_deviation": {"emoji": "❌", "text": "Серьёзная ошибка", "color": "red"},
    "unknown": {"emoji": "❓", "text": "Нет данных", "color": "gray"},
}


def get_quality_label_ru(deviation_label: str) -> dict:
    return QUALITY_LABELS_RU.get(deviation_label, QUALITY_LABELS_RU["unknown"])


# ── Node Context (Russian) ──

def generate_node_context_ru(
    player: str,
    street: str,
    line_description: str,
    pot_size: float = 0.0,
    stack_size: float = 100.0,
) -> dict:
    """Generate educational context in Russian for a decision node."""
    street_ru = {"flop": "флопе", "turn": "тёрне", "river": "ривере"}.get(street, street)
    pos_label = "в позиции (ходите последним)" if player == "IP" else "без позиции (ходите первым)"

    node_explanation = f"Вы {pos_label} на {street_ru}. "
    if line_description:
        node_explanation += f"Линия: {line_description}. "

    if pot_size > 0:
        spr = stack_size / pot_size if pot_size > 0 else 0
        if spr > 10:
            node_explanation += "Глубокие стеки — есть пространство для манёвра."
        elif spr > 3:
            node_explanation += "Средний SPR — решения о вложении стека приближаются."
        else:
            node_explanation += "Короткий SPR — любая крупная ставка обязывает идти до конца."

    spot_context = _describe_spot_ru(player, street, line_description)

    return {
        "node_explanation": node_explanation,
        "spot_context": spot_context,
    }


def _describe_spot_ru(player: str, street: str, line_description: str) -> str:
    line = (line_description or "").lower()
    if "cbet" in line or "c-bet" in line:
        return "Ситуация продолженной ставки (continuation bet). Агрессор префлопа решает, ставить ли снова."
    if "check" in line and "raise" in line:
        return "Ситуация чек-рейза. Игрок чекнул, получил ставку и решает — рейзить или нет."
    if "facing bet" in line or "vs bet" in line:
        return "Вы столкнулись со ставкой и решаете: фолд, колл или рейз."
    if street == "flop":
        if player == "IP":
            return "В позиции на флопе. Вы ходите после оппонента — информационное преимущество."
        return "Без позиции на флопе. Вы ходите первым — важно балансировать между чеком и ставкой."
    if street == "turn":
        return "На тёрне. Новая карта изменила ситуацию — скорректируйте стратегию."
    if street == "river":
        return "На ривере. Карт больше не будет — решения только о вэлью и блефах."
    return f"Точка принятия решения на {street}."


# ── Drill Feedback (Russian) ──

def drill_feedback_ru(is_correct: bool, is_acceptable: bool, chosen: str, best: str,
                       chosen_freq: float, best_freq: float) -> str:
    """Generate drill feedback text in Russian."""
    chosen_ru = action_ru(chosen)
    best_ru = action_ru(best)

    if is_correct:
        return (
            f"Правильно! Солвер играет {best_ru} с частотой {best_freq*100:.0f}%."
        )
    if is_acceptable:
        return (
            f"Приемлемо. Ваш выбор ({chosen_ru}) имеет {chosen_freq*100:.0f}% частоты солвера — "
            f"это часть смешанной стратегии. Основное действие — {best_ru} ({best_freq*100:.0f}%)."
        )
    return (
        f"Неверно. Солвер предпочитает {best_ru} ({best_freq*100:.0f}%). "
        f"Ваш выбор ({chosen_ru}) — всего {chosen_freq*100:.0f}% частоты."
    )
