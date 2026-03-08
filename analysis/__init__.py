"""
4D history data analysis: load, transform, and visualize.
Uses Polars for fast data engineering and Seaborn/Matplotlib for viz.
"""

from analysis.load import load_history, get_draws_long, get_number_frequencies
from analysis.plots import (
    plot_draws_per_day,
    plot_first_digit_distribution,
    plot_number_frequency,
    plot_number_frequency_single,
    plot_operator_breakdown,
    plot_prize_type_breakdown,
)

__all__ = [
    "load_history",
    "get_draws_long",
    "get_number_frequencies",
    "plot_draws_per_day",
    "plot_number_frequency",
    "plot_number_frequency_single",
    "plot_operator_breakdown",
    "plot_first_digit_distribution",
    "plot_prize_type_breakdown",
]
