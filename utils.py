#!/usr/bin/env python3

"""utils.py module description."""

import os
import re
import subprocess
import sys


class Command(object):
    # \brief Runs a command in the background
    @classmethod
    def RunBackground(cls, cmd, **kwargs):
        # set default values
        debug = kwargs.get("debug", 0)
        dry_run = kwargs.get("dry-run", 0)
        env = kwargs.get("env", None)
        stdin = subprocess.PIPE if kwargs.get("stdin", False) else None
        bufsize = kwargs.get("bufsize", 0)
        universal_newlines = kwargs.get("universal_newlines", False)
        default_close_fds = True if sys.platform == "linux2" else False
        close_fds = kwargs.get("close_fds", default_close_fds)
        # build strout
        strout = ""
        if debug > 1:
            s = cls.Cmd2Str(cmd)
            strout += "running %s" % s
            print("--> $ %s\n" % strout)
        if dry_run != 0:
            return "", "RunBackground dry run"
        if debug > 2:
            strout += "\ncmd = %r" % cmd
        if debug > 3:
            strout += "\nenv = %r" % env
        # get the shell parameter
        shell = type(cmd) in (type(""), type(""))
        # run the command
        p = subprocess.Popen(
            cmd,  # noqa: P204
            stdin=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=bufsize,
            universal_newlines=universal_newlines,
            env=env,
            close_fds=close_fds,
            shell=shell,
        )
        return p, strout

    @classmethod
    def Run(cls, cmd, **kwargs):
        # interpret command parameters
        dry_run = kwargs.get("dry-run", 0)
        stdin = kwargs.get("stdin", None)
        # run command in the background
        try:
            p, strout = cls.RunBackground(cmd, **kwargs)
        except BaseException:
            xtype, xvalue, _ = sys.exc_info()
            stderr = 'Error running command "%s": %s, %s' % (
                cls.Cmd2Str(cmd),
                str(xtype),
                str(xvalue),
            )
            return -1, "", stderr
        if dry_run != 0:
            return 0, strout + " dry-run", ""
        # wait for the command to terminate
        if stdin is not None:
            stdout, stderr = p.communicate(stdin)
        else:
            stdout, stderr = p.communicate()
        retcode = p.returncode
        # clean up
        del p
        # return results
        stdout = stdout.decode("ascii").strip()
        stderr = stderr.decode("ascii").strip()
        return retcode, strout + stdout, stderr

    @staticmethod
    def Cmd2Str(cmd):
        if type(cmd) in (type(""), type("")):
            return cmd
        # return ' '.join(cmd)
        line = [(c if " " not in c else ('"' + c + '"')) for c in cmd]
        stdout = " ".join(line)
        return stdout


def ffprobe_run(stream_info, infile):
    cmd = ["ffprobe", "-v", "0", "-of", "csv=s=x:p=0", "-select_streams", "v:0"]
    cmd += ["-show_entries", stream_info]
    cmd += [
        infile,
    ]
    retcode, stdout, stderr = Command.Run(cmd)
    return stdout


def ffmpeg_run(params, debug=0):
    cmd = [
        "ffmpeg",
    ] + params
    return Command.Run(cmd, debug=debug)


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


def get_psnr(filename, ref, pix_fmt, resolution, psnr_log, debug):
    psnr_log = psnr_log if psnr_log is not None else "/tmp/psnr.txt"
    ffmpeg_params = [
        "-i",
        filename,
        "-i",
        ref,
        "-filter_complex",
        "psnr=stats_file={psnr_log}",
        "-f",
        "null",
        "-",
    ]
    # [Parsed_psnr_0 @ 0x2b37c80] PSNR y:25.856528 u:38.911172 v:40.838878 \
    # average:27.530116 min:26.081163 max:29.675452
    retcode, stdout, stderr = ffmpeg_run(ffmpeg_params, debug)
    pattern = r"\[Parsed_psnr_0.*PSNR.*y:([\d\.]+)"
    res = re.search(pattern, stderr)
    assert res
    return res.groups()[0]


def get_ssim(filename, ref, pix_fmt, resolution, ssim_log, debug):
    ssim_log = ssim_log if ssim_log is not None else "/tmp/ssim.txt"
    ffmpeg_params = [
        "-i",
        filename,
        "-i",
        ref,
        "-filter_complex",
        "ssim=stats_file={ssim_log}",
        "-f",
        "null",
        "-",
    ]
    # [Parsed_ssim_0 @ 0x2e81e80] SSIM Y:0.742862 (5.898343) U:0.938426 \
    # (12.106034) V:0.970545 (15.308392) All:0.813403 (7.290963)
    retcode, stdout, stderr = ffmpeg_run(ffmpeg_params, debug)
    pattern = r"\[Parsed_ssim_0.*SSIM.*All:([\d\.]+)"
    res = re.search(pattern, stderr)
    assert res
    return res.groups()[0]


def get_vmaf(filename, ref, pix_fmt, resolution, vmaf_log, debug):
    vmaf_log = vmaf_log if vmaf_log is not None else "/tmp/vmaf.txt"
    VMAF_MODEL = "/usr/share/model/vmaf_v0.6.1neg.json"
    # check whether ffmpeg supports libvmaf
    ffmpeg_supports_libvmaf = False
    ffmpeg_params = [
        "-filters",
    ]
    retcode, stdout, stderr = ffmpeg_run(ffmpeg_params, debug)
    assert retcode == 0, stderr
    for line in stdout.splitlines():
        if "libvmaf" in line and "Calculate the VMAF" in line:
            ffmpeg_supports_libvmaf = True
    if ffmpeg_supports_libvmaf:
        # ffmpeg supports libvmaf: use it (way faster)
        # important: vmaf must be called with videos in the right order
        # <distorted_video> <reference_video>
        # https://jina-liu.medium.com/a-practical-guide-for-vmaf-481b4d420d9c
        ffmpeg_params = [
            "-i",
            filename,
            "-i",
            ref,
            "-lavfi",
            f"libvmaf=model=path={VMAF_MODEL}:log_path={vmaf_log}",
            "-f",
            "null",
            "-",
        ]
        retcode, stdout, stderr = ffmpeg_run(ffmpeg_params, debug)
        assert retcode == 0, stderr
        # [libvmaf @ 0x223d040] VMAF score: 7.812678
        pattern = r".*VMAF score: ([\d\.]+)"
        res = re.search(pattern, stderr)
        assert res
        return res.groups()[0]

    else:
        # run_vmaf binary
        width, height = resolution.split("x")
        vmaf_dir = os.environ.get("VMAF_DIR", None)
        if vmaf_dir:
            vmaf_env = {
                "PYTHONPATH": "%s/python/src:%s/python/script/" % (vmaf_dir, vmaf_dir),
            }
            vmaf_runner = os.path.join(os.environ["VMAF_DIR"], "run_vmaf")
        else:
            vmaf_env = None
            vmaf_runner = "run_vmaf"

        cmd = [vmaf_runner, pix_fmt, width, height, ref, filename]
        retcode, stdout, stderr = Command.Run(cmd, env=vmaf_env, debug=debug)
        assert retcode == 0, stderr
        # Aggregate ... VMAF_score:\([[:digit:].]\+\).*/\1/p')
        pattern = r"Aggregate.*VMAF_score:([\d\.]+)"
        res = re.search(pattern, stdout)
        assert res
        return res.groups()[0]
