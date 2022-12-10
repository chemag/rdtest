#!/usr/bin/env python3

"""utils.py module description."""

import os
import re
import subprocess
import sys
import time


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
    if type(command) is list:
        command = subprocess.list2cmdline(command)
    if debug > 0:
        print(f"running $ {command}")
    if dry_run:
        return 0, b"stdout", b"stderr"
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
    # clean up
    del p
    # return results
    return returncode, out, err, ts2 - ts1


def ffprobe_run(stream_info, infile):
    cmd = ["ffprobe", "-v", "0", "-of", "csv=s=x:p=0", "-select_streams", "v:0"]
    cmd += ["-show_entries", stream_info]
    cmd += [
        infile,
    ]
    retcode, stdout, stderr, _ = run(cmd)
    return stdout.decode("ascii").strip()


def ffmpeg_run(params, debug=0):
    cmd = [
        "ffmpeg",
    ] + params
    return run(cmd, debug=debug)


def get_resolution(infile):
    return ffprobe_run("stream=width,height", infile)


def get_pix_fmt(infile):
    return ffprobe_run("stream=pix_fmt", infile)


def get_framerate(infile):
    return ffprobe_run("stream=r_frame_rate", infile)


def get_duration(infile):
    # "stream=duration" fails on webm files
    return ffprobe_run("format=duration", infile)


# returns bitrate in kbps
def get_bitrate(infile):
    size_bytes = os.stat(infile).st_size
    in_duration_secs = get_duration(infile)
    actual_bitrate = 8.0 * size_bytes / float(in_duration_secs)
    return actual_bitrate


def get_psnr(distorted_filename, ref_filename, pix_fmt, resolution, psnr_log, debug):
    psnr_log = psnr_log if psnr_log is not None else "/tmp/psnr.txt"
    ffmpeg_params = [
        "-i",
        distorted_filename,
        "-i",
        ref_filename,
        "-filter_complex",
        "psnr=stats_file={psnr_log}",
        "-f",
        "null",
        "-",
    ]
    # [Parsed_psnr_0 @ 0x2b37c80] PSNR y:25.856528 u:38.911172 v:40.838878 \
    # average:27.530116 min:26.081163 max:29.675452
    retcode, stdout, stderr, _ = ffmpeg_run(ffmpeg_params, debug)
    pattern = r"\[Parsed_psnr_0.*PSNR.*y:([\d\.]+)"
    res = re.search(pattern, stderr.decode("ascii"))
    assert res
    return res.groups()[0]


def get_ssim(distorted_filename, ref_filename, pix_fmt, resolution, ssim_log, debug):
    ssim_log = ssim_log if ssim_log is not None else "/tmp/ssim.txt"
    ffmpeg_params = [
        "-i",
        distorted_filename,
        "-i",
        ref_filename,
        "-filter_complex",
        "ssim=stats_file={ssim_log}",
        "-f",
        "null",
        "-",
    ]
    # [Parsed_ssim_0 @ 0x2e81e80] SSIM Y:0.742862 (5.898343) U:0.938426 \
    # (12.106034) V:0.970545 (15.308392) All:0.813403 (7.290963)
    retcode, stdout, stderr, _ = ffmpeg_run(ffmpeg_params, debug)
    pattern = r"\[Parsed_ssim_0.*SSIM.*All:([\d\.]+)"
    res = re.search(pattern, stderr.decode("ascii"))
    assert res
    return res.groups()[0]


def get_vmaf(distorted_filename, ref_filename, pix_fmt, resolution, vmaf_log, debug):
    vmaf_log = vmaf_log if vmaf_log is not None else "/tmp/vmaf.txt"
    VMAF_MODEL = "/usr/share/model/vmaf_v0.6.1neg.json"
    # 1. ensure ffmpeg supports libvmaf
    ffmpeg_supports_libvmaf = False
    ffmpeg_params = [
        "-filters",
    ]
    retcode, stdout, stderr, _ = ffmpeg_run(ffmpeg_params, debug)
    assert retcode == 0, stderr
    for line in stdout.decode("ascii").splitlines():
        if "libvmaf" in line and "Calculate the VMAF" in line:
            ffmpeg_supports_libvmaf = True
    assert ffmpeg_supports_libvmaf, "error: ffmpeg does not support vmaf"
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
        f"libvmaf=model=path={VMAF_MODEL}:log_path={vmaf_log}",
        "-f",
        "null",
        "-",
    ]
    retcode, stdout, stderr, _ = ffmpeg_run(ffmpeg_params, debug)
    assert retcode == 0, stderr
    # [libvmaf @ 0x223d040] VMAF score: 7.812678
    pattern = r".*VMAF score: ([\d\.]+)"
    res = re.search(pattern, stderr.decode("ascii"))
    assert res
    return res.groups()[0]
