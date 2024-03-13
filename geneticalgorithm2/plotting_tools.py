
from typing import Optional, Sequence

import numpy as np

from .aliases import PathLike
from .files import mkdir_of_file


def plot_several_lines(
    lines: Sequence[Sequence[float]],
    colors: Sequence[str],
    labels: Optional[Sequence[str]] = None,
    linewidths: Optional[Sequence[int]] = None,
    title: str = '',
    xlabel: str = 'Generation',
    ylabel: str = 'Minimized function',
    save_as: Optional[PathLike] = None,
    dpi: int = 200
):
    # import matplotlib
    # matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator

    ax = plt.axes()
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))

    if labels is None:
        labels = list(map(str, range(len(lines))))
    if linewidths is None:
        linewidths = [1.5] * len(lines)

    for line, color, label, linewidth in zip(
        lines, colors, labels, linewidths
    ):
        plt.plot(
            line,
            color=color,
            label=label,
            linewidth=linewidth
        )

    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.legend()

    if save_as is not None:
        plt.savefig(save_as, dpi=dpi)

    plt.show()

def plot_pop_scores(scores: Sequence[float], title: str = 'Population scores', save_as: Optional[str] = None):
    """
    plots scores (numeric values) as sorted bars
    """
    # import matplotlib
    # matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.cm as cm
    from matplotlib.colors import Normalize
    from matplotlib.ticker import NullLocator
    
    sc = sorted(scores)[::-1]

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.xaxis.set_major_locator(NullLocator())

    def autolabel(rects):
        """Attach a text label above each bar in *rects*, displaying its height."""
        for rect in rects[-1:]:
            height = round(rect.get_height(), 2)
            ax.annotate('{}'.format(height),
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3),  # 3 points vertical offset
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=14, fontweight='bold')
    


    cols = np.zeros(len(sc))
    cols[-1] = 1

    x_coord = np.arange(len(sc))
    my_norm = Normalize(vmin=0, vmax=1)
    
    rc = ax.bar(x_coord, sc,  width=0.7, color=cm.get_cmap('Set2')(my_norm(cols)))
    
    autolabel(rc)

    #ax.set_xticks(x_coord)
    ax.set_title(title, fontsize=16, fontweight='bold')
    ax.set_xlabel('Population objects')
    ax.set_ylabel('Cost values')
    #ax.set_ylim([0, max(subdict.values())*1.2])
    #fig.suptitle(title, fontsize=15, fontweight='bold')

    
    fig.tight_layout()
    
    if save_as is not None:
        mkdir_of_file(save_as)
        plt.savefig(save_as, dpi=200)
    
    plt.show()
