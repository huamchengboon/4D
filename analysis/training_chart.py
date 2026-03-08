"""
Live-updating training charts in pop-up windows (macOS / desktop).
Three separate windows: reward, hit rate, policy loss. Uses matplotlib.
Training runs in a background thread so the GUI event loop never blocks it.
"""

from __future__ import annotations

import sys
from collections import deque

import matplotlib
if sys.platform == "darwin":
    try:
        matplotlib.use("MacOSX")
    except Exception:
        matplotlib.use("TkAgg")
else:
    matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import numpy as np

MAX_POINTS = 500


def _normalize(a: list[float]) -> list[float]:
    """Min-max normalize to [0, 1] for display."""
    if not a:
        return []
    arr = np.array(a, dtype=float)
    lo, hi = arr.min(), arr.max()
    if hi <= lo:
        return [0.5] * len(a)
    return ((arr - lo) / (hi - lo)).tolist()


def create_chart_window():
    """
    Create three matplotlib figures (reward, hit rate, loss) and a callback that only appends metrics (no GUI calls).
    Returns (figs, update_chart_fn, step_callback).
    - figs: tuple of (fig_reward, fig_hr, fig_loss) for keep_chart_open().
    - step_callback: pass to run_rl_backtest (runs in training thread); only appends to shared deque.
    - update_chart_fn: call from main thread in a loop with plt.pause(); redraws all three from shared data.
    """
    # Window 1: Reward (RM per draw)
    fig_reward, ax_reward = plt.subplots(figsize=(7, 4))
    fig_reward.canvas.manager.set_window_title("RL Training — Reward (RM)")
    ax_reward.set_xlabel("Step")
    ax_reward.set_ylabel("Reward (RM)")
    ax_reward.set_title("Reward per draw (winnings − cost)")
    ax_reward.grid(True, alpha=0.3)
    (line_reward,) = ax_reward.plot([], [], "g-", linewidth=1.5)

    # Window 2: Hit rate
    fig_hr, ax_hr = plt.subplots(figsize=(7, 4))
    fig_hr.canvas.manager.set_window_title("RL Training — Hit rate")
    ax_hr.set_xlabel("Step")
    ax_hr.set_ylabel("Hit rate")
    ax_hr.set_title("Cumulative hit rate (0–1)")
    ax_hr.set_ylim(0, 1)
    ax_hr.grid(True, alpha=0.3)
    (line_hr,) = ax_hr.plot([], [], "c-", linewidth=1.5)

    # Window 3: Policy loss (gradient) — spikes when reward is high (big update), not financial loss
    fig_loss, ax_loss = plt.subplots(figsize=(7, 4))
    fig_loss.canvas.manager.set_window_title("RL Training — Policy loss")
    ax_loss.set_xlabel("Step")
    ax_loss.set_ylabel("Loss (normalized)")
    ax_loss.set_title("Policy gradient loss (spikes when reward ↑ = strong update; not RM loss)")
    ax_loss.grid(True, alpha=0.3)
    (line_loss,) = ax_loss.plot([], [], "r-", linewidth=1.5)

    shared: deque = deque(maxlen=MAX_POINTS * 2)

    def step_callback(step: int, total: int, reward: float, hit_rate: float, loss: float, epoch_label: str = "") -> None:
        shared.append((step, reward, hit_rate, loss))

    def update_chart() -> None:
        if not shared:
            return
        data = list(shared)
        x = [d[0] for d in data]
        rewards = [d[1] for d in data]
        hit_rates = [d[2] for d in data]
        losses = [d[3] for d in data]
        x_arr = np.array(x)
        x_min = max(0, (x[-1] - MAX_POINTS)) if x else 0
        x_max = (x[-1] + 10) if x else 100

        # Update reward window (raw values; no normalization so scale is meaningful)
        line_reward.set_data(x_arr, rewards)
        ax_reward.set_xlim(x_min, x_max)
        ax_reward.relim()
        ax_reward.autoscale_view(scalex=False, scaley=True)
        fig_reward.canvas.draw_idle()
        fig_reward.canvas.flush_events()

        # Update hit rate (already 0–1)
        line_hr.set_data(x_arr, hit_rates)
        ax_hr.set_xlim(x_min, x_max)
        ax_hr.relim()
        ax_hr.autoscale_view(scalex=False, scaley=False)
        fig_hr.canvas.draw_idle()
        fig_hr.canvas.flush_events()

        # Update loss (normalized for scale)
        line_loss.set_data(x_arr, _normalize(losses))
        ax_loss.set_ylim(0, 1)
        ax_loss.set_xlim(x_min, x_max)
        ax_loss.relim()
        ax_loss.autoscale_view(scalex=False, scaley=False)
        fig_loss.canvas.draw_idle()
        fig_loss.canvas.flush_events()

    plt.ion()
    plt.show(block=False)
    plt.pause(0.05)

    figs = (fig_reward, fig_hr, fig_loss)
    return figs, update_chart, step_callback


def keep_chart_open(fig_or_figs) -> None:
    """Switch to blocking mode so the window(s) stay open until the user close them."""
    plt.ioff()
    plt.show(block=True)
