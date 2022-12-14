#!/usr/bin/env python3

"""rdtest.py module description."""

# Invalid name "get_info" (should match ^_?[A-Z][a-zA-Z0-9]*$)
# pylint: disable-msg=C0103

import argparse
import os
import pathlib
import sys

import utils


# LCEVC_ENC_DIR=~/work/lcevc/src/FB-Release-20200203/enc_ffmpeg_linux_ubuntu_LC/ LCEVC_ENCODER=ffmpeg LCEVC_DEC_DIR=~/work/lcevc/src/FB-Release-20200203/ffmpeg_dec/ LCEVC_DECODER=ffmpeg-ER-decoder ~/proj/rdtest/rdtest.py ~/dropbox/fb/video/codec_test_material/Johnny_1280x720_60.y4m --tmp-dir /home/root/tmp/rdtest_py_tmp -ddd /tmp/results.drop_20200203.johnny.txt --codecs "lcevc-x264 x264" --bitrates '100000' --resolutions '864x480'  # noqa: E501

CODEC_INFO = {
    "mjpeg": {"codecname": "mjpeg", "extension": ".mp4", "parameters": {}},
    "lcevc-x264": {"codecname": "pplusenc_x264", "extension": ".mp4", "parameters": {}},
    "x264": {"codecname": "libx264", "extension": ".mp4", "parameters": {}},
    "openh264": {"codecname": "libopenh264", "extension": ".mp4", "parameters": {}},
    "x265": {"codecname": "libx265", "extension": ".mp4", "parameters": {}},
    "vp8": {
        "codecname": "vp8",
        "extension": ".webm",
        "parameters": {
            # quality parameters
            "quality": "realtime",
        },
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
    },
    "libaom-av1": {
        "codecname": "libaom-av1",
        "extension": ".mp4",
        "parameters": {
            # ABR at https://trac.ffmpeg.org/wiki/Encode/AV1
            # this should reduce the encoding time to manageable levels
            "cpu-used": 5,
        },
    },
}

# resolution set 1
RESOLUTIONS = [
    "640x360",  # 200-437kbps
    "480x272",  # actually 480x270 100-200kbps
    "320x160",  # < 100kbps
]

# resolution set 2
RESOLUTIONS = [
    "1280x720",
    "864x480",
    "640x360",
    "432x240",
    "216x120",
    # '160x90',
]

# Notes:
# * lcevc-x264 encoder barfs when asked to encode a '160x90' file
# * 720p is not a realistic encoding resolution in mobile due to
# performance issues
BITRATES = [
    2500,
    1000,
    560,
    280,
    140,
    70,
    35,
]

RCMODES = [
    "cbr",
    "crf",
]

# TODO(jblome): fix lcevc-x264 CRF mode parameters
RCMODES = [
    "cbr",
]


default_values = {
    "debug": 0,
    "cleanup": True,
    "ref_res": None,
    "ref_pix_fmt": "yuv420p",
    "vmaf_dir": "/tmp/",
    "tmp_dir": "/tmp/",
    "gop_length_frames": 600,
    "codecs": CODEC_INFO.keys(),
    "resolutions": RESOLUTIONS,
    "bitrates": BITRATES,
    "rcmodes": RCMODES,
    "infile": None,
    "outfile": None,
}


def run_experiment(options):
    # check all software is ok
    utils.check_software(options.debug)

    # prepare output directory
    pathlib.Path(options.tmp_dir).mkdir(parents=True, exist_ok=True)

    # 1. in: get infile information
    in_filename = options.infile
    if options.debug > 0:
        print("# [run] parsing file: %s" % (in_filename))
    assert os.access(options.infile, os.R_OK), "file %s is not readable" % in_filename
    in_basename = os.path.basename(in_filename)
    in_resolution = utils.get_resolution(in_filename)
    in_framerate = utils.get_framerate(in_filename)

    # 2. ref: decode the original file into a raw file
    ref_basename = f"{in_basename}.ref_{in_resolution}.y4m"
    if options.debug > 0:
        print(f"# [run] normalize file: {in_filename} -> {ref_basename}")
    ref_filename = os.path.join(options.tmp_dir, ref_basename)
    ref_resolution = in_resolution if options.ref_res is None else options.ref_res
    ref_framerate = in_framerate
    ref_pix_fmt = options.ref_pix_fmt
    ffmpeg_params = [
        "-y",
        "-i",
        options.infile,
        "-s",
        ref_resolution,
        "-pix_fmt",
        ref_pix_fmt,
        ref_filename,
    ]
    retcode, stdout, stderr, _ = utils.ffmpeg_run(ffmpeg_params, options.debug)
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

    with open(options.outfile, "w+") as fout:
        # run the list of encodings
        fout.write(
            "in_filename,codec,resolution,width,height,rcmode,"
            "bitrate,encoder_duration,actual_bitrate,psnr,ssim,"
            "vmaf,parameters\n"
        )
        for codec in options.codecs:
            # open outfile
            parameters_csv_str = ""
            for k, v in CODEC_INFO[codec]["parameters"].items():
                parameters_csv_str += "%s=%s;" % (k, str(v))
            for resolution in options.resolutions:
                for bitrate in options.bitrates:
                    for rcmode in options.rcmodes:
                        (
                            encoder_duration,
                            actual_bitrate,
                            psnr,
                            ssim,
                            vmaf,
                        ) = run_single_experiment(
                            ref_filename,
                            ref_resolution,
                            ref_pix_fmt,
                            ref_framerate,
                            codec,
                            resolution,
                            bitrate,
                            rcmode,
                            options.gop_length_frames,
                            options.tmp_dir,
                            options.debug,
                            options.cleanup,
                        )
                        width, height = resolution.split("x")
                        fout.write(
                            "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,"
                            "%s\n"
                            % (
                                in_basename,
                                codec,
                                resolution,
                                width,
                                height,
                                rcmode,
                                bitrate,
                                encoder_duration,
                                actual_bitrate,
                                psnr,
                                ssim,
                                vmaf,
                                parameters_csv_str,
                            )
                        )


def get_lcevc_enc_parms(resolution, bitrate, rcmode, gop_length_frames):
    enc_parms = []
    enc_env = None
    if "LCEVC_ENC_DIR" in os.environ:
        lcevc_enc_dir = os.environ["LCEVC_ENC_DIR"]
        enc_tool = os.path.join(
            lcevc_enc_dir, os.environ.get("LCEVC_ENCODER", "ffmpeg")
        )
        # check encoder tool is executable
        assert os.path.isfile(enc_tool) and os.access(enc_tool, os.X_OK), (
            "Error: %s must be executable" % enc_tool
        )
        enc_env = {
            "LD_LIBRARY_PATH": "%s:%s" % (lcevc_enc_dir, os.environ["LD_LIBRARY_PATH"]),
        }
    enc_parms += ["-c:v", "pplusenc_x264"]
    enc_parms += ["-base_encoder", "x264"]
    # no b-frames
    enc_parms += ["-bf", "0"]
    # medium preset for x264 makes more sense for mobile
    enc_parms += ["-preset", "medium"]
    # lcevc-only parameters
    if rcmode == "cbr":
        mode = ""
        # no b-frames
        # mode += 'bf=0;'
        # medium preset for x264 makes more sense for mobile
        mode += "preset=medium;"
        # current lcevc overhead is 13 kbps
        bitrate = str(int(bitrate) - 13)
        mode += "bitrate=%s;" % bitrate
        # TODO(chema): this should be settable (?)
        # mode += 'rc_pcrf_base_rc_mode=%s;' % rcmode
        # mode += 'rc_pcrf_base_rc_mode=crf;'
        # internal setting (best setting for low resolutions)
        # mode += 'rc_pcrf_sw_loq1=32768;'
        # GoP length (default is 2x fps)
        # mode += 'rc_pcrf_gop_length=%s;' % gop_length_frames
        # upsampling
        mode += "encoding_upsample=cubic;"
        # ipp mode
        mode += "rc_pcrf_ipp_mode=1;"
    elif rcmode == "cfr":
        # TODO(jblome): fix lcevc-x264 CFR mode parameters
        AssertionError("# error: cfr needs better parameters")
    else:
        AssertionError("# error unsupported rcmode: %s" % rcmode)
    enc_parms += ["-eil_params", mode]
    enc_parms += ["-s", resolution, "-g", str(gop_length_frames)]
    return enc_parms, enc_env


def run_single_enc(
    in_filename, outfile, codec, resolution, bitrate, rcmode, gop_length_frames, debug
):
    if debug > 0:
        print("# [%s] encoding file: %s -> %s" % (codec, in_filename, outfile))

    # get encoding settings
    enc_tool = "ffmpeg"
    enc_parms = [
        "-y",
    ]
    enc_parms += ["-i", in_filename]

    enc_env = None
    if CODEC_INFO[codec]["codecname"] == "mjpeg":
        enc_parms += ["-c:v", CODEC_INFO[codec]["codecname"]]
        # TODO(chema): use bitrate as quality value (2-31)
        enc_parms += ["-q:v", "%s" % bitrate]
        enc_parms += ["-s", resolution]
    elif CODEC_INFO[codec]["codecname"] == "pplusenc_x264":
        enc_parms2, enc_env = get_lcevc_enc_parms(
            resolution, bitrate, rcmode, gop_length_frames
        )
        enc_parms.append(enc_parms2)
    else:
        enc_parms += ["-c:v", CODEC_INFO[codec]["codecname"]]
        enc_parms += ["-maxrate", "%sk" % bitrate]
        enc_parms += ["-minrate", "%sk" % bitrate]
        enc_parms += ["-b:v", "%sk" % bitrate]
        if CODEC_INFO[codec]["codecname"] in ("libx264", "libx265"):
            # no b-frames
            enc_parms += ["-bf", "0"]
        if CODEC_INFO[codec]["codecname"] in ("libx264", "libopenh264", "libx265"):
            # set bufsize to 2x the bitrate
            bufsize = str(int(bitrate) * 2)
            enc_parms += ["-bufsize", bufsize]
        enc_parms += ["-s", resolution]
        enc_parms += ["-g", str(gop_length_frames)]
        for k, v in CODEC_INFO[codec]["parameters"].items():
            enc_parms += ["-%s" % k, str(v)]
        if CODEC_INFO[codec]["codecname"] in ("libaom-av1",):
            # ABR at https://trac.ffmpeg.org/wiki/Encode/AV1
            enc_parms += ["-strict", "experimental"]

    # pass audio through
    enc_parms += ["-c:a", "copy"]
    enc_parms += [outfile]

    # run encoder
    cmd = [
        enc_tool,
    ] + enc_parms
    retcode, stdout, stderr, other = utils.run(cmd, env=enc_env, debug=debug)
    assert retcode == 0, stderr
    return other["time_diff"]


def run_single_dec(infile, outfile, codec, debug):
    if debug > 0:
        print("# [%s] decoding file: %s -> %s" % (codec, infile, outfile))

    # get decoding settings
    dec_tool = "ffmpeg"
    dec_parms = []
    if CODEC_INFO[codec]["codecname"] == "pplusenc_x264":
        dec_parms += ["-vcodec", "lcevc_h264"]
    dec_parms += ["-i", infile]
    dec_env = None
    if CODEC_INFO[codec]["codecname"] == "pplusenc_x264":
        dec_env = {}
        if "LCEVC_DEC_DIR" in os.environ:
            lcevc_dec_dir = os.environ["LCEVC_DEC_DIR"]
            dec_tool = os.path.join(
                lcevc_dec_dir, os.environ.get("LCEVC_DECODER", "ffmpeg")
            )
            # check decoder tool is executable
            assert os.path.isfile(dec_tool) and os.access(dec_tool, os.X_OK), (
                "Error: %s must be executable" % dec_tool
            )
            dec_env["LD_LIBRARY_PATH"] = "%s:%s" % (
                lcevc_dec_dir,
                os.environ["LD_LIBRARY_PATH"],
            )
        if "PPlusDec2Ref" in dec_tool:
            dec_parms += ["--no-display", "-o", outfile]
        else:
            dec_parms += ["-y", outfile]
        # perseus decoder requires X context
        dec_env["DISPLAY"] = ":0"
    else:
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
    bitrate,
    rcmode,
    gop_length_frames,
    tmp_dir,
    debug,
    cleanup,
):
    if debug > 0:
        print(
            "# [run] run_single_experiment codec: %s resolution: %s "
            "bitrate: %s rmcode: %s" % (codec, resolution, bitrate, rcmode)
        )
    ref_basename = os.path.basename(ref_filename)

    # common info for enc, dec, and decs
    gen_basename = ref_basename + ".ref_%s" % ref_resolution
    gen_basename += ".codec_%s" % codec
    gen_basename += ".resolution_%s" % resolution
    gen_basename += ".bitrate_%s" % bitrate
    gen_basename += ".rcmode_%s" % rcmode

    # 3. enc: encode copy with encoder
    enc_basename = gen_basename + CODEC_INFO[codec]["extension"]
    enc_filename = os.path.join(tmp_dir, enc_basename)
    encoder_duration = run_single_enc(
        ref_filename,
        enc_filename,
        codec,
        resolution,
        bitrate,
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
    psnr = utils.get_psnr(decs_filename, ref_filename, None, debug)
    ssim = utils.get_ssim(decs_filename, ref_filename, None, debug)
    vmaf = utils.get_vmaf(decs_filename, ref_filename, None, debug)

    # get actual bitrate
    actual_bitrate = utils.get_bitrate(enc_filename)

    # clean up experiments files
    if cleanup:
        os.remove(enc_filename)
        os.remove(dec_filename)
        os.remove(decs_filename)
    return encoder_duration, actual_bitrate, psnr, ssim, vmaf


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
        const=True,
        default=default_values["cleanup"],
        help="Cleanup Files%s" % (" [default]" if default_values["cleanup"] else ""),
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_const",
        dest="cleanup",
        const=False,
        help="Do Not Cleanup Files%s"
        % (" [default]" if not default_values["cleanup"] else ""),
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
        "--rcmodes",
        nargs="+",
        dest="rcmodes",
        default=default_values["rcmodes"],
        help="use RCMODES list",
    )
    parser.add_argument(
        "infile",
        type=str,
        default=default_values["infile"],
        metavar="input-file",
        help="input file",
    )
    parser.add_argument(
        "outfile",
        type=str,
        default=default_values["outfile"],
        metavar="output-file",
        help="results file",
    )
    # do the parsing
    options = parser.parse_args(argv[1:])
    # post-process list-based arguments
    # support ',' and ' ' to separate list-based options
    for field in ("codecs", "resolutions", "bitrates", "rcmodes"):
        for sep in (",", " "):
            if len(vars(options)[field]) == 1 and sep in vars(options)[field][0]:
                vars(options)[field] = vars(options)[field][0].split(sep)
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
    if not all("x" in r for r in options.resolutions):
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
    if not all(r in RCMODES for r in options.rcmodes):
        print(
            "# error: invalid rcmode(s): %r supported_rcmodes: %r"
            % ([r for r in options.rcmodes if r not in RCMODES], RCMODES)
        )
        sys.exit(-1)
    return options


def main(argv):
    # parse options
    options = get_options(argv)
    # get infile/outfile
    assert options.infile != "-"
    assert options.outfile != "-"
    # print results
    if options.debug > 0:
        print(options)
    # do something
    run_experiment(options)


if __name__ == "__main__":
    # at least the CLI program name: (CLI) execution
    main(sys.argv)
