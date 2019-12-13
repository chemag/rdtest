#!/usr/bin/env python3
# (c) Facebook, Inc. and its affiliates. Confidential and proprietary.

import sys
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import seaborn as sb

RESOLUTIONS = [
    '216x120',
    '432x240',
    '640x360',
    '864x480',
    '1280x720',
]

PLOT_NAMES = {
    'vmaf': 'VMAF Score',
    'psnr': 'PSNR Score',
    'ssim': 'SSIM Score',
    'overshoot': 'Bitrate Overshoot (Percentage)',
}

COLORS = {
    'x264': 'blue',
    'lcevc-x264': 'skyblue',
}


def get_width(row):
    return int(row['resolution'].split('x')[1])


def get_overshoot(row):
    return (100.0 * (row['actual_bitrate'] - row['bitrate'])) / row['bitrate']


def plot_max_min(set1, yaxis, ax):
    bitrate = int(ax.title.get_text().split(' = ')[1])
    myset = set1[set1.bitrate == bitrate]
    max_values = {}
    for codec in myset.codec.unique():
        m = myset[myset.codec == codec]
        max_values[codec] = {
            'width': m.loc[m[yaxis].idxmax()]['width'],
            yaxis: m.loc[m[yaxis].idxmax()][yaxis],
        }
    for codec in max_values.keys():
        # add dots and lines for the best scores
        # ax.scatter(x=max_values[codec]['width'],
        #        y=max_values[codec][yaxis],
        #        color='r')
        # add horizontal lines for the best score
        y = max_values[codec][yaxis]
        ax.axhline(y=y, color=COLORS[codec], linestyle=':')
    # add vertical arrow for the best score
    # x = max_values['lcevc-x264']['width']
    # y1 = max_values['lcevc-x264'][yaxis]
    # y2 = max_values['x264'][yaxis]
    # yaxis_delta = y1 - y2
    # color = 'k' if yaxis_delta > 0 else 'r'
    # import code; code.interact(local=locals())  # python gdb/debugging
    # ax.annotate('%s' % yaxis_delta, xy=(x,y), xytext=(x,y),
    #        arrowprops=dict(arrowstyle="<->", color=color))
    # ax.vlines(x, y1, y2, color=color)


def process_file(inputfile):
    # read CSV input
    data = np.genfromtxt(inputfile, delimiter=',', dtype=None, names=True,
                         encoding=None)

    # create pandas dataframe
    set1 = pd.DataFrame(data, dtype=None)
    set1['width'] = set1.apply(lambda row: get_width(row), axis=1)
    set1['overshoot'] = set1.apply(lambda row: get_overshoot(row), axis=1)
    set1.sort_values(by=['in_filename', 'codec', 'width', 'rcmode'],
                     inplace=True)

    # common plot settings
    sb.set_style('darkgrid', {'axes.facecolor': '.9'})

    for yaxis in PLOT_NAMES:
        plot_name = PLOT_NAMES[yaxis]
        kwargs = {
            'x': 'width',
            'y': yaxis,
            'col': 'bitrate',
            'hue': 'codec',
            'ci': 'sd',
            'capsize': .2,
            'palette': 'Paired',
            'height': 6,
            'aspect': .75,
            'kind': 'point',
            'data': set1,
            'col_wrap': 3,
            'row_order': RESOLUTIONS,
        }
        fg = sb.catplot(**kwargs)
        fg.set_ylabels(plot_name, fontsize=15)
        # process all the Axes in the figure
        for ax in fg.axes:
            # make sure all the x-axes show xticks
            plt.setp(ax.get_xticklabels(), visible=True)
            plot_max_min(set1, yaxis, ax)
        # write to disk
        output_file = '%s.%s.png' % (inputfile, yaxis)
        fg.savefig(output_file)

    # plt.show()


if __name__ == '__main__':
    inputfile = sys.argv[1]
    process_file(inputfile)
