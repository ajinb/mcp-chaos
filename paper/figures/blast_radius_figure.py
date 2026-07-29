"""Figure: measured agent-task blast radius vs the independence prediction.

Plots Table 1 of the Tool-Call Plane paper as a graph. Data are regenerated
live from the released harness (examples/blast_radius_sweep.py parameters:
20 seeds x 200 tasks per cell), so the figure is the measurement, not a
transcription.

Design notes: TCAF identity is carried by position (the curves never cross),
direct labels, and marker shape -- not color. Color encodes condition only:
blue = no-resilience family (measured points + predicted curves), neutral
gray = resilient. Two-hue palette validated for CVD safety and >=3:1 contrast;
grayscale-safe for print.

Usage: python paper/figures/blast_radius_figure.py [--seeds 20] [--tasks 200]
Writes fig_blast_radius.pdf (vector, for the paper) and .png (preview).
"""

from __future__ import annotations

import argparse
import pathlib
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FixedLocator, NullLocator  # noqa: E402

from mcp_chaos.resilience import ResilienceConfig  # noqa: E402
from mcp_chaos.sim.agent_loop import run_workload  # noqa: E402

BLUE = "#2171b5"   # no-resilience family (measured + predicted)
GRAY = "#5f6b76"   # resilient (neutral condition marker, direct-labeled)
INK = "#333333"

ERROR_RATES = [0.005, 0.01, 0.02, 0.05, 0.10]
FANOUTS = [2, 4, 8, 16]
MARKERS = {2: "o", 4: "s", 8: "^", 16: "D"}


def measure(seeds: int, tasks: int):
    out = {}
    for resilient in (False, True):
        cfg = ResilienceConfig.enabled() if resilient else ResilienceConfig.disabled()
        for f in FANOUTS:
            means, sds = [], []
            for e in ERROR_RATES:
                brs = [run_workload(tasks=tasks, fanout=f, error_rate=e, seed=s,
                                    resilience=cfg).blast_radius for s in range(seeds)]
                means.append(statistics.mean(brs))
                sds.append(statistics.stdev(brs))
            out[(f, resilient)] = (means, sds)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--tasks", type=int, default=200)
    args = ap.parse_args()

    data = measure(args.seeds, args.tasks)

    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "Nimbus Roman", "DejaVu Serif"],
        "mathtext.fontset": "stix",
        "font.size": 8,
        "axes.linewidth": 0.6,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
    })

    fig, ax = plt.subplots(figsize=(3.5, 2.7))

    # Predicted curves: 1 - (1-e)^TCAF, dashed, one per fan-out; direct labels
    # hang off the curve ends (identity by position + label, not color).
    xs = [0.004 * (1.045 ** i) for i in range(80)]
    xs = [x for x in xs if x <= 0.103]
    for f in FANOUTS:
        ax.plot(xs, [1 - (1 - x) ** f for x in xs],
                ls=(0, (4, 2)), lw=0.9, color=BLUE, alpha=0.75, zorder=2)
        ax.annotate(f"TCAF = {f}", xy=(0.108, 1 - (1 - xs[-1]) ** f), xycoords="data",
                    fontsize=6.5, color=INK, va="center", ha="left")

    # Measured, no resilience: mean +/- sd over seeds.
    for f in FANOUTS:
        means, sds = data[(f, False)]
        ax.errorbar(ERROR_RATES, means, yerr=sds, ls="none",
                    marker=MARKERS[f], ms=3.4, mfc=BLUE, mec="white", mew=0.5,
                    ecolor=BLUE, elinewidth=0.7, capsize=1.4, capthick=0.7, zorder=3)

    # Measured, resilient: worst case is TCAF=16; all others are <= it.
    means16, sds16 = data[(16, True)]
    ax.errorbar(ERROR_RATES, means16, yerr=sds16, ls="-", lw=0.8,
                marker="D", ms=2.8, color=GRAY, mfc=GRAY, mec="white", mew=0.5,
                ecolor=GRAY, elinewidth=0.7, capsize=1.2, capthick=0.7, zorder=3)

    ax.set_xscale("log")
    ax.set_xlim(0.004, 0.185)
    ax.set_ylim(-0.02, 0.9)
    ax.xaxis.set_major_locator(FixedLocator(ERROR_RATES))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.set_xticklabels([f"{e:.1%}".rstrip("0").rstrip(".").replace(".0%", "%")
                        for e in ERROR_RATES])
    ax.set_yticks([0.0, 0.2, 0.4, 0.6, 0.8])
    ax.set_yticklabels(["0%", "20%", "40%", "60%", "80%"])
    ax.set_xlabel("injected per-call error rate $e$ (log scale)", fontsize=8)
    ax.set_ylabel("agent-task blast radius", fontsize=8)

    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, color="#dddddd", lw=0.4)
    ax.set_axisbelow(True)

    handles = [
        plt.Line2D([], [], ls="none", marker="o", ms=3.4, mfc=BLUE, mec="white", mew=0.5),
        plt.Line2D([], [], ls=(0, (4, 2)), lw=0.9, color=BLUE, alpha=0.75),
        plt.Line2D([], [], ls="-", lw=0.8, marker="D", ms=2.8, color=GRAY,
                   mfc=GRAY, mec="white", mew=0.5),
    ]
    labels = [
        "measured, no resilience (mean $\\pm$ sd)",
        "independence prediction $1-(1-e)^{\\mathrm{TCAF}}$",
        "measured, resilient (worst shown: TCAF = 16)",
    ]
    ax.legend(handles, labels, loc="upper left", fontsize=6.5, frameon=False,
              borderaxespad=0.2, handlelength=1.9, labelspacing=0.4)

    out = pathlib.Path(__file__).resolve().parent
    fig.tight_layout(pad=0.3)
    fig.savefig(out / "fig_blast_radius.pdf")
    fig.savefig(out / "fig_blast_radius.png", dpi=300)
    print(f"wrote {out / 'fig_blast_radius.pdf'} and .png")


if __name__ == "__main__":
    main()
