#!/usr/bin/env python3

"""rdimage.py module description."""

import argparse
import functools
import glob
import os
import os.path
import pathlib
import sys

import utils


CODEC_INFO = {
    "jpeg/libjpeg-turbo": {
        "format": "jpeg",
        "codec": "libjpeg-turbo",
        "encode_command": "cjpeg -quality {jpeg_quality} -outfile {outfile} {infile}",
        "parameters": ["jpeg_quality"],
        "input_format": ".ppm",
        "output_format": ".jpeg",
    },
    "jxl/libjxl": {
        "format": "jxl",
        "codec": "libjxl",
        "encode_command": "cjxl {infile} {outfile} --quality {jxl_quality}",
        "parameters": ["jxl_quality"],
        "input_format": ".ppm",
        "output_format": ".jxl",
        "decode_command": "djxl {infile} {outfile}",
    },
    "heic/x265": {
        "format": "heic",
        "codec": "x265",
        "encode_command": "heif-enc -e x265 -p quality={heic_quality} -p preset={heic_preset} -o {outfile} {infile}",
        "parameters": ["heic_quality", "heic_preset"],
        "input_format": ".y4m",
        "output_format": ".heic",
        "decode_command": "heif-convert {infile} {outfile}",
    },
    "avif/libaom": {
        "format": "avif",
        "codec": "libaom",
        "encode_command": "avifenc -c aom -s {avif_speed} -o {outfile} {infile}",
        "parameters": ["avif_speed"],
        "input_format": ".y4m",
        "output_format": ".avif",
    },
    "avif/svt": {
        "format": "avif",
        "codec": "svt",
        "encode_command": "avifenc -c svt -s {avif_speed} -o {outfile} {infile}",
        "parameters": ["avif_speed"],
        "input_format": ".y4m",
        "output_format": ".avif",
    },
}
JPEG_QUALITY_LIST = list(range(0, 101, 20))
JXL_QUALITY_LIST = list(range(10, 101, 20))
HEIC_QUALITY_LIST = list(range(0, 101, 20))
HEIC_PRESET_LIST = [
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
]
AVIF_SPEED_LIST = list(range(0, 11, 2))

default_values = {
    "debug": 0,
    "nruns": 10,
    "cleanup": True,
    "tmp_dir": "/tmp/",
    "vmaf_dir": "/tmp/",
    "codecs": list(CODEC_INFO.keys()),
    "jpeg_quality": JPEG_QUALITY_LIST,
    "jxl_quality": JXL_QUALITY_LIST,
    "heic_quality": HEIC_QUALITY_LIST,
    "heic_preset": HEIC_PRESET_LIST,
    "avif_speed": AVIF_SPEED_LIST,
    "indir": None,
    "outfile": None,
}


# https://stackabuse.com/python-how-to-flatten-list-of-lists/
def flatten(the_list):
    if len(the_list) == 0:
        return the_list
    if isinstance(the_list[0], list) or isinstance(the_list[0], tuple):
        return flatten(the_list[0]) + flatten(the_list[1:])
    return the_list[:1] + flatten(the_list[1:])


def run_experiment(options):
    # check all software is ok
    utils.check_software(options.debug)

    # prepare output directory
    pathlib.Path(options.tmp_dir).mkdir(parents=True, exist_ok=True)

    # 1. get list of input files
    infile_list = []
    for fname in glob.glob(f"{options.indir}/*"):
        # check whether the file is a media file
        try:
            resolution = utils.get_resolution(fname)
        except:
            if options.debug > 0:
                print(f"warning: skipping {fname} as no-media file")
            continue
        assert "x" in resolution, f"error: invalid resolution: {resolution}"
        infile_list.append(fname)

    # 2. get all the possible combinations of input parameters
    parameter_name_list = [
        "codec",
    ] + list(set(flatten([v["parameters"] for v in CODEC_INFO.values()])))
    parameter_val_list = []
    for codec in options.codecs:
        tmp_parameter_val_list = [
            codec,
        ]
        # develop all the possible combinations of parameters
        for parameter in parameter_name_list[1:]:
            value_list = (
                vars(options)[parameter]
                if parameter in CODEC_INFO[codec]["parameters"]
                else [
                    "",
                ]
            )
            tmp_parameter_val_list = list(
                [x, y] for x in tmp_parameter_val_list for y in value_list
            )
        # flatten the resulting parameter list
        tmp_parameter_val_list = [flatten(l) for l in tmp_parameter_val_list]
        parameter_val_list += tmp_parameter_val_list

    # 3. run each experiment
    results = []
    for orig_infile in infile_list:
        for parameter_vals in parameter_val_list:
            parameter_dict = {k: v for k, v in zip(parameter_name_list, parameter_vals)}
            codec = parameter_dict["codec"]
            # 3.0. prepare the encode command
            # adapt input file to the encoder requirements
            input_format = CODEC_INFO[codec]["input_format"]
            infile_format = os.path.splitext(os.path.basename(orig_infile))[1]
            if input_format == infile_format:
                infile = orig_infile
            else:
                infile = os.path.join(
                    options.tmp_dir,
                    os.path.splitext(os.path.basename(orig_infile))[0] + input_format,
                )
                ffmpeg_params = ["-y", "-i", orig_infile, infile]
                retcode, stdout, stderr, _ = utils.ffmpeg_run(
                    ffmpeg_params, options.debug
                )
                assert (
                    retcode == 0
                ), f"error converting {orig_infile} to {infile}\nstdout: {stdout}\nstderr: {stderr}"
            # get the output file with the right type
            postfix = ""
            for name, val in zip(parameter_name_list, parameter_vals):
                if val != "":
                    # parameter is being used
                    postfix += f".{name}_{val}"
            # escape postfix
            postfix = postfix.replace("/", "_")
            output_format = CODEC_INFO[codec]["output_format"]
            outfile = os.path.join(
                options.tmp_dir,
                os.path.splitext(os.path.basename(infile))[0] + postfix + output_format,
            )
            cmd = CODEC_INFO[codec]["encode_command"].format(
                **parameter_dict, infile=infile, outfile=outfile
            )
            # 3.1. run the encode command
            # TODO(chema): implement nruns
            retcode, stdout, stderr, duration = utils.run(cmd, debug=options.debug)
            assert (
                retcode == 0
            ), f"error encoding video file\ncmd: {cmd}\nstdout: {stdout}\nstderr: {stderr}"
            resolution = utils.get_resolution(infile)
            # outresolution = utils.get_resolution(outfile)
            # assert resolution == outresolution, f"error: resolution change\n  {infile}: {resolution}\n  {outfile}: {outresolution}"
            infilesize = os.path.getsize(infile)
            outfilesize = os.path.getsize(outfile)
            numpixels = functools.reduce(
                int.__mul__, [int(val) for val in resolution.split("x")]
            )
            inbpp = (8 * infilesize) / numpixels
            outbpp = (8 * outfilesize) / numpixels
            ratiobpp = outbpp / inbpp
            # 3.2. decode the file (if needed)
            decode_command = CODEC_INFO[codec].get("decode_command", None)
            if decode_command is None:
                distorted_infile = outfile
            else:
                distorted_infile = outfile + input_format
                cmd = decode_command.format(infile=outfile, outfile=distorted_infile)
                retcode, stdout, stderr, _ = utils.run(cmd, debug=options.debug)
                assert (
                    retcode == 0
                ), f"error decoding video file\ncmd: {cmd}\nstdout: {stdout}\nstderr: {stderr}"
            # 3.3. calculate the quality score(s)
            psnr = utils.get_psnr(distorted_infile, infile, None, options.debug)
            ssim = utils.get_ssim(distorted_infile, infile, None, options.debug)
            vmaf = utils.get_vmaf(distorted_infile, infile, None, options.debug)
            # 3.4. store results
            local_results = (
                [codec, os.path.basename(infile), resolution]
                + parameter_vals[1:]
                + [
                    infilesize,
                    inbpp,
                    outfilesize,
                    outbpp,
                    ratiobpp,
                    duration,
                    psnr,
                    ssim,
                    vmaf,
                ]
            )
            results.append(local_results)
    # 4. dump results
    with open(options.outfile, "w+") as fout:
        # run the list of encodings
        header = (
            "codec,infile,resolution,"
            + ",".join(parameter_name_list[1:])
            + ",infilesize,inbpp,outfilesize,outbpp,ratiobpp,duration,psnr,ssim,vmaf\n"
        )
        fout.write(header)
        for local_results in results:
            fout.write(",".join(str(item) for item in local_results) + "\n")


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
        "--nruns",
        action="store",
        dest="nruns",
        default=default_values["nruns"],
        help="number of runs for each experiment",
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
        "--tmp-dir",
        action="store",
        dest="tmp_dir",
        default=default_values["tmp_dir"],
        help="use TMP_DIR tmp dir",
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
        "--jpeg-quality",
        nargs="+",
        dest="jpeg_quality",
        default=default_values["jpeg_quality"],
        help="use QUALITY list for jpeg",
    )
    parser.add_argument(
        "--jxl-quality",
        nargs="+",
        dest="jxl_quality",
        default=default_values["jxl_quality"],
        help="use QUALITY list for jxl",
    )
    parser.add_argument(
        "--heic-quality",
        nargs="+",
        dest="heic_quality",
        default=default_values["heic_quality"],
        help="use QUALITY list for heic",
    )
    parser.add_argument(
        "--heic-preset",
        nargs="+",
        dest="heic_preset",
        default=default_values["heic_preset"],
        help="use PRESET list for heic",
    )
    parser.add_argument(
        "--avif-speed",
        nargs="+",
        dest="avif_speed",
        default=default_values["avif_speed"],
        help="use SPEED list for avif",
    )
    # input/output parameters
    parser.add_argument(
        "indir",
        type=str,
        default=default_values["indir"],
        metavar="input-directory",
        help="input directory",
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
    for field in (
        "codecs",
        "jpeg_quality",
        "jxl_quality",
        "heic_quality",
        "heic_preset",
        "avif_speed",
    ):
        for sep in (",", " "):
            if len(vars(options)[field]) == 1 and sep in vars(options)[field][0]:
                vars(options)[field] = vars(options)[field][0].split(sep)
    # check valid values in options.codecs
    if not all(c in CODEC_INFO.keys() for c in options.codecs):
        print(
            "# error: invalid codec(s): %r supported_codecs: %r"
            % (
                [c for c in options.codecs if c not in list(CODEC_INFO.keys())],
                list(CODEC_INFO.keys()),
            )
        )
        sys.exit(-1)
    # check valid values in heic_preset
    if not all(c in HEIC_PRESET_LIST for c in options.heic_preset):
        print(
            "# error: invalid heic_preset(s): %r supported_heic_preset: %r"
            % (
                [c for c in options.heic_preset if c not in HEIC_PRESET_LIST],
                list(HEIC_PRESET_LIST),
            )
        )
        sys.exit(-1)
    return options


def main(argv):
    # parse options
    options = get_options(argv)
    # get outfile
    assert options.outfile != "-"
    # print results
    if options.debug > 0:
        print(options)
    # do something
    run_experiment(options)


if __name__ == "__main__":
    # at least the CLI program name: (CLI) execution
    main(sys.argv)
