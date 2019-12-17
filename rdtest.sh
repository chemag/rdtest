#!/bin/bash
# (c) Facebook, Inc. and its affiliates. Confidential and proprietary.

# Example:
# ```
# $ ./rdtest.sh /tmp/in.mp4 /tmp/results.txt --tmpdir /tmp/rdtest_tmp --resolutions "216x120" --bitrates "35" --rcmodes "cbr" -d
# ```
# Use `/tmp/in.mp4` as test file. Will produce results at `/tmp/results.txt`.
# Also:
# * will use `/tmp/rdtest_tmp/` as temporary directory
# * will limit the resolutions to 216x120
# * will limit the bitrates to 35 (kbps)
# * will limit the rcmodes to CBR


# tool configuration
LCEVC_ENC_DIR=${LCEVC_ENC_DIR:-""}
LCEVC_ENCODER="${LCEVC_ENC_DIR}/ffmpeg"
LCEVC_DEC_DIR=${LCEVC_DEC_DIR:-""}
LCEVC_DECODER="${LCEVC_DEC_DIR}/PPlusDec2Ref"
VMAF_DIR=${VMAF_DIR:=""}


declare -a CODECS
CODECS=(
    "lcevc-x264"
    "x264"
    "vp8"
)

declare -a RESOLUTIONS
# resolution set 1
RESOLUTIONS=(
    "640x360"  # 200-437kbps
    "480x272"  # actually 480x270 100-200kbps
    "320x160"  # < 100kbps
)

# resolution set 2
RESOLUTIONS=(
    "1280x720"
    "864x480"
    "640x360"
    "432x240"
    "216x120"
    #"160x90"
)

# Notes:
# * lcevc-x264 encoder barfs when asked to encode a "160x90" file
# * 720p is not a realistic encoding resolution in mobile due to
# performance issues

declare -a BITRATES
BITRATES=(
    2500
    1000
    560
    280
    140
    70
    35
)

declare -a RCMODES
RCMODES=(
    "cbr"
    "cfr"
)

# TODO(jblome): fix lcevc-x264 CFR mode parameters
RCMODES=(
    "cbr"
)


get_resolution () {
  local infile=$1
  local resolution
  resolution=$(ffprobe -v 0 -of csv=s=x:p=0 -select_streams v:0 -show_entries stream=width,height "${infile}")
  echo "${resolution}"
}


get_framerate () {
  local infile=$1
  local framerate
  framerate=$(ffprobe -v 0 -of csv=p=0 -select_streams v:0 -show_entries stream=r_frame_rate "${infile}")
  echo "scale=2; ${framerate}" | bc
}


get_duration () {
  local infile=$1
  local duration
  duration=$(ffprobe -v 0 -of csv=p=0 -select_streams v:0 -show_entries stream=duration "${infile}")
  echo "${duration}"
}


get_video_quality_vmaf () {
  local inraw=$1
  local refraw=$2
  local res=$3
  local pix_fmt=$4

  # check whether ffmpeg supports libvmaf
  local vmaf
  local ffmpeg_vmaf
  ffmpeg_vmaf=$(ffmpeg -filters|&grep libvmaf |grep "Calculate the VMAF")
  if [[ "${ffmpeg_vmaf}" == *"Calculate the VMAF"* ]]; then
    # ffmpeg supports libvmaf: use it (way faster)
    # [libvmaf @ 0x223d040] VMAF score: 7.812678
    vmaf=$(ffmpeg \
        -f rawvideo -pix_fmt "${pix_fmt}" -s "${res}" -i "${inraw_scaled}" \
        -f rawvideo -pix_fmt "${pix_fmt}" -s "${res}" -i "${refraw}" \
        -lavfi libvmaf="log_path=/tmp/vmaf.txt" -report -f null - 2>&1 | \
        grep "VMAF score" | sed -n -e 's/.*VMAF score: \([[:digit:].]\+\)/\1/p')
  else
    w=$(echo "${refres}" | grep -Eo "[0-9]*x" | grep -Eo "[0-9]*")
    h=$(echo "${refres}" | grep -Eo "x[0-9]*" | grep -Eo "[0-9]*")
    VMAF_PATH="PYTHONPATH=${VMAF_DIR}/python/src:${VMAF_DIR}/python/script/"
    VMAF_RUNNER="${VMAF_DIR}/run_vmaf"
    export "${VMAF_PATH}"
    vmaf=$("${VMAF_RUNNER}" "${refpix_fmt}" "${w}" "${h}" \
        "${refraw}" "${inraw_scaled}" 2>&1 | grep "Aggregate" | \
        sed -n -e 's/.*VMAF_score:\([[:digit:].]\+\).*/\1/p')
    fi

  echo "${vmaf}"
}


get_video_quality () {
  local inraw=$1
  local inres=$2
  local inpix_fmt=$3
  local refraw=$4
  local refres=$5
  local refpix_fmt=$6

  # scale the encoded video to the reference resolution and pixel format
  local inraw_scaled="${inraw}.scaled.yuv"
  ffmpeg -y -nostats -loglevel 0 \
      -f rawvideo -pix_fmt "${inpix_fmt}" -s "${inres}" -i "${inraw}" \
      -f rawvideo -pix_fmt "${refpix_fmt}" -s "${refres}" "${inraw_scaled}" \
      > /dev/null 2>&1

  # calculate objective quality statistics
  local l=""
  local psnr
  # [Parsed_psnr_0 @ 0x2b37c80] PSNR y:25.856528 u:38.911172 v:40.838878 average:27.530116 min:26.081163 max:29.675452
  psnr=$(ffmpeg \
      -f rawvideo -pix_fmt "${refpix_fmt}" -s "${refres}" -i "${inraw_scaled}" \
      -f rawvideo -pix_fmt "${refpix_fmt}" -s "${refres}" -i "${refraw}" \
      -filter_complex "psnr" -f NULL ${l} - 2>&1 | grep Parsed_psnr | \
      sed -n -e 's/.*y:\([[:digit:].]\+\) u:.*/\1/p')

  local ssim
  # [Parsed_ssim_0 @ 0x2e81e80] SSIM Y:0.742862 (5.898343) U:0.938426 (12.106034) V:0.970545 (15.308392) All:0.813403 (7.290963)
  ssim=$(ffmpeg \
      -f rawvideo -pix_fmt "${refpix_fmt}" -s "${refres}" -i "${inraw_scaled}" \
      -f rawvideo -pix_fmt "${refpix_fmt}" -s "${refres}" -i "${refraw}" \
      -filter_complex "ssim" -f NULL ${l} - 2>&1 | grep "Parsed_ssim" | \
      sed -n -e 's/.*All:\([[:digit:].]\+\) (.*/\1/p')

  # calculate subjective quality statistics
  local vmaf
  vmaf=$(get_video_quality_vmaf "${inraw}" "${refraw}" "${refres}" "${refpix_fmt}")

  echo "${psnr},${ssim},${vmaf}"
}


run_single_experiment () {
  local codec=$1
  local inraw=$2
  local inres=$3
  local inrate=$4
  local inpix_fmt=$5
  # output parameters
  local resolution=$6
  # bitrate is defined in kbps
  local bitrate=$7
  local rcmode=$8
  local outraw=$9
  local tmpenc="${10}"
  local debug="${11}"

  # build ffmpeg common parameters
  ENCTOOL=$(command -v ffmpeg)
  DECTOOL=$(command -v ffmpeg)
  ENCPARMS=(-y)
  ENCPARMS+=(-f rawvideo -s "${inres}" -r "${inrate}" -pix_fmt "${inpix_fmt}" -i "${inraw}")
  DECPARMS=(-i "${tmpenc}")

  # per-codec parameters
  if [ "${codec}" = "lcevc-x264" ]; then
    ENCTOOL="${LCEVC_ENCODER}"
    ENCPARMS+=(-c:v pplusenc_x264 -base_encoder x264)
    if [ "${rcmode}" = "cbr" ]; then
      local mode="bitrate=${bitrate}\\;rc_pcrf_base_rc_mode=${rcmode}\\;"
    elif [ "${rcmode}" = "cfr" ]; then
      # TODO(jblome): fix lcevc-x264 CFR mode parameters
      echo "# error: cfr needs better parameters"
      return 1
    else
      echo "# error unsupported rcmode: ${rcmode}"
      return 1
    fi
    ENCPARMS+=(-eil_params "${mode}")
    ENCPARMS+=(-s "${resolution}" -g 600)
    DECTOOL="${LCEVC_DECODER}"
    DECPARMS+=(--no-display -o "${outraw}")

  elif [ "${codec}" = "x264" ]; then
    ENCPARMS+=(-c:v libx264)
    ENCPARMS+=(-maxrate "${bitrate}k" -minrate "${bitrate}k" -b:v "${bitrate}k")
    ENCPARMS+=(-bufsize 4M)
    ENCPARMS+=(-s "${resolution}" -g 600)
    DECPARMS+=(-y "${outraw}")

  elif [ "${codec}" = "vp8" ]; then
    ENCPARMS+=(-c:v libvpx)
    ENCPARMS+=(-maxrate "${bitrate}k" -minrate "${bitrate}k" -b:v "${bitrate}k")
    ENCPARMS+=(-quality realtime -qmin 2 -qmax 56)
    ENCPARMS+=(-s "${resolution}" -g 600)
    DECPARMS+=(-y "${outraw}")
  fi

  ENCPARMS+=(-c:a copy "${tmpenc}")

  # encode the file
  if [ "${debug}" -gt 0 ]; then
    echo "# [${codec}] encoding file: ${inraw} -> ${tmpenc}"
  fi
  if [ "${debug}" -gt 1 ]; then
    echo "LD_LIBRARY_PATH=\"${LCEVC_ENC_DIR}:${LD_LIBRARY_PATH}\"" \
        "\"${ENCTOOL}\"" "${ENCPARMS[@]}"
  fi
  LD_LIBRARY_PATH="${LCEVC_ENC_DIR}:${LD_LIBRARY_PATH}" \
      "${ENCTOOL}" "${ENCPARMS[@]}" > /dev/null 2>&1

  if [ $? -ne 0 ]; then
    echo "# error encoding file: ${inraw} -> ${tmpenc}"
    echo "LD_LIBRARY_PATH=\"${LCEVC_ENC_DIR}:${LD_LIBRARY_PATH}\"" \
        "\"${ENCTOOL}\"" "${ENCPARMS[@]}"
    return 1
  fi

  # decode the file
  if [ "${debug}" -gt 0 ]; then
    echo "# [${codec}] decoding file: ${tmpenc} -> ${outraw}"
  fi
  if [ "${debug}" -gt 1 ]; then
    echo "LD_LIBRARY_PATH=\"${LCEVC_ENC_DIR}:${LD_LIBRARY_PATH}\"" \
        "\"${DECTOOL}\"" "${DECPARMS[@]}"
  fi
  LD_LIBRARY_PATH="${LCEVC_DEC_DIR}:${LD_LIBRARY_PATH}" \
      "${DECTOOL}" "${DECPARMS[@]}" > /dev/null 2>&1
  if [ $? -ne 0 ]; then
    echo "# error decoding file: ${tmpenc} -> ${outraw}"
    echo "LD_LIBRARY_PATH=\"${LCEVC_ENC_DIR}:${LD_LIBRARY_PATH}\"" \
        "\"${DECTOOL}\"" "${DECPARMS[@]}"
    return 1
  fi
}


run_lcevc_experiment () {
  local input=$1
  local refres=$2
  local refpix_fmt=$3
  local output_dir=$4
  local debug=$5
  local results=$6

  mkdir -p "${output_dir}"
  # remove directory path
  local in_filename="${input##*/}"
  local in_duration_secs
  in_duration_secs=$(get_duration "${input}")

  # make sure the input file exists
  if [[ -r "${in_filename}" ]]; then
    echo "# error: input file not readable: ${in_filename}"
    return 1
  fi

  # first decode the original file into a raw file
  local in_resolution
  in_resolution=$(get_resolution "${input}")
  local inrate
  inrate=$(get_framerate "${input}")

  refraw="${output_dir}/${in_filename}.ref_${in_resolution}.yuv"
  if [[ ! -r "${refraw}" ]]; then
    if [ "${debug}" -gt 0 ]; then
      echo "# generating raw reference: ${refraw}"
      echo "ffmpeg -y -i ${input} -f rawvideo -s ${refres} -pix_fmt ${refpix_fmt} ${refraw}"
    fi
    ffmpeg -y -i "${input}" \
        -f rawvideo -s "${refres}" -pix_fmt "${refpix_fmt}" "${refraw}" \
        > /dev/null 2>&1
  fi

  # lcevc encodings
  echo "# in_filename,codec,resolution,rcmode,bitrate,actual_bitrate,psnr,ssim,vmaf" > "${results}"
  for codec in "${CODECS[@]}"; do
    for resolution in "${RESOLUTIONS[@]}"; do
      for bitrate in "${BITRATES[@]}"; do
        for rcmode in "${RCMODES[@]}"; do
          local outraw="${output_dir}/${in_filename}.${codec}.${resolution}.${bitrate}.${rcmode}.yuv"
          local tmpenc="${outraw}.mp4"
          if [ "${debug}" -gt 0 ]; then
            echo "# generating ${outraw}"
          fi
          run_single_experiment "${codec}" "${refraw}" "${refres}" "${inrate}" "${refpix_fmt}" "${resolution}" "${bitrate}" "${rcmode}" "${outraw}" "${tmpenc}" "${debug}"
          if [ $? -ne 0 ]; then
            echo "# error processing file: ${refraw} -> ${outraw}"
            return 1
          fi
          size_bytes=$(stat -c '%s' "${tmpenc}")
          actual_bitrate=$(bc <<<"8 * $size_bytes / $in_duration_secs / 1000")
          if [ "${debug}" -gt 0 ]; then
            echo "# parsing ${outraw}"
          fi
          quality=$(get_video_quality "${outraw}" "${resolution}" "${refpix_fmt}" "${refraw}" "${refres}" "${refpix_fmt}")
          # print output line
          echo "${in_filename},${codec},${resolution},${rcmode},${bitrate},${actual_bitrate},${quality}" >> "${results}"
        done
      done
    done
  done
}

debug=0
tmpdir="/tmp/"
refres="1280x720"
refpix_fmt="yuv420p"

usage() {
  echo "./rdtest.sh [options] input_file.yuv results.txt"
}

process_args() {
  # convert argument list to a parsed string
  ARGS=$(getopt -o f:b::d --long "tmpdir:,vmaf-dir:,resolution:,pix_fmt:,codecs:,resolutions:,bitrates:,rcmodes:,debug,quiet" -n "getopt.sh" -- "$@");
  # check for bad arguments
  if [ $? -ne 0 ]; then
    echo "Terminating..." >&2
    exit 1
  fi
  # convert parsed string back to argument list
  #   quotes around "$ARGS" are essential
  eval set -- "$ARGS"
  # parse arguments
  while true; do
    case "$1" in
      -d|--debug)
        debug=$((debug + 1))
        shift
        ;;
      --quiet)
        debug=0
        shift
        ;;
      -s|--resolution)
        refres="$2"
        shift 2
        ;;
      --pix_fmt)
        refpix_fmt="$2"
        shift 2
        ;;
      --tmpdir)
        tmpdir="$2"
        shift 2
        ;;
      --vmaf-dir)
        VMAF_DIR="$2"
        shift 2
        ;;
      --codecs)
        # shellcheck disable=SC2206
        CODECS=($2)
        shift 2
        ;;
      --resolutions)
        # shellcheck disable=SC2206
        RESOLUTIONS=($2)
        shift 2
        ;;
      --bitrates)
        # shellcheck disable=SC2206
        BITRATES=($2)
        shift 2
        ;;
      --rcmodes)
        # shellcheck disable=SC2206
        RCMODES=($2)
        shift 2
        ;;
      -h|--help)
        shift;
        echo "Usage: $0 [-s] [-d seplist] file ..."
        exit 1
        ;;
      --) shift; break; ;;
    esac
  done
  # check there are 2 extra parameters
  if [ "$#" -ne 2 ]; then
    usage
    exit 1
  fi
  infile=$1
  results=$2
  shift 2
}

main() {
  process_args "$@"

  # print values
  if [[ "$debug" -ge "1" ]]; then
    echo "debug = ${debug}"
    echo "tmpdir = ${tmpdir}"
    echo "vmaf_dir = ${VMAF_DIR}"
    echo "infile = ${infile}"
    echo "refres = ${refres}"
    echo "refpix_fmt = ${refpix_fmt}"
    echo "results = ${results}"
  fi

  # make sure the vmaf runner exists
  if [[ -x "${VMAF_RUNNER}" ]]; then
    echo "# error: vmaf runner not executable: ${VMAF_RUNNER}"
    return 1
  fi

  run_lcevc_experiment "${infile}" "${refres}" "${refpix_fmt}" "${tmpdir}" "${debug}" "${results}"
}


main "$@"

