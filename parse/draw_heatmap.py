#!/usr/bin/env python3
"""Draw a latency-breakdown heatmap.

Takes the .npy file produced by parse_breakdown_to_heatmap.py (rows = pipeline
stages, client stages first then server stages; columns = tail samples ordered
by end-to-end latency) and writes a PDF figure.

    ./draw_heatmap.py heatmap_isolated_thread_default_1_64_1_0_1_1_1.npy
    ./draw_heatmap.py heatmap.npy -o figure.pdf --cap 500 --no-bar --no-ylabel
"""
import argparse
import os

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import transforms
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import FancyBboxPatch

# ---------- style (global) ----------
mpl.rcParams.update({
    # font
    "font.size": 12,

    # lines and markers
    "lines.linewidth": 2.5,
    "lines.solid_capstyle": "round",
    "lines.solid_joinstyle": "round",

    # thick frame and ticks

    "xtick.labelsize": 15,
    "xtick.major.width": 2,
    "xtick.major.size": 6,
    "xtick.major.pad": 10,
    "xtick.minor.width": 2,
    "xtick.minor.size": 3,
    "xtick.direction": "in",

    "ytick.labelsize": 15,
    "ytick.major.width": 2,
    "ytick.major.size": 6,
    "ytick.major.pad": 6,
    "ytick.minor.width": 1,
    "ytick.minor.size": 3,
    "ytick.direction": "in",

    # grid
    "grid.linestyle": ":",
    "grid.linewidth": 2,
    "grid.color": "black",
    "grid.alpha": 1,

    # axes
    "axes.labelsize": 15,
    "axes.linewidth": 2,
    "axes.axisbelow": True,
    "axes.labelweight": 600,

    # legend
    "legend.fontsize": 12,
})


# ---------- colormap ----------
reds = mpl.colormaps["Reds"]
deep = reds(1.0)  # the darkest color of Reds


def mix_with_white(rgba, a):
    # a=1 keeps the original color; the smaller a, the closer to white
    r, g, b, _ = rgba
    return (1 - (1 - r) * a, 1 - (1 - g) * a, 1 - (1 - b) * a)


paper_reds = LinearSegmentedColormap.from_list(
    "paper_reds",
    [
        (0.00, (1.00, 1.00, 1.00)),
        (0.18, mix_with_white(reds(0.35), 0.55)),
        (0.55, reds(0.55)),
        (0.82, reds(0.85)),
        (1.00, deep),
    ],
    N=256
)

# One label per row: the same stage order on the client and on the server, see
# STAGES in parse_breakdown_to_heatmap.py.
STAGE_LABELS = ['rx_irq', 'rx_napi', 'rx_ip', 'rx_tcp', 'rx_sched',
                'rx_data_copy', 'app', 'tx_data_copy', 'tx_tcp', 'tx_ip',
                'tx_queue', 'tx_xmit']
HEATMAP_LABELS = STAGE_LABELS * 2

# Figure geometry (inches). The axes is placed inside a deliberately oversized
# figure and the final PDF is cropped to the padded bounding box below.
AX_WIDTH = 2.4
AX_HEIGHT = 2.2
FIG_WIDTH = 20
FIG_HEIGHT = 20

PAD_LEFT = 0.8
PAD_LEFT_NO_LABEL = 0.4
PAD_RIGHT = 0.95
PAD_RIGHT_NO_BAR = 0.4
PAD_BOTTOM = 0.7  # Figure 6a and 10c-d
PAD_TOP = 0.15


def draw_heatmap(tail_latencies, save_path, cap, bar=True, ylabel=True):
    fig = plt.figure(figsize=(FIG_WIDTH, FIG_HEIGHT))  # Create a very big figure
    ax = fig.add_axes([0.3, 0.3, AX_WIDTH / FIG_WIDTH, AX_HEIGHT / FIG_HEIGHT])

    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.add_patch(FancyBboxPatch(
        (0, 0), 1, 1,
        boxstyle="round,pad=0.0,rounding_size=0.001",
        transform=ax.transAxes,
        linewidth=2,
        edgecolor="black",
        facecolor="none",
        zorder=1,
        clip_on=False,
    ))

    # Draw heatmap
    ax.imshow(tail_latencies, aspect='auto', interpolation='nearest',
              vmin=0, vmax=cap, cmap=paper_reds)

    # Draw horizontal line to separate client and server
    n_rows, n_cols = tail_latencies.shape
    split = n_rows / 2
    ax.axhline(y=split - 0.6, color='black', linestyle=(0, (2, 4)),
               linewidth=1, dash_capstyle='round')
    ax.text(x=n_cols / 2, y=split - 1, s='Client', ha='center', fontsize=12)
    ax.text(x=n_cols / 2, y=n_rows - 1, s='Server', ha='center', fontsize=12)

    if bar:
        cax_width = 0.006
        cax_pad = 0.005

        ax_pos = ax.get_position()
        cax = fig.add_axes([
            ax_pos.x1 + cax_pad,  # right next to ax
            ax_pos.y0,
            cax_width,
            ax_pos.height,
        ])

        cb = fig.colorbar(ax.images[0], cax=cax, fraction=0.046, pad=0)
        cb.set_label('Latency (us)', rotation=90, labelpad=5)
        cb.ax.yaxis.set_tick_params(labelsize=12)
        cb.outline.set_visible(False)
        cb.ax.add_patch(FancyBboxPatch(
            (0, 0), 1, 1,
            boxstyle="round,pad=0.0,rounding_size=0.001",
            transform=cb.ax.transAxes,
            linewidth=2,
            edgecolor="black",
            facecolor="none",
            zorder=5,
            clip_on=False,
        ))

    ax.set_xlabel('Percentile', labelpad=8)
    ax.set_xticks(ticks=np.linspace(0, n_cols - 1, 5))
    ax.set_xticklabels([f"{x}" for x in np.linspace(99.8, 100, 5)],
                       rotation=0, fontsize=12)
    ax.tick_params(axis='x', labelsize=12)

    ax.set_yticks(ticks=np.arange(n_rows))
    if ylabel:
        labels = HEATMAP_LABELS if n_rows == len(HEATMAP_LABELS) else \
            [str(i) for i in range(n_rows)]
        ax.set_yticklabels(labels=labels, ha='right', fontsize=8)
        ax.tick_params(axis='y', labelsize=8)
    else:
        ax.set_yticklabels(labels=[])

    ax.tick_params(axis="both", which="both", width=1, length=3)

    # Crop the oversized figure to the axes plus a fixed padding.
    pos = ax.get_position()
    fig_w, fig_h = fig.get_size_inches()
    x0 = fig_w * pos.x0
    y0 = fig_h * pos.y0
    width = fig_w * pos.width
    height = fig_h * pos.height

    bbox = transforms.Bbox.from_extents(
        x0 - (PAD_LEFT if ylabel else PAD_LEFT_NO_LABEL),
        y0 - PAD_BOTTOM,
        x0 + width + (PAD_RIGHT if bar else PAD_RIGHT_NO_BAR),
        y0 + height + PAD_TOP,
    )

    fig.savefig(save_path, bbox_inches=bbox)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("npy", help="heatmap .npy file produced by parse_breakdown_to_heatmap.py")
    parser.add_argument("-o", "--output",
                        help="output PDF (default: the input path with a .pdf suffix)")
    parser.add_argument("--cap", type=float, default=1500,
                        help="upper bound of the color scale, in us (500 for Figure 10c-d)")
    parser.add_argument("--no-bar", dest="bar", action="store_false",
                        help="do not draw the colorbar")
    parser.add_argument("--no-ylabel", dest="ylabel", action="store_false",
                        help="do not draw the stage labels")
    args = parser.parse_args()

    tail_latencies = np.load(args.npy)
    save_path = args.output or os.path.splitext(args.npy)[0] + ".pdf"
    draw_heatmap(tail_latencies, save_path, args.cap, bar=args.bar, ylabel=args.ylabel)
    print(f"Wrote {save_path} ({tail_latencies.shape[0]} stages x "
          f"{tail_latencies.shape[1]} tail samples).")
