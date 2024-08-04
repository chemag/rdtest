#!/usr/bin/env python3

"""utils.py module description."""

import json
import numpy as np
import os
import re
import subprocess
import sys
import tempfile
import time

PERCENTILE_LIST = (0, 5, 10, 25, 75, 90, 95, 100)

VMAF_MODEL = "/usr/share/model/vmaf_4k_v0.6.1.json"
VMAF_MODEL = "/usr/share/model/vmaf_v0.6.1.json"
VMAF_MODEL = "/usr/share/model/vmaf_v0.6.1neg.json"


# https://gitlab.com/AOMediaCodec/avm/-/blob/main/tools/convexhull_framework/src/Utils.py#L426
def parse_perf_stats(perfstats_filename):
    enc_time = 0
    enc_instr = 0
    enc_cycles = 0
    flog = open(perfstats_filename, "r")
    for line in flog:
        m = re.search(r"(\S+)\s+instructions", line)
        if m:
            enc_instr = int(m.group(1).replace(",", ""))
        m = re.search(r"(\S+)\s+cycles:u", line)
        if m:
            enc_cycles = int(m.group(1).replace(",", ""))
        m = re.search(r"(\S+)\s+seconds\s+user", line)
        if m:
            enc_time = float(m.group(1))
    perf_stats = {
        "time_perf": enc_time,
        "instr": enc_instr,
        "cycles": enc_cycles,
    }
    return perf_stats


def run(command, **kwargs):
    debug = kwargs.get("debug", 0)
    dry_run = kwargs.get("dry_run", False)
    env = kwargs.get("env", None)
    stdin = subprocess.PIPE if kwargs.get("stdin", False) else None
    bufsize = kwargs.get("bufsize", 0)
    universal_newlines = kwargs.get("universal_newlines", False)
    default_close_fds = True if sys.platform == "linux2" else False
    close_fds = kwargs.get("close_fds", default_close_fds)
    shell = kwargs.get("shell", True)
    get_perf_stats = kwargs.get("get_perf_stats", False)
    if type(command) is list:
        command = subprocess.list2cmdline(command)
    if debug > 0:
        print(f"running $ {command}")
    if dry_run:
        return 0, b"stdout", b"stderr"
    if get_perf_stats:
        _, perfstats_filename = tempfile.mkstemp(dir=tempfile.gettempdir())
        command = f"3>{perfstats_filename} perf stat --log-fd 3 {command}"
    ts1 = time.time()
    p = subprocess.Popen(  # noqa: E501
        command,
        stdin=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=bufsize,
        universal_newlines=universal_newlines,
        env=env,
        close_fds=close_fds,
        shell=shell,
    )
    # wait for the command to terminate
    if stdin is not None:
        out, err = p.communicate(stdin)
    else:
        out, err = p.communicate()
    returncode = p.returncode
    ts2 = time.time()
    other = {
        "time_diff": ts2 - ts1,
    }
    if get_perf_stats:
        perf_stats = parse_perf_stats(perfstats_filename)
        other.update(perf_stats)
    # clean up
    del p
    # return results
    return returncode, out, err, other


def ffprobe_run(stream_info, infile, debug=0):
    cmd = ["ffprobe", "-v", "0", "-of", "csv=s=x:p=0", "-select_streams", "v:0"]
    cmd += ["-show_entries", stream_info]
    cmd += [
        infile,
    ]
    retcode, stdout, stderr, _ = run(cmd, debug=debug)
    assert retcode == 0, f"error running {cmd}\nout: {stdout}\nerr: {stderr}"
    return stdout.decode("ascii").strip()


def ffmpeg_run(params, debug=0):
    cmd = [
        "ffmpeg",
        "-hide_banner",
    ] + params
    return run(cmd, debug=debug)


def get_resolution(infile, debug=0):
    return ffprobe_run("stream=width,height", infile, debug)


def get_pix_fmt(infile, debug=0):
    return ffprobe_run("stream=pix_fmt", infile, debug)


def get_framerate(infile, debug=0):
    return ffprobe_run("stream=r_frame_rate", infile, debug)


def get_duration(infile, debug=0):
    # "stream=duration" fails on webm files
    return ffprobe_run("format=duration", infile, debug)


# returns bitrate in kbps
def get_bitrate(infile):
    size_bytes = os.stat(infile).st_size
    in_duration_secs = get_duration(infile)
    actual_bitrate = 8.0 * size_bytes / float(in_duration_secs)
    return actual_bitrate


def get_psnr(distorted_filename, ref_filename, psnr_log, debug):
    psnr_log = (
        psnr_log
        if psnr_log is not None
        else tempfile.NamedTemporaryFile(prefix="psnr.", suffix=".log").name
    )
    ffmpeg_params = [
        "-i",
        distorted_filename,
        "-i",
        ref_filename,
        "-filter_complex",
        f"psnr=stats_file={psnr_log}",
        "-f",
        "null",
        "-",
    ]
    retcode, stdout, stderr, _ = ffmpeg_run(ffmpeg_params, debug)
    return parse_psnr_log(psnr_log)


def parse_psnr_log(psnr_log):
    """Parse log/output files and return quality score"""
    with open(psnr_log) as fd:
        data = fd.read()
    # n:1 mse_avg:2.59 mse_y:3.23 mse_u:1.61 mse_v:1.03 psnr_avg:44.00 psnr_y:43.04 psnr_u:46.07 psnr_v:48.02
    # n:2 mse_avg:3.77 mse_y:4.87 mse_u:1.96 mse_v:1.20 psnr_avg:42.36 psnr_y:41.25 psnr_u:45.22 psnr_v:47.35
    psnr_values = []
    for line in data.splitlines():
        # break line in k:v strings
        line_items = list(item for item in line.split(" ") if ":" in item)
        psnr_values.append(
            {item.split(":")[0]: item.split(":")[1] for item in line_items}
        )
    psnr_y_list = np.array(list(float(item["psnr_y"]) for item in psnr_values))
    psnr_u_list = np.array(list(float(item["psnr_u"]) for item in psnr_values))
    psnr_v_list = np.array(list(float(item["psnr_v"]) for item in psnr_values))
    psnr_dict = {
        "y_mean": psnr_y_list.mean(),
        "u_mean": psnr_u_list.mean(),
        "v_mean": psnr_v_list.mean(),
    }
    # add some percentiles
    psnr_dict.update(
        {
            f"y_p{percentile}": np.percentile(psnr_y_list, percentile)
            for percentile in PERCENTILE_LIST
        }
    )
    psnr_dict.update(
        {
            f"u_p{percentile}": np.percentile(psnr_u_list, percentile)
            for percentile in PERCENTILE_LIST
        }
    )
    psnr_dict.update(
        {
            f"v_p{percentile}": np.percentile(psnr_v_list, percentile)
            for percentile in PERCENTILE_LIST
        }
    )
    return psnr_dict


def get_ssim(distorted_filename, ref_filename, ssim_log, debug):
    ssim_log = (
        ssim_log
        if ssim_log is not None
        else tempfile.NamedTemporaryFile(prefix="ssim.", suffix=".log").name
    )
    ffmpeg_params = [
        "-i",
        distorted_filename,
        "-i",
        ref_filename,
        "-filter_complex",
        f"ssim=stats_file={ssim_log}",
        "-f",
        "null",
        "-",
    ]
    retcode, stdout, stderr, _ = ffmpeg_run(ffmpeg_params, debug)
    return parse_ssim_log(ssim_log)


def parse_ssim_log(ssim_log):
    """Parse log/output files and return quality score"""
    with open(ssim_log) as fd:
        data = fd.read()
    # n:1 Y:0.985329 U:0.982885 V:0.985790 All:0.984998 (18.238620)
    # n:2 Y:0.979854 U:0.979630 V:0.983818 All:0.980478 (17.094663)
    ssim_values = []
    for line in data.splitlines():
        # break line in k:v strings
        line_items = list(item for item in line.split(" ") if ":" in item)
        ssim_values.append(
            {item.split(":")[0]: item.split(":")[1] for item in line_items}
        )
    ssim_y_list = np.array(list(float(item["Y"]) for item in ssim_values))
    ssim_u_list = np.array(list(float(item["U"]) for item in ssim_values))
    ssim_v_list = np.array(list(float(item["V"]) for item in ssim_values))
    ssim_dict = {
        "y_mean": ssim_y_list.mean(),
        "u_mean": ssim_u_list.mean(),
        "v_mean": ssim_v_list.mean(),
    }
    # add some percentiles
    ssim_dict.update(
        {
            f"y_p{percentile}": np.percentile(ssim_y_list, percentile)
            for percentile in PERCENTILE_LIST
        }
    )
    ssim_dict.update(
        {
            f"u_p{percentile}": np.percentile(ssim_u_list, percentile)
            for percentile in PERCENTILE_LIST
        }
    )
    ssim_dict.update(
        {
            f"v_p{percentile}": np.percentile(ssim_v_list, percentile)
            for percentile in PERCENTILE_LIST
        }
    )
    return ssim_dict


def ffmpeg_supports_libvmaf(debug):
    libvmaf_support = False
    ffmpeg_params = [
        "-filters",
    ]
    retcode, stdout, stderr, _ = ffmpeg_run(ffmpeg_params, debug)
    assert retcode == 0, stderr
    for line in stdout.decode("ascii").splitlines():
        if "libvmaf" in line and "Calculate the VMAF" in line:
            libvmaf_support = True
    return libvmaf_support


def check_software(debug):
    # ensure ffmpeg supports libvmaf
    libvmaf_support = ffmpeg_supports_libvmaf(debug)
    assert libvmaf_support, "error: ffmpeg does not support vmaf"


def get_vmaf(distorted_filename, ref_filename, vmaf_json, debug):
    vmaf_json = (
        vmaf_json
        if vmaf_json is not None
        else tempfile.NamedTemporaryFile(prefix="vmaf.", suffix=".json").name
    )
    # ffmpeg supports libvmaf: use it (way faster)
    # important: vmaf must be called with videos in the right order
    # <distorted_video> <reference_video>
    # https://jina-liu.medium.com/a-practical-guide-for-vmaf-481b4d420d9c
    ffmpeg_params = [
        "-i",
        distorted_filename,
        "-i",
        ref_filename,
        "-lavfi",
        f"libvmaf=model=path={VMAF_MODEL}:log_fmt=json:log_path={vmaf_json}",
        "-f",
        "null",
        "-",
    ]
    retcode, _, stderr, _ = ffmpeg_run(ffmpeg_params, debug)
    assert retcode == 0, stderr
    return parse_vmaf_output(vmaf_json)


def parse_vmaf_output(vmaf_json):
    """Parse log/output files and return quality score"""
    with open(vmaf_json) as fd:
        data = json.load(fd)
    vmaf_dict = {
        "mean": data["pooled_metrics"]["vmaf"]["mean"],
        "harmonic_mean": data["pooled_metrics"]["vmaf"]["harmonic_mean"],
    }
    # get per-frame VMAF values
    vmaf_list = np.array(
        list(data["frames"][i]["metrics"]["vmaf"] for i in range(len(data["frames"])))
    )
    # add some percentiles
    vmaf_dict.update(
        {
            f"p{percentile}": np.percentile(vmaf_list, percentile)
            for percentile in PERCENTILE_LIST
        }
    )
    return vmaf_dict
