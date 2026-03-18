"""
4D history data analysis: load, transform, and visualize.
Uses Polars for fast data engineering and Seaborn/Matplotlib for viz.
"""

from analysis.load import load_history, get_draws_long, get_number_frequencies

# Plotting helpers pull in heavy, optional visualization dependencies (matplotlib/seaborn).
# The API server imports the `analysis.*` modules at runtime; therefore we must not require
# plotting libs just to start the FastAPI process.
#
# We keep the public plotting API, but import the plotting module lazily only when
# the caller actually uses these functions.

def plot_draws_per_day(*args, **kwargs):
    from analysis.plots import plot_draws_per_day as _fn

    return _fn(*args, **kwargs)


def plot_first_digit_distribution(*args, **kwargs):
    from analysis.plots import plot_first_digit_distribution as _fn

    return _fn(*args, **kwargs)


def plot_number_frequency(*args, **kwargs):
    from analysis.plots import plot_number_frequency as _fn

    return _fn(*args, **kwargs)


def plot_number_frequency_single(*args, **kwargs):
    from analysis.plots import plot_number_frequency_single as _fn

    return _fn(*args, **kwargs)


def plot_operator_breakdown(*args, **kwargs):
    from analysis.plots import plot_operator_breakdown as _fn

    return _fn(*args, **kwargs)


def plot_prize_type_breakdown(*args, **kwargs):
    from analysis.plots import plot_prize_type_breakdown as _fn

    return _fn(*args, **kwargs)

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
