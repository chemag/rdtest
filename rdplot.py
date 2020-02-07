#!/usr/bin/env python3
# (c) Facebook, Inc. and its affiliates. Confidential and proprietary.

import argparse
import math
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
    'bitrate': 'Bitrate',
    'actual_bitrate': 'Actual Bitrate',
}

COLORS = {
    'x264': 'blue',
    'lcevc-x264': 'red',
    'vp8': 'green',
}

FORMATS = {
    120: '.:',
    240: '.-.',
    360: '.-',
    480: '.--',
}

COLORS2 = {
    'x264': {
        # blue
        120: '#00c0ff',
        240: '#0080ff',
        360: '#0040ff',
        480: '#0000ff',
    },
    'lcevc-x264': {
        # red
        120: '#ffc000',
        240: '#ff8000',
        360: '#ff4000',
        480: '#ff0000',
    },
    'vp8': {
        # green
        120: '#004000',
        240: '#008000',
        360: '#00c000',
        480: '#00ff00',
    },
}

PLOT_TYPES = {
    'bitrate-vmaf',  # traditional rd-test
    'resolution-vmaf',
    'vmaf-bitrate',
    'all',
}

default_values = {
    'debug': 0,
    'plot_type': 'resolution-vmaf',
    'simple': False,
    'filter': False,
    'infile': None,
}


def get_resolution(row):
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
            'resolution': m.loc[m[yaxis].idxmax()]['resolution'],
            yaxis: m.loc[m[yaxis].idxmax()][yaxis],
        }
    for codec in max_values.keys():
        # add dots and lines for the best scores
        # ax.scatter(x=max_values[codec]['resolution'],
        #        y=max_values[codec][yaxis],
        #        color='r')
        # add horizontal lines for the best score
        y = max_values[codec][yaxis]
        ax.axhline(y=y, color=COLORS[codec], linestyle=':')
    # add vertical arrow for the best score
    # x = max_values['lcevc-x264']['resolution']
    # y1 = max_values['lcevc-x264'][yaxis]
    # y2 = max_values['x264'][yaxis]
    # yaxis_delta = y1 - y2
    # color = 'k' if yaxis_delta > 0 else 'r'
    # import code; code.interact(local=locals())  # python gdb/debugging
    # ax.annotate('%s' % yaxis_delta, xy=(x,y), xytext=(x,y),
    #        arrowprops=dict(arrowstyle="<->", color=color))
    # ax.vlines(x, y1, y2, color=color)


def process_file(options):
    # read CSV input
    data = np.genfromtxt(options.infile, delimiter=',',
                         dtype=None, names=True, encoding=None)

    # create pandas dataframe
    set1 = pd.DataFrame(data, dtype=None)
    set1['resolution'] = set1.apply(lambda row: get_resolution(row), axis=1)
    set1['overshoot'] = set1.apply(lambda row: get_overshoot(row), axis=1)
    set1.sort_values(by=['in_filename', 'codec', 'resolution', 'rcmode'],
                     inplace=True)
    if options.filter:
        # filter overshooting values
        for index, row in set1.iterrows():
            if row['overshoot'] > 10.0:
                set1.drop(index, inplace=True)

    if options.plot_type == 'resolution-vmaf':
        plot_resolution_vmaf(options, set1)
    elif options.plot_type == 'vmaf-bitrate':
        plot_vmaf_bitrate(options, set1, options.simple)
    elif options.plot_type == 'bitrate-vmaf':
        plot_bitrate_vmaf(options, set1, options.simple)
    elif options.plot_type == 'all':
        plot_resolution_vmaf(options, set1)
        plot_vmaf_bitrate(options, set1, options.simple)
        plot_bitrate_vmaf(options, set1, options.simple)


def plot_resolution_vmaf(options, set1):
    # common plot settings
    sb.set_style('darkgrid', {'axes.facecolor': '.9'})

    for yaxis in PLOT_NAMES:
        if yaxis == 'bitrate':
            continue
        plot_name = PLOT_NAMES[yaxis]
        kwargs = {
            'x': 'resolution',
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
            # plot_max_min(set1, yaxis, ax)
        # write to disk
        outfile = '%s.%s.%s.png' % (options.infile, options.plot_type, yaxis)
        fg.savefig(outfile)


def plot_vmaf_bitrate(options, set1, simple=False):
    xcol = 'vmaf'
    ycol = 'actual_bitrate'
    vcol = 'codec'
    pcol = 'resolution'
    if simple:
        plot_generic_simple(options, set1, xcol, ycol, vcol, pcol)
    else:
        plot_generic(options, set1, xcol, ycol, vcol, pcol)


def plot_bitrate_vmaf(options, set1, simple=False):
    for feature in ('vmaf', 'overshoot'):
        xcol = 'actual_bitrate'
        ycol = feature
        vcol = 'codec'
        pcol = 'resolution'
        if simple:
            plot_generic_simple(options, set1, xcol, ycol, vcol, pcol)
        else:
            plot_generic(options, set1, xcol, ycol, vcol, pcol)


def plot_generic(options, set1, xcol, ycol, vcol, pcol):
    # plot the results
    fig = plt.figure()
    num_pcol = set1[pcol].nunique()
    max_ncols = 3
    ncols = min(num_pcol, max_ncols)
    nrows = math.ceil(num_pcol / max_ncols)
    # different plots
    for plot_id in range(num_pcol):
        pval = set1[pcol].unique()[plot_id]
        pset1 = set1[set1[pcol] == pval]
        ax = fig.add_subplot(nrows, ncols, 1 + plot_id)
        # different lines in each plot
        for var_id in range(pset1[vcol].nunique()):
            vval = pset1[vcol].unique()[var_id]
            color = COLORS[vval]
            xvals = pset1[pset1[vcol] == vval][xcol].tolist()
            yvals = pset1[pset1[vcol] == vval][ycol].tolist()
            label = str(vval)
            fmt = '.-'
            ax.plot(xvals, yvals, fmt, label=label, color=color)
            ax.set_xlabel(PLOT_NAMES[xcol])
            if plot_id % max_ncols == 0:
                ax.set_ylabel(PLOT_NAMES[ycol])
            ax.legend(loc='upper left')
            ax.set_title('%s: %s' % (pcol, pval))
    # write to disk
    outfile = '%s.%s.%s.png' % (options.infile, options.plot_type, ycol)
    plt.savefig(outfile)


# same than plot_generic, but mixing pcol and vcol in the same Figure
def plot_generic_simple(options, set1, xcol, ycol, vcol, pcol):
    # plot the results
    fig = plt.figure()
    num_pcol = set1[pcol].nunique()
    # different plots
    ax = fig.add_subplot(1, 1, 1)
    # turn plots into lines
    for plot_id in range(num_pcol):
        pval = set1[pcol].unique()[plot_id]
        pset1 = set1[set1[pcol] == pval]
        fmt = FORMATS[pval]
        # different lines in each plot
        for var_id in range(pset1[vcol].nunique()):
            vval = pset1[vcol].unique()[var_id]
            color = COLORS2[vval][pval]
            xvals = pset1[pset1[vcol] == vval][xcol].tolist()
            yvals = pset1[pset1[vcol] == vval][ycol].tolist()
            label = '%s.%s' % (str(pval), str(vval))
            ax.plot(xvals, yvals, fmt, label=label, color=color)
            ax.set_xlabel(PLOT_NAMES[xcol])
            ax.set_ylabel(PLOT_NAMES[ycol])
            ax.legend(loc='lower right')
    ax.set_title('%s' % (list(set1.iterrows())[0][1]['in_filename']))
    # write to disk
    outfile = '%s.%s.%s.png' % (options.infile, options.plot_type, ycol)
    plt.savefig(outfile)


def get_options(argv):
    """Generic option parser.

    Args:
        argv: list containing arguments

    Returns:
        Namespace - An argparse.ArgumentParser-generated option object
    """
    # init parser
    # usage = 'usage: %prog [options] arg1 arg2'
    # parser = argparse.OptionParser(usage=usage)
    # parser.print_help() to get argparse.usage (large help)
    # parser.print_usage() to get argparse.usage (just usage line)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-d', '--debug', action='count',
                        dest='debug', default=default_values['debug'],
                        help='Increase verbosity (multiple times for more)',)
    parser.add_argument('--quiet', action='store_const',
                        dest='debug', const=-1,
                        help='Zero verbosity',)
    parser.add_argument('--simple', action='store_true',
                        dest='simple', default=default_values['simple'],
                        help='Simple Plots',)
    parser.add_argument('--filter', action='store_true',
                        dest='filter', default=default_values['filter'],
                        help='Filter Out Overshooting Samples',)
    parser.add_argument('--plot', action='store', type=str,
                        dest='plot_type', default=default_values['plot_type'],
                        choices=PLOT_TYPES,
                        metavar='PLOT_TYPE',
                        help='plot type %r' % PLOT_TYPES,)
    parser.add_argument('--traditional', action='store_const',
                        dest='plot_type', const='bitrate-vmaf',
                        metavar='PLOT_TYPE',
                        help='plot type: bitrate-vmaf',)
    parser.add_argument('infile', type=str,
                        default=default_values['infile'],
                        metavar='input-file',
                        help='input file',)
    # do the parsing
    options = parser.parse_args(argv[1:])
    if options.infile == '-':
        options.infile = sys.stdin
    return options


def main(argv):
    # parse options
    options = get_options(argv)
    process_file(options)


if __name__ == '__main__':
    # at least the CLI program name: (CLI) execution
    main(sys.argv)
