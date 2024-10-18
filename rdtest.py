#!/usr/bin/env python

"""rdtest.py module description."""

# Invalid name "get_info" (should match ^_?[A-Z][a-zA-Z0-9]*$)
# pylint: disable-msg=C0103

import argparse
import itertools
import os
import pandas as pd
import pathlib
import sys

import utils


CODEC_INFO = {
    "mjpeg": {
        "codecname": "mjpeg",
        "extension": ".mp4",
        "parameters": {},
    },
    "x264": {
        "codecname": "libx264",
        "extension": ".mp4",
        "parameters": {},
        "preset-name": "preset",
        "presets": (
            "ultrafast",
            "superfast",
            "veryfast",
            "faster",
            "fast",
            "medium",
            "slow",
            "slower",
            "veryslow",
            "placebo",
        ),
    },
    "openh264": {
        "codecname": "libopenh264",
        "extension": ".mp4",
        "parameters": {},
        "preset-name": "complexity",
        "presets": ("0", "1", "2"),
    },
    "x265": {
        "codecname": "libx265",
        "extension": ".mp4",
        "parameters": {},
        "preset-name": "preset",
        "presets": (
            "ultrafast",
            "superfast",
            "veryfast",
            "faster",
            "fast",
            "medium",
            "slow",
            "slower",
            "veryslow",
            "placebo",
        ),
    },
    "vp8": {
        "codecname": "vp8",
        "extension": ".webm",
        "parameters": {
            # quality parameters
            "quality": "realtime",
        },
        "preset-name": "cpu-used",
        "presets": (
            "0",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "10",
            "11",
            "12",
            "13",
            "14",
            "15",
            "16",
        ),
    },
    "vp9": {
        "codecname": "libvpx-vp9",
        "extension": ".webm",
        "parameters": {
            # quality parameters
            "quality": "realtime",
            "qmin": 2,
            "qmax": 56,
        },
        "preset-name": "cpu-used",
        "presets": ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9"),
    },
    "libaom-av1": {
        "codecname": "libaom-av1",
        "extension": ".mp4",
        "parameters": {
            # ABR at https://trac.ffmpeg.org/wiki/Encode/AV1
            # this should reduce the encoding time to manageable levels
            # "cpu-used": 5,
        },
        "preset-name": "cpu-used",
        "presets": ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"),
    },
    "libsvtav1": {
        "codecname": "libsvtav1",
        "extension": ".mp4",
        "parameters": {},
        "preset-name": "preset",
        "presets": (
            "-1",
            "0",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "10",
            "11",
            "12",
            "13",
        ),
    },
    "libsvtav1-raw": {
        "codecname": "libsvtav1-raw",
        "extension": ".ivf",
        "binary": "SvtAv1EncApp",
        "parameters": {},
        "preset-name": "preset",
        "presets": (
            "-1",
            "0",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "10",
            "11",
            "12",
            "13",
        ),
    },
}


# codecs
DEFAULT_CODECS = CODEC_INFO.keys()


# resolution set 1
DEFAULT_RESOLUTIONS = [
    "640x360",  # 200-437kbps
    "480x272",  # actually 480x270 100-200kbps
    "320x160",  # < 100kbps
]

# resolution set 2
DEFAULT_RESOLUTIONS = [
    "1280x720",
    "864x480",
    "640x360",
    "432x240",
    "216x120",
    # '160x90',
]

# use None for input resolution
DEFAULT_RESOLUTIONS = [
    None,
]

# bitrates are defined in Kbps
# TODO(chema): add a better mechanism to define bitrates
DEFAULT_BITRATES = [
    2500,
    1000,
    560,
    280,
    140,
    70,
    35,
]
DEFAULT_QUALITIES = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50]
# https://trac.ffmpeg.org/wiki/Encode/H.264
# https://trac.ffmpeg.org/wiki/Encode/H.265
DEFAULT_PRESETS = [
    "ultrafast",
    "superfast",
    "veryfast",
    "faster",
    "fast",
    "medium",  # default preset
    "slow",
    "slower",
    "veryslow",
]
# https://trac.ffmpeg.org/wiki/Encode/AV1
# higher numbers provide a higher encoding speed
PRESETS_AV1 = [
    0,
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    12,
    13,
]

DEFAULT_RCMODES = [
    "cbr",
    "crf",
]


default_values = {
    "debug": 0,
    "cleanup": 0,
    "label": "",
    "ref_res": None,
    "ref_pix_fmt": "yuv420p",
    "vmaf_dir": "/tmp/",
    "tmp_dir": "/tmp/",
    "gop_length_frames": 600,
    "codecs": DEFAULT_CODECS,
    "resolutions": DEFAULT_RESOLUTIONS,
    "bitrates": DEFAULT_BITRATES,
    "qualities": DEFAULT_QUALITIES,
    "presets": DEFAULT_PRESETS,
    "rcmodes": DEFAULT_RCMODES,
    "infile_list": [],
    "outfile": None,
}


def run_experiment(options):
    # check all software is ok
    utils.check_software(options.debug)

    # prepare output directory
    pathlib.Path(options.tmp_dir).mkdir(parents=True, exist_ok=True)

    df = None
    for infile in options.infile_list:
        df_tmp = run_experiment_single_file(
            infile,
            options.label,
            options.codecs,
            options.resolutions,
            options.rcmodes,
            options.presets,
            options.bitrates,
            options.qualities,
            options.ref_res,
            options.ref_pix_fmt,
            options.gop_length_frames,
            options.tmp_dir,
            options.cleanup,
            options.debug,
        )
        df = df_tmp if df is None else pd.concat([df, df_tmp])
    # write up the results
    df.to_csv(options.outfile, index=False)


def run_experiment_single_file(
    infile,
    label,
    codecs,
    resolutions,
    rcmodes,
    presets,
    bitrates,
    qualities,
    ref_res,
    ref_pix_fmt,
    gop_length_frames,
    tmp_dir,
    cleanup,
    debug,
):
    # 1. in: get infile information
    if debug > 0:
        print("# [run] parsing file: %s" % (infile))
    assert os.access(infile, os.R_OK), "file %s is not readable" % infile
    in_basename = os.path.basename(infile)
    in_resolution = utils.get_resolution(infile)
    in_framerate = utils.get_framerate(infile)

    # 2. ref: decode the original file into a raw file
    ref_basename = f"{in_basename}.ref_{in_resolution}.y4m"
    if debug > 0:
        print(f"# [run] normalize file: {infile} -> {ref_basename}")
    ref_filename = os.path.join(tmp_dir, ref_basename)
    ref_resolution = in_resolution if ref_res is None else ref_res
    ref_framerate = in_framerate
    ref_pix_fmt = ref_pix_fmt
    ffmpeg_params = [
        "-y",
        "-i",
        infile,
        "-s",
        ref_resolution,
        "-pix_fmt",
        ref_pix_fmt,
        ref_filename,
    ]
    retcode, stdout, stderr, _ = utils.ffmpeg_run(ffmpeg_params, debug)
    assert retcode == 0, stderr
    # check produced file matches the requirements
    assert ref_resolution == utils.get_resolution(
        ref_filename
    ), "Error: %s must have resolution: %s (is %s)" % (
        ref_filename,
        ref_resolution,
        utils.get_resolution(ref_filename),
    )
    assert ref_pix_fmt == utils.get_pix_fmt(
        ref_filename
    ), "Error: %s must have pix_fmt: %s (is %s)" % (
        ref_filename,
        ref_pix_fmt,
        utils.get_pix_fmt(ref_filename),
    )

    columns_init = (
        "infile",
        "label",
        "codec",
        "resolution",
        "width",
        "height",
        "framerate",
        "rcmode",
        "quality",
        "bitrate",
        "preset",
        "actual_bitrate",
    )
    columns_fini = ("parameters",)
    df = None

    # run the list of encodings
    for codec, resolution, rcmode, preset in itertools.product(
        codecs, resolutions, rcmodes, presets
    ):
        if resolution is None:
            resolution = in_resolution
        parameters_csv_str = ""
        for k, v in CODEC_INFO[codec]["parameters"].items():
            parameters_csv_str += "%s=%s;" % (k, str(v))
        # get bitrate/quality list
        if rcmode == "cbr":
            quality_bitrate_option = "bitrate"
            qualities_bitrates = bitrates
        elif rcmode == "crf":
            quality_bitrate_option = "quality"
            qualities_bitrates = qualities
        for quality_bitrate in qualities_bitrates:
            (
                encoder_stats,
                actual_bitrate,
                psnr_dict,
                ssim_dict,
                vmaf_dict,
            ) = run_single_experiment(
                ref_filename,
                ref_resolution,
                ref_pix_fmt,
                ref_framerate,
                codec,
                resolution,
                quality_bitrate_option,
                quality_bitrate,
                preset,
                rcmode,
                gop_length_frames,
                tmp_dir,
                debug,
                cleanup,
            )
            width, height = resolution.split("x")
            ref_framerate = utils.get_framerate(ref_filename)
            if quality_bitrate_option == "bitrate":
                quality = ""
                bitrate = quality_bitrate
            elif quality_bitrate_option == "quality":
                bitrate = ""
                quality = quality_bitrate
            if df is None:
                columns = (
                    columns_init
                    + tuple(encoder_stats.keys())
                    + tuple(psnr_dict.keys())
                    + tuple(ssim_dict.keys())
                    + tuple(vmaf_dict.keys())
                    + columns_fini
                )
                df = pd.DataFrame(columns=columns)
            df.loc[len(df.index)] = (
                in_basename,
                label,
                codec,
                resolution,
                width,
                height,
                ref_framerate,
                rcmode,
                quality,
                bitrate,
                preset,
                actual_bitrate,
                *encoder_stats.values(),
                *psnr_dict.values(),
                *ssim_dict.values(),
                *vmaf_dict.values(),
                parameters_csv_str,
            )
    return df


def run_single_enc(
    infile,
    outfile,
    codec,
    resolution,
    quality_bitrate_option,
    quality_bitrate,
    preset,
    rcmode,
    gop_length_frames,
    debug,
):
    if debug > 0:
        print("# [%s] encoding file: %s -> %s" % (codec, infile, outfile))

    # get encoding settings
    enc_tool = "ffmpeg"
    enc_parms = [
        "-y",
    ]
    enc_parms += ["-i", infile]

    enc_env = None
    if CODEC_INFO[codec]["codecname"] == "libsvtav1-raw":
        enc_tool = CODEC_INFO[codec]["binary"]
        enc_parms = ["-i", infile]
        # ~/work/video/av1/svt-av1/Bin/Release/SvtAv1EncApp --rc 1 --lp 1 --tbr 14000 --preset 10 --keyint 600 -i /tmp/rdtest_py_tmp/easy.mp4.ref_1728x2304.y4m --output /tmp/rdtest_py_tmp/foo.mp4.ivf
        if rcmode == "cbr":
            # TODO(chema): use VBR (1) instead of CBR (2) as SvtAv1EncApp is complaining
            # Svt[error]: CBR Rate control is currently not supported for SVT_AV1_PRED_RANDOM_ACCESS, use VBR mode
            # enc_parms += ["--rc", "2"]
            enc_parms += ["--rc", "1"]
            bitrate = quality_bitrate
            enc_parms += ["--tbr", "%s" % bitrate]
        elif rcmode == "crf":
            enc_parms += ["--rc", "0"]
            quality = quality_bitrate
            enc_parms += ["--crf", "%s" % quality]
        enc_parms += ["--preset", "%s" % preset]
        # maximize CPU usage
        enc_parms += ["--lp", "0"]
        # set random access prediction structure
        enc_parms += ["--pred-struct", "2"]
        if gop_length_frames is not None:
            enc_parms += ["--keyint", str(gop_length_frames)]
        enc_parms += ["--output", outfile]

    elif CODEC_INFO[codec]["codecname"] == "mjpeg":
        enc_parms += ["-c:v", CODEC_INFO[codec]["codecname"]]
        # TODO(chema): use bitrate as quality value (2-31)
        assert rcmode == "crf", f"error: mjpeg only defined for {rcmode}"
        quality = quality_bitrate
        enc_parms += ["-q:v", "%s" % quality]
        enc_parms += ["-s", resolution]
    else:
        enc_parms += ["-c:v", CODEC_INFO[codec]["codecname"]]
        if rcmode == "cbr":
            bitrate = quality_bitrate
            # enc_parms += ["-maxrate", "%sk" % bitrate]
            # enc_parms += ["-minrate", "%sk" % bitrate]
            enc_parms += ["-b:v", "%sk" % bitrate]
            # if CODEC_INFO[codec]["codecname"] in ("libx264", "libopenh264", "libx265"):
            #    # set bufsize to 2x the bitrate
            #    bufsize = str(int(bitrate) * 2)
            #    enc_parms += ["-bufsize", bufsize]
        elif rcmode == "crf":
            quality = quality_bitrate
            enc_parms += ["-crf", "%s" % quality]

        if CODEC_INFO[codec]["codecname"] in ("libx264", "libx265"):
            # no b-frames
            enc_parms += ["-bf", "0"]
        # add preset (if available)
        if CODEC_INFO[codec].get("preset-name", None) is not None:
            preset_name = CODEC_INFO[codec].get("preset-name")
            enc_parms += [f"-{preset_name}", preset]
        enc_parms += ["-s", resolution]
        if gop_length_frames is not None:
            enc_parms += ["-g", str(gop_length_frames)]
        for k, v in CODEC_INFO[codec]["parameters"].items():
            enc_parms += ["-%s" % k, str(v)]
        if CODEC_INFO[codec]["codecname"] in ("libaom-av1",):
            # ABR at https://trac.ffmpeg.org/wiki/Encode/AV1
            enc_parms += ["-strict", "experimental"]

    if enc_tool == "ffmpeg":
        # pass audio through
        enc_parms += ["-c:a", "copy"]
        enc_parms += [outfile]

    # run encoder
    cmd = [
        enc_tool,
    ] + enc_parms
    retcode, stdout, stderr, stats = utils.run(
        cmd, env=enc_env, debug=debug, gnu_time=True
    )
    assert retcode == 0, stderr
    return stats


def run_single_dec(infile, outfile, codec, debug):
    if debug > 0:
        print("# [%s] decoding file: %s -> %s" % (codec, infile, outfile))

    # get decoding settings
    dec_tool = "ffmpeg"
    dec_parms = []
    dec_parms += ["-i", infile]
    dec_env = None
    dec_parms += ["-y", outfile]

    # run decoder
    cmd = [
        dec_tool,
    ] + dec_parms
    retcode, stdout, stderr, _ = utils.run(cmd, env=dec_env, debug=debug)
    assert retcode == 0, stderr


def run_single_experiment(
    ref_filename,
    ref_resolution,
    ref_pix_fmt,
    ref_framerate,
    codec,
    resolution,
    quality_bitrate_option,
    quality_bitrate,
    preset,
    rcmode,
    gop_length_frames,
    tmp_dir,
    debug,
    cleanup,
):
    if debug > 0:
        print(
            f"# [run] run_single_experiment codec: {codec} resolution: {resolution} "
            f"{quality_bitrate_option}: {quality_bitrate} rcmode: {rcmode} preset: {preset}"
        )
    ref_basename = os.path.basename(ref_filename)

    # common info for enc, dec, and decs
    gen_basename = ref_basename + f".ref_{ref_resolution}"
    gen_basename += f".codec_{codec}"
    gen_basename += f".resolution_{resolution}"
    gen_basename += f".{quality_bitrate_option}_{quality_bitrate}"
    gen_basename += f".preset_{preset}"
    gen_basename += f".rcmode_{rcmode}"

    # 3. enc: encode copy with encoder
    enc_basename = gen_basename + CODEC_INFO[codec]["extension"]
    enc_filename = os.path.join(tmp_dir, enc_basename)
    encoder_stats = run_single_enc(
        ref_filename,
        enc_filename,
        codec,
        resolution,
        quality_bitrate_option,
        quality_bitrate,
        preset,
        rcmode,
        gop_length_frames,
        debug,
    )

    # 4. dec: decode copy in order to get statistics
    dec_basename = enc_basename + ".y4m"
    dec_filename = os.path.join(tmp_dir, dec_basename)
    run_single_dec(enc_filename, dec_filename, codec, debug)

    # 5. decs: scale the decoded video to the reference resolution and
    # pixel format
    # This is needed to make sure the quality metrics make sense
    decs_basename = dec_basename + ".scaled"
    decs_basename += ".resolution_%s" % ref_resolution
    decs_basename += ".y4m"
    decs_filename = os.path.join(tmp_dir, decs_basename)
    if debug > 0:
        print("# [%s] scaling file: %s -> %s" % (codec, dec_filename, decs_filename))
    ffmpeg_params = [
        "-y",
        "-nostats",
        "-loglevel",
        "0",
        "-i",
        dec_filename,
        "-pix_fmt",
        ref_pix_fmt,
        "-s",
        ref_resolution,
        decs_filename,
    ]
    retcode, stdout, stderr, _ = utils.ffmpeg_run(ffmpeg_params, debug)
    assert retcode == 0, stderr
    # check produced file matches the requirements
    assert ref_resolution == utils.get_resolution(
        decs_filename
    ), "Error: %s must have resolution: %s (is %s)" % (
        decs_filename,
        ref_resolution,
        utils.get_resolution(decs_filename),
    )
    assert ref_pix_fmt == utils.get_pix_fmt(
        decs_filename
    ), "Error: %s must have pix_fmt: %s (is %s)" % (
        decs_filename,
        ref_pix_fmt,
        utils.get_pix_fmt(decs_filename),
    )

    # get quality scores
    psnr_dict = utils.get_psnr(decs_filename, ref_filename, None, debug)
    ssim_dict = utils.get_ssim(decs_filename, ref_filename, None, debug)
    vmaf_dict = utils.get_vmaf(decs_filename, ref_filename, None, debug)

    # get actual bitrate
    actual_bitrate = utils.get_bitrate(enc_filename)

    # clean up experiments files
    if cleanup > 0:
        os.remove(dec_filename)
        os.remove(decs_filename)
    if cleanup > 1:
        os.remove(enc_filename)
    return encoder_stats, actual_bitrate, psnr_dict, ssim_dict, vmaf_dict


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
    parser.add_argument(
        "-d",
        "--debug",
        action="count",
        dest="debug",
        default=default_values["debug"],
        help="Increase verbosity (multiple times for more)",
    )
    parser.add_argument(
        "--quiet",
        action="store_const",
        dest="debug",
        const=-1,
        help="Zero verbosity",
    )
    parser.add_argument(
        "--cleanup",
        action="store_const",
        dest="cleanup",
        const=1,
        default=default_values["cleanup"],
        help="Cleanup Raw Files%s"
        % (" [default]" if default_values["cleanup"] == 1 else ""),
    )
    parser.add_argument(
        "--full-cleanup",
        action="store_const",
        dest="cleanup",
        const=2,
        default=default_values["cleanup"],
        help="Cleanup All Files%s"
        % (" [default]" if default_values["cleanup"] == 2 else ""),
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_const",
        dest="cleanup",
        const=0,
        help="Do Not Cleanup Files%s"
        % (" [default]" if not default_values["cleanup"] == 0 else ""),
    )
    parser.add_argument(
        "--label",
        action="store",
        dest="label",
        default=default_values["label"],
        help="use LABEL to label the experiment",
    )
    parser.add_argument(
        "-s",
        "--resolution",
        action="store",
        dest="ref_res",
        default=default_values["ref_res"],
        help="force RESOLUTION for the raw video",
    )
    parser.add_argument(
        "--pix_fmt",
        action="store",
        dest="ref_pix_fmt",
        default=default_values["ref_pix_fmt"],
        help="force PIX_FMT pix_fmt for the raw video",
    )
    parser.add_argument(
        "--tmp-dir",
        action="store",
        dest="tmp_dir",
        default=default_values["tmp_dir"],
        help="use TMP_DIR tmp dir",
    )
    parser.add_argument(
        "--gop-length",
        action="store",
        dest="gop_length_frames",
        default=default_values["gop_length_frames"],
        help="GoP length (in frames)",
    )
    parser.add_argument(
        "--vmaf-dir",
        action="store",
        dest="vmaf_dir",
        default=default_values["vmaf_dir"],
        help="use VMAF_DIR vmaf dir",
    )
    # list of arguments
    parser.add_argument(
        "--codecs",
        nargs="+",
        dest="codecs",
        default=default_values["codecs"],
        help="use CODECS list (%s)" % list(CODEC_INFO.keys()),
    )
    parser.add_argument(
        "--resolutions",
        nargs="+",
        dest="resolutions",
        default=default_values["resolutions"],
        help="use RESOLUTIONS list",
    )
    parser.add_argument(
        "--bitrates",
        nargs="+",
        dest="bitrates",
        default=default_values["bitrates"],
        help="use BITRATES list",
    )
    parser.add_argument(
        "--qualities",
        nargs="+",
        dest="qualities",
        default=default_values["qualities"],
        help="use QUALITIES list",
    )
    parser.add_argument(
        "--presets",
        nargs="+",
        dest="presets",
        default=default_values["presets"],
        help="use PRESETS list",
    )
    parser.add_argument(
        "--rcmodes",
        nargs="+",
        dest="rcmodes",
        default=default_values["rcmodes"],
        help="use RCMODES list",
    )
    parser.add_argument(
        dest="infile_list",
        type=str,
        nargs="+",
        default=default_values["infile_list"],
        metavar="input-file",
        help="input file",
    )
    parser.add_argument(
        "-o",
        "--outfile",
        dest="outfile",
        type=str,
        default=default_values["outfile"],
        metavar="output-file",
        help="results file",
    )
    # do the parsing
    options = parser.parse_args(argv[1:])
    # post-process list-based arguments
    # support ',' and ' ' to separate list-based options
    for field in (
        "codecs",
        "resolutions",
        "bitrates",
        "rcmodes",
        "qualities",
        "presets",
    ):
        if len(vars(options)[field]) == 1:
            for sep in (",", " "):
                parameter = vars(options)[field][0]
                if parameter is None:
                    continue
                elif sep in parameter:
                    vars(options)[field] = parameter.split(sep)
    # check valid values in options.codecs
    if not all(c in CODEC_INFO.keys() for c in options.codecs):
        print(
            "# error: invalid codec(s): %r supported_codecs: %r"
            % (
                [c for c in options.codecs if c not in CODEC_INFO.keys()],
                list(CODEC_INFO.keys()),
            )
        )
        sys.exit(-1)
    # check valid values in options.resolutions
    if not all((r is None or "x" in r) for r in options.resolutions):
        print(
            "# error: invalid resolution(s): %r"
            % ([r for r in options.resolutions if "x" not in r])
        )
        sys.exit(-1)
    # check valid values in options.bitrates
    if not all((isinstance(b, int) or b.isnumeric()) for b in options.bitrates):
        print(
            "# error: invalid bitrate(s): %r"
            % (
                [
                    b
                    for b in options.bitrates
                    if not (isinstance(b, int) or b.isnumeric())
                ]
            )
        )
        sys.exit(-1)
    # check valid values in options.rcmodes
    if not all(r in DEFAULT_RCMODES for r in options.rcmodes):
        print(
            "# error: invalid rcmode(s): %r supported_rcmodes: %r"
            % (
                [r for r in options.rcmodes if r not in DEFAULT_RCMODES],
                DEFAULT_RCMODES,
            )
        )
        sys.exit(-1)
    return options


def main(argv):
    # parse options
    options = get_options(argv)
    # get infile/outfile
    assert options.outfile != "-"
    # print results
    if options.debug > 0:
        print(options)
    # do something
    run_experiment(options)


if __name__ == "__main__":
    # at least the CLI program name: (CLI) execution
    main(sys.argv)
