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
    'duration': 'Encoder Duration (sec)',
}

COLORS = {
    'mjpeg': 'green',
    'x264': 'blue',
    'lcevc-x264': 'cyan',
    'openh264': 'yellow',
    'x265': 'red',
    'vp8': 'green',
    'vp9': 'magenta',
    'libaom-av1': 'black',
}

FORMATS = {
    120: '.:',
    240: '.-.',
    360: '.-',
    480: '.--',
}

COLORS2 = {
    'mjpeg': {
        # green-ish
        120: '#204020',
        240: '#208020',
        360: '#20c020',
        480: '#20ff20',
    },
    'x264': {
        # blue
        120: '#00c0ff',
        240: '#0080ff',
        360: '#0040ff',
        480: '#0000ff',
    },
    'lcevc-x264': {
        # cyan
        120: '#c0ffff',
        240: '#80ffff',
        360: '#40ffff',
        480: '#00ffff',
    },
    'openh264': {
        # yellow
        120: '#ffc0ff',
        240: '#ff80ff',
        360: '#ff40ff',
        480: '#ff00ff',
    },
    'x265': {
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
    'vp9': {
        # magenta
        120: '#ff0080',
        240: '#ff00a0',
        360: '#ff00d0',
        480: '#ff00ff',
    },
    'libaom-av1': {
        # black
        120: '#ffc0ff',
        240: '#ff80ff',
        360: '#ff40ff',
        480: '#ff00ff',
    },
}

PLOT_TYPES = {
    'bitrate-vmaf',  # traditional rd-test
    'bitrate-ssim',  # traditional rd-test
    'bitrate-psnr',  # traditional rd-test
    'bitrate-overshoot',  # traditional rd-test
    'bitrate-actual_bitrate',  # traditional rd-test
    'bitrate-duration',  # traditional rd-test
    'resolution-vmaf',
    'vmaf-bitrate',
    'all',
}

default_values = {
    'debug': 0,
    'plot_type': 'resolution-vmaf',
    'simple': False,
    'filter': False,
    'infiles': [],
    'outfile': None,
}


def get_resolution(row):
    return int(row['resolution'].split('x')[1])


def get_overshoot(row):
    return (100.0 * (row['actual_bitrate'] - row['bitrate'])) / row['bitrate']


def plot_max_min(df, ycol, ax):
    bitrate = int(ax.title.get_text().split(' = ')[1])
    myset = df[df.bitrate == bitrate]
    max_values = {}
    for codec in myset.codec.unique():
        m = myset[myset.codec == codec]
        max_values[codec] = {
            'resolution': m.loc[m[ycol].idxmax()]['resolution'],
            ycol: m.loc[m[ycol].idxmax()][ycol],
        }
    for codec in max_values.keys():
        # add dots and lines for the best scores
        # ax.scatter(x=max_values[codec]['resolution'],
        #        y=max_values[codec][ycol],
        #        color='r')
        # add horizontal lines for the best score
        y = max_values[codec][ycol]
        ax.axhline(y=y, color=COLORS[codec], linestyle=':')
    # add vertical arrow for the best score
    # x = max_values['lcevc-x264']['resolution']
    # y1 = max_values['lcevc-x264'][ycol]
    # y2 = max_values['x264'][ycol]
    # ycol_delta = y1 - y2
    # color = 'k' if ycol_delta > 0 else 'r'
    # import code; code.interact(local=locals())  # python gdb/debugging
    # ax.annotate('%s' % ycol_delta, xy=(x,y), xytext=(x,y),
    #        arrowprops=dict(arrowstyle="<->", color=color))
    # ax.vlines(x, y1, y2, color=color)


def process_input(options):
    # create pandas dataframe
    df = pd.DataFrame([], dtype=None)
    # read CSV input
    for infile in options.infiles:
        data = np.genfromtxt(infile, delimiter=',', dtype=None, names=True,
                             encoding=None)
        # create pandas dataframe
        df_tmp = pd.DataFrame(data, dtype=None)
        df = df.append(df_tmp)

    # add resolution and overshoot fields
    df['resolution'] = df.apply(lambda row: get_resolution(row), axis=1)
    df['overshoot'] = df.apply(lambda row: get_overshoot(row), axis=1)
    df.sort_values(by=['in_filename', 'codec', 'resolution', 'rcmode'],
                   inplace=True)
    if options.filter:
        # filter overshooting values
        for index, row in df.iterrows():
            if row['overshoot'] > 10.0:
                df.drop(index, inplace=True)

    if options.plot_type == 'resolution-vmaf':
        plot_resolution_vmaf(options, df)
    elif options.plot_type == 'vmaf-bitrate':
        plot_traditional('vmaf', 'actual_bitrate', options, df,
                         options.simple,
                         legend_loc='upper left')
    elif options.plot_type == 'bitrate-vmaf':
        plot_traditional('actual_bitrate', 'vmaf', options, df,
                         options.simple,
                         legend_loc='lower right')
    elif options.plot_type == 'bitrate-psnr':
        plot_traditional('actual_bitrate', 'psnr', options, df,
                         options.simple,
                         legend_loc='lower right')
    elif options.plot_type == 'bitrate-ssim':
        plot_traditional('actual_bitrate', 'ssim', options, df,
                         options.simple,
                         legend_loc='lower right')
    elif options.plot_type == 'bitrate-overshoot':
        plot_traditional('bitrate', 'overshoot', options, df,
                         options.simple,
                         legend_loc='lower right')
    elif options.plot_type == 'bitrate-actual_bitrate':
        plot_traditional('bitrate', 'actual_bitrate', options, df,
                         options.simple,
                         legend_loc='lower right')
    elif options.plot_type == 'bitrate-duration':
        plot_traditional('actual_bitrate', 'duration', options, df,
                         options.simple,
                         legend_loc='upper left')
    elif options.plot_type == 'all':
        # plot_resolution_vmaf(options, df)
        plot_traditional('vmaf', 'actual_bitrate', options, df,
                         options.simple,
                         legend_loc='upper left')
        plot_traditional('actual_bitrate', 'vmaf', options, df,
                         options.simple)
        plot_traditional('actual_bitrate', 'psnr', options, df,
                         options.simple)
        plot_traditional('actual_bitrate', 'ssim', options, df,
                         options.simple)
        plot_traditional('bitrate', 'overshoot', options, df,
                         options.simple)


def plot_resolution_vmaf(options, df):
    # common plot settings
    sb.set_style('darkgrid', {'axes.facecolor': '.9'})

    xcol = 'resolution'
    for ycol in PLOT_NAMES:
        if ycol == 'bitrate':
            continue
        plot_name = PLOT_NAMES[ycol]
        kwargs = {
            'x': xcol,
            'y': ycol,
            'col': 'bitrate',
            'hue': 'codec',
            'ci': 'sd',
            'capsize': .2,
            'palette': 'Paired',
            'height': 6,
            'aspect': .75,
            'kind': 'point',
            'data': df,
            'col_wrap': 3,
            'row_order': RESOLUTIONS,
        }
        fg = sb.catplot(**kwargs)
        fg.set_ylabels(plot_name, fontsize=15)
        # process all the Axes in the figure
        for ax in fg.axes:
            # make sure all the x-axes show xticks
            plt.setp(ax.get_xticklabels(), visible=True)
            # plot_max_min(df, ycol, ax)
        # write to disk
        outfile = '%s.%s-%s.png' % (options.outfile, xcol, ycol)
        fg.savefig(outfile)


def plot_traditional(xcol, ycol, options, df, simple=False, **kwargs):
    vcol = 'codec'
    pcol = 'resolution'
    if simple:
        plot_generic_simple(options, df, xcol, ycol, vcol, pcol, **kwargs)
    else:
        plot_generic(options, df, xcol, ycol, vcol, pcol, **kwargs)


def plot_generic(options, df, xcol, ycol, vcol, pcol, **kwargs):
    # plot the results
    fig = plt.figure()
    num_pcol = df[pcol].nunique()
    max_ncols = 2
    ncols = min(num_pcol, max_ncols)
    nrows = math.ceil(num_pcol / max_ncols)
    # different plots
    for plot_id in range(num_pcol):
        pval = df[pcol].unique()[plot_id]
        pdf = df[df[pcol] == pval]
        ax = fig.add_subplot(nrows, ncols, 1 + plot_id)
        # different lines in each plot
        for var_id in range(pdf[vcol].nunique()):
            vval = pdf[vcol].unique()[var_id]
            color = COLORS[vval]
            xvals = pdf[pdf[vcol] == vval][xcol].tolist()
            yvals = pdf[pdf[vcol] == vval][ycol].tolist()
            label = str(vval)
            fmt = '.-'
            ax.plot(xvals, yvals, fmt, label=label, color=color)
            ax.set_xlabel(PLOT_NAMES[xcol])
            if plot_id % max_ncols == 0:
                ax.set_ylabel(PLOT_NAMES[ycol])
            ax.legend(loc=kwargs.get('legend_loc', 'upper left'))
            ax.set_title('%s: %s' % (pcol, pval))
    # write to disk
    outfile = '%s.%s-%s.png' % (options.outfile, xcol, ycol)
    plt.savefig(outfile)


# same than plot_generic, but mixing pcol and vcol in the same Figure
def plot_generic_simple(options, df, xcol, ycol, vcol, pcol, **kwargs):
    # plot the results
    fig = plt.figure()
    num_pcol = df[pcol].nunique()
    # different plots
    ax = fig.add_subplot(1, 1, 1)
    # turn plots into lines
    for plot_id in range(num_pcol):
        pval = df[pcol].unique()[plot_id]
        pdf = df[df[pcol] == pval]
        fmt = FORMATS[pval]
        # different lines in each plot
        for var_id in range(pdf[vcol].nunique()):
            vval = pdf[vcol].unique()[var_id]
            color = COLORS2[vval][pval]
            xvals = pdf[pdf[vcol] == vval][xcol].tolist()
            yvals = pdf[pdf[vcol] == vval][ycol].tolist()
            label = '%s.%s' % (str(pval), str(vval))
            ax.plot(xvals, yvals, fmt, label=label, color=color)
            ax.set_xlabel(PLOT_NAMES[xcol])
            ax.set_ylabel(PLOT_NAMES[ycol])
            ax.legend(loc=kwargs.get('legend_loc', 'lower right'))
    ax.set_title('%s' % (list(df.iterrows())[0][1]['in_filename']))
    # write to disk
    outfile = '%s.%s-%s.png' % (options.outfile, xcol, ycol)
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
    parser.add_argument('-i', '--infile', action='append', type=str,
                        dest='infiles', default=default_values['infiles'],
                        metavar='input-files',
                        help='input files',)
    parser.add_argument('outfile', type=str,
                        default=default_values['outfile'],
                        metavar='output-file',
                        help='output file',)
    # do the parsing
    options = parser.parse_args(argv[1:])
    infile_list = []
    for infile in options.infiles:
        if infile == '-':
            infile = sys.stdin
        infile_list.append(infile)
    options.infiles = infile_list
    return options


def main(argv):
    # parse options
    options = get_options(argv)
    process_input(options)


if __name__ == '__main__':
    # at least the CLI program name: (CLI) execution
    main(sys.argv)
