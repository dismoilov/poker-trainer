"""
Context-aware poker explanation generator.

Produces detailed, educational explanations for GTO drill feedback
based on board texture, hand strength, position, and action.
"""

from app.services.gto_data import (
    get_hand_tier,
    hand_connects_with_board,
    hand_has_rank,
    hand_is_suited,
    hand_is_pair,
    hand_is_broadway,
    hand_is_connector,
    hand_top_rank_value,
    board_high_card_value,
    RANK_VALUES,
)


# ═══════════════════════════════════════════════════════════════════
# Board texture analysis
# ═══════════════════════════════════════════════════════════════════

def _classify_board(board: list[str]) -> dict:
    """Analyze board texture and return classification."""
    ranks = [card[0] for card in board]
    suits = [card[1] for card in board]
    vals = sorted([RANK_VALUES.get(r, 0) for r in ranks], reverse=True)

    # Flush analysis
    suit_counts = {}
    for s in suits:
        suit_counts[s] = suit_counts.get(s, 0) + 1
    max_suit = max(suit_counts.values())
    flush_type = "monotone" if max_suit == 3 else ("two_tone" if max_suit == 2 else "rainbow")

    # Connectivity
    gaps = [vals[i] - vals[i + 1] for i in range(len(vals) - 1)]
    connected = all(g <= 2 for g in gaps) and max(gaps) <= 2
    has_pair = len(set(ranks)) < len(ranks)

    # Board height
    high_val = vals[0]
    if high_val >= 12:  # Q+
        height = "high"
    elif high_val >= 9:  # 9-J
        height = "medium"
    else:
        height = "low"

    # Texture type
    if has_pair:
        texture = "paired"
    elif connected and max_suit >= 2:
        texture = "wet"
    elif connected:
        texture = "wet"
    elif max_suit == 3:
        texture = "monotone"
    elif max_suit == 2 and max(gaps) <= 3:
        texture = "semi_wet"
    elif max_suit == 2:
        texture = "two_tone"
    else:
        texture = "dry"

    return {
        "texture": texture,
        "flush_type": flush_type,
        "height": height,
        "connected": connected,
        "has_pair": has_pair,
        "high_card": ranks[vals.index(vals[0])],
        "vals": vals,
    }


# ═══════════════════════════════════════════════════════════════════
# Explanation generation
# ═══════════════════════════════════════════════════════════════════

def generate_explanation(
    hand: str,
    board: list[str],
    chosen_action: str,
    correct_action: str,
    frequencies: dict[str, float],
    position: str,
    line_description: str,
    pot_type: str = "SRP",  # SRP, 3bet, 4bet
) -> list[str]:
    """Generate detailed poker explanation for a drill answer."""
    explanations: list[str] = []
    tier = get_hand_tier(hand)
    connection = hand_connects_with_board(hand, board)
    board_info = _classify_board(board)
    is_ip = position in ("BTN", "CO", "MP", "UTG")  # simplified

    # 1. Board texture description
    explanations.append(_board_texture_explanation(board_info))

    # 2. Hand strength on this board
    explanations.append(_hand_strength_explanation(hand, tier, connection, board_info))

    # 3. Range / nut advantage
    explanations.append(_range_advantage_explanation(board_info, is_ip, pot_type))

    # 4. Position context
    explanations.append(_position_explanation(position, is_ip, board_info))

    # 5. Action-specific explanation
    if correct_action:
        explanations.append(_action_explanation(
            hand, correct_action, chosen_action, frequencies,
            connection, board_info, is_ip, tier
        ))

    # 6. Blocker effects
    blocker_note = _blocker_explanation(hand, board_info)
    if blocker_note:
        explanations.append(blocker_note)

    # 7. Mixed strategy note
    if frequencies:
        mixed_actions = [a for a, f in frequencies.items() if 0.15 < f < 0.85]
        if len(mixed_actions) > 1:
            explanations.append(
                f"GTO рекомендует смешанную стратегию для {hand}: "
                f"это значит, что нужно чередовать действия с определёнными частотами, "
                f"чтобы оставаться неэксплуатируемым."
            )

    return explanations


def _board_texture_explanation(board_info: dict) -> str:
    """Describe the board texture."""
    texture = board_info["texture"]
    flush = board_info["flush_type"]
    height = board_info["height"]

    texture_names = {
        "dry": "Сухой борд",
        "paired": "Парный борд",
        "semi_wet": "Полу-координированный борд",
        "wet": "Мокрый (координированный) борд",
        "monotone": "Монотонный борд (три карты одной масти)",
        "two_tone": "Двухмастный борд",
    }
    height_names = {
        "high": "с высокими картами",
        "medium": "со средними картами",
        "low": "с низкими картами",
    }

    name = texture_names.get(texture, "Борд")
    h = height_names.get(height, "")

    if texture == "dry":
        return f"{name} {h}. На таких текстурах c-bet можно ставить часто и маленьким сайзингом (33% пота), т.к. руки оппонента редко попадают."
    elif texture == "paired":
        return f"{name} {h}. На парных текстурах IP игрок может ставить c-bet с высокой частотой маленьким сайзингом, т.к. трипсы и фулл-хаусы встречаются редко."
    elif texture == "wet":
        return f"{name} {h}. Координированные текстуры уравнивают рейнджи — дро и готовые руки есть у обоих игроков. C-bet частота снижается, но сайзинг увеличивается."
    elif texture == "monotone":
        return f"{name} {h}. Флеш-дро есть у многих рук в обоих рейнджах, поэтому c-bet частота снижена, а чек становится основной линией."
    elif texture == "semi_wet":
        return f"{name} {h}. Умеренная координированность — c-bet с mix сайзингов (33% и 75%), частота зависит от силы руки."
    elif texture == "two_tone":
        return f"{name} {h}. Наличие двух карт одной масти создаёт дро-возможности. C-bet частота умеренная, сайзинг зависит от текстуры."
    return f"{name} {h}."


def _hand_strength_explanation(hand: str, tier: int, connection: str, board_info: dict) -> str:
    """Describe hand strength on this board."""
    connection_names = {
        "set": f"{hand} — сет! Это очень сильная рука (монстр), играем на наращивание банка.",
        "two_pair": f"{hand} — две пары. Сильная рука, но уязвима на координированных бордах.",
        "overpair": f"{hand} — оверпара (пара выше всех карт борда). Сильная рука для value bet.",
        "top_pair": f"{hand} — топ-пара. Стандартная value рука, сила зависит от кикера.",
        "middle_pair": f"{hand} — средняя пара. Часто играем чек-колл или тонкий value bet.",
        "bottom_pair": f"{hand} — нижняя пара. Обычно играем чек и иногда колл, редко бет.",
        "pair": f"{hand} — пара. Маргинальная рука, стратегия зависит от позиции и текстуры.",
        "underpair": f"{hand} — андерпара (пара ниже карт борда). Слабая рука для showdown.",
        "draw": f"{hand} — дро рука. Имеет потенциал улучшиться, можно использовать как полу-блеф.",
        "nothing": f"{hand} — рука без попадания в борд. Рассматриваем как потенциальный блеф или фолд.",
    }

    base = connection_names.get(connection, f"{hand} — оценка ситуации.")

    tier_desc = ""
    if tier <= 2:
        tier_desc = f" {hand} входит в топ-8% стартовых рук (Tier {tier})."
    elif tier <= 4:
        tier_desc = f" {hand} — крепкая стартовая рука (Tier {tier}, топ-25%)."
    elif tier <= 6:
        tier_desc = f" {hand} — средняя/спекулятивная рука (Tier {tier})."
    else:
        tier_desc = f" {hand} — слабая стартовая рука (Tier {tier})."

    return base + tier_desc


def _range_advantage_explanation(board_info: dict, is_ip: bool, pot_type: str) -> str:
    """Explain range and nut advantage."""
    texture = board_info["texture"]
    height = board_info["height"]

    if pot_type == "3bet":
        if height == "high":
            return "В 3bet поте на борде с высокими картами 3bet-тор (обычно OOP) имеет range advantage: больше AA, KK, AK в его рейндже."
        else:
            return "В 3bet поте на борде с низкими/средними картами коллер (IP) имеет больше сетов и двух пар из средних пар и коннекторов."

    if is_ip:
        if height == "high":
            return "IP игрок (opener) имеет range advantage на высоких бордах: больше топ-пар и оверпар в его рейндже по сравнению с BB."
        elif texture in ("wet", "monotone"):
            return "На мокром борде range advantage IP менее выражен, т.к. BB защищает широко и попадает в дро и готовые руки."
        else:
            return "IP игрок имеет nut advantage (больше натсовых комбинаций) — это позволяет ставить c-bet с высокой частотой."
    else:
        if height == "low" and texture in ("wet", "semi_wet"):
            return "BB имеет range advantage на низких координированных бордах: сеты 33-77, две пары, стриты из дешёвых коннекторов."
        elif height == "high":
            return "На высоких бордах BB играет из позиции слабости — его рейндж хуже попадает в топ-пары с хорошими кикерами."
        else:
            return "OOP позиция компенсируется тем, что BB защищает широкий рейндж — на некоторых текстурах это даёт advantage."


def _position_explanation(position: str, is_ip: bool, board_info: dict) -> str:
    """Explain positional dynamics."""
    if is_ip:
        return (
            f"Вы {position} (в позиции). Позиционное преимущество позволяет контролировать размер банка, "
            f"блефовать эффективнее и реализовать equity лучше, чем OOP оппонент."
        )
    else:
        return (
            f"Вы {position} (вне позиции). OOP снижает equity realization — "
            f"нужно играть сбалансировано: чекать сильные руки для ловушек (check-raise/check-call) "
            f"и не переоценивать маргинальные руки."
        )


def _action_explanation(
    hand: str,
    correct_action: str,
    chosen_action: str,
    frequencies: dict[str, float],
    connection: str,
    board_info: dict,
    is_ip: bool,
    tier: int,
) -> str:
    """Explain why the correct action is recommended."""
    freq = frequencies.get(correct_action, 0)
    freq_pct = f"{freq:.0%}"

    action_names = {
        "check": "Чек",
        "bet33": "Бет 33%",
        "bet75": "Бет 75%",
        "fold": "Фолд",
        "call": "Колл",
        "raise": "Рейз",
    }
    correct_name = action_names.get(correct_action, correct_action)

    if correct_action == "check":
        if connection in ("set", "two_pair", "overpair", "top_pair"):
            return (
                f"GTO рекомендует {correct_name} с частотой {freq_pct} для {hand}. "
                f"Сильные руки часто чекают OOP для баланса: это защищает чек-рейндж "
                f"и позволяет ставить ловушку (check-raise / check-call)."
            )
        elif connection in ("nothing", "underpair"):
            return (
                f"GTO рекомендует {correct_name} с частотой {freq_pct}. "
                f"Без попадания в борд агрессия неоправдана — "
                f"рука не имеет достаточно equity для блефа на данной текстуре."
            )
        else:
            return (
                f"GTO рекомендует {correct_name} с частотой {freq_pct}. "
                f"Средние руки часто выбирают пассивную линию для контроля банка."
            )

    elif correct_action in ("bet33", "bet75"):
        sizing = "малый (33% пота)" if correct_action == "bet33" else "большой (75% пота)"
        if connection in ("set", "two_pair", "overpair"):
            return (
                f"GTO рекомендует бет {sizing} с частотой {freq_pct} для {hand}. "
                f"С сильной рукой ставим для извлечения value из средних и слабых рук оппонента."
            )
        elif connection in ("draw",):
            return (
                f"GTO рекомендует бет {sizing} с частотой {freq_pct}. "
                f"Дро-руки используются как полу-блефы: мы давим на оппонента, "
                f"и при коле у нас есть equity для улучшения."
            )
        elif connection in ("nothing",):
            if board_info["texture"] == "dry":
                return (
                    f"GTO рекомендует бет {sizing} с частотой {freq_pct}. "
                    f"На сухом борде даже без попадания можно блефовать с высокой частотой, "
                    f"т.к. оппонент тоже промахивается."
                )
            else:
                return (
                    f"GTO рекомендует бет {sizing} с частотой {freq_pct}. "
                    f"Блеф на координированном борде — балансирующий элемент стратегии."
                )
        else:
            return (
                f"GTO рекомендует бет {sizing} с частотой {freq_pct}. "
                f"Бет с {hand} на данной текстуре — часть сбалансированного рейнджа."
            )

    elif correct_action == "fold":
        return (
            f"GTO рекомендует фолд с частотой {freq_pct} для {hand}. "
            f"Рука не имеет достаточно equity против рейнджа бета оппонента. "
            f"Продолжение здесь стоит слишком дорого по EV."
        )

    elif correct_action == "call":
        return (
            f"GTO рекомендует колл с частотой {freq_pct} для {hand}. "
            f"Рука имеет достаточно equity для продолжения, но недостаточно силы для рейза."
        )

    elif correct_action == "raise":
        if connection in ("set", "two_pair"):
            return (
                f"GTO рекомендует рейз с частотой {freq_pct} для {hand}. "
                f"Очень сильная рука — рейз для наращивания банка и защиты от дро."
            )
        else:
            return (
                f"GTO рекомендует рейз с частотой {freq_pct} для {hand}. "
                f"Рейз как полу-блеф/блеф — необходим для баланса рейз-рейнджа."
            )

    return f"GTO рекомендует {correct_name} с частотой {freq_pct} для {hand}."


def _blocker_explanation(hand: str, board_info: dict) -> str | None:
    """Generate blocker-specific explanation if relevant."""
    high_card = board_info["high_card"]

    if hand_has_rank(hand, "A"):
        if high_card == "A":
            return (
                "Блокер-эффект: ваш туз блокирует AX комбинации оппонента — "
                "у него меньше топ-пар, что увеличивает эффективность блефа."
            )
        else:
            return (
                "Блокер: наличие A в руке блокирует часть сильных стартовых рук оппонента "
                "(AA, AK, AQ), что может влиять на решение о блефе."
            )

    if hand_has_rank(hand, "K") and high_card == "K":
        return (
            "Блокер: ваш король блокирует KX комбинации оппонента. "
            "Меньше топ-пар в его рейндже — блеф может быть более прибыльным."
        )

    if hand_is_suited(hand) and board_info["flush_type"] in ("two_tone", "monotone"):
        return (
            "Масть вашей руки блокирует некоторые флеш-дро оппонента, "
            "что снижает количество сильных продолжений в его рейндже."
        )

    return None
