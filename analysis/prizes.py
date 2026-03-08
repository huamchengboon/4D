"""
Magnum 4D prize amounts (Big forecast, per RM1 bet) and P&L for model predictions.
"""

from __future__ import annotations

# Magnum 4D Big forecast, per RM1 bet (see docs/MAGNUM_4D_PRIZES.md)
MAGNUM_PRIZE_1ST = 2_500
MAGNUM_PRIZE_2ND = 1_000
MAGNUM_PRIZE_3RD = 500
MAGNUM_PRIZE_SPECIAL = 180
MAGNUM_PRIZE_CONSOLATION = 60

# Magnum 4D Small forecast: only 1st/2nd/3rd pay; Special & Consolation = 0
MAGNUM_SMALL_PRIZE_1ST = 3_500
MAGNUM_SMALL_PRIZE_2ND = 2_000
MAGNUM_SMALL_PRIZE_3RD = 1_000
MAGNUM_SMALL_PRIZE_SPECIAL = 0
MAGNUM_SMALL_PRIZE_CONSOLATION = 0

# 3D (last 3 digits match): when your number's last 3 digits match 1st/2nd/3rd prize's last 3
# Source: check4d.org Malaysia prize structure
MAGNUM_3D_BIG_1ST = 250   # last 3 match 1st prize
MAGNUM_3D_BIG_2ND = 210   # last 3 match 2nd prize
MAGNUM_3D_BIG_3RD = 150   # last 3 match 3rd prize
MAGNUM_3D_SMALL_1ST = 660  # last 3 match 1st only; Small has no 3D 2nd/3rd
MAGNUM_3D_SMALL_2ND = 0
MAGNUM_3D_SMALL_3RD = 0

# Cost per draw when betting RM1 on each of 23 numbers
COST_PER_DRAW_RM = 23.0


def _idx_to_number(i: int) -> str:
    return f"{i:04d}"


def compute_draw_winnings(
    predicted_indices: list[int],
    draw_prizes: dict,
) -> float:
    """
    Given 23 predicted number indices and one draw's prize breakdown (1st, 2nd, 3rd, special, consolation),
    return total winnings in RM. Each prediction is assumed to be a RM1 bet.
    Uses Magnum 4D prize table; same prize tier used for all operators.
    """
    first = draw_prizes.get("1st")
    second = draw_prizes.get("2nd")
    third = draw_prizes.get("3rd")
    special = set(draw_prizes.get("special") or [])
    consolation = set(draw_prizes.get("consolation") or [])

    total = 0.0
    for idx in predicted_indices:
        num = _idx_to_number(idx)
        if first and num == first:
            total += MAGNUM_PRIZE_1ST
        elif second and num == second:
            total += MAGNUM_PRIZE_2ND
        elif third and num == third:
            total += MAGNUM_PRIZE_3RD
        elif num in special:
            total += MAGNUM_PRIZE_SPECIAL
        elif num in consolation:
            total += MAGNUM_PRIZE_CONSOLATION
    return total


def compute_profit_loss(
    results: list,
    draws_with_prizes: list[dict],
    bet_per_number: float = 1.0,
) -> tuple[float, float, float]:
    """
    results: list of StepResult (each has .action = list of 23 indices).
    draws_with_prizes: list of prize dicts, same length and order as results.
    bet_per_number: RM per number (default 1, so RM23 per draw).
    Returns: (total_cost_rm, total_winnings_rm, total_profit_rm).
    """
    n_draws = len(results)
    k = 23
    total_cost = n_draws * k * bet_per_number
    total_winnings = 0.0
    for i in range(n_draws):
        if i < len(draws_with_prizes):
            total_winnings += compute_draw_winnings(results[i].action, draws_with_prizes[i])
    total_profit = total_winnings - total_cost
    return (total_cost, total_winnings, total_profit)
