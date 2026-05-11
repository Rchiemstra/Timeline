#!/usr/bin/env bash
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Start Xvfb + minimal WM, run FreeCAD integration, encode MP4/GIF.

set -euo pipefail

FC_SCRIPT="${1:-${TIPTRACK_REPO_ROOT}/tests/integration/freecad_tiptrack_gui_smoke.py}"

if [[ ! -f "$FC_SCRIPT" ]]; then
  echo "tiptrack-docker: script not found: ${FC_SCRIPT}" >&2
  echo "tiptrack-docker: mount this repo at /work (see docker-compose.yml)." >&2
  exit 2
fi

tiptrack_encode_integration_media() {
  local AD="${TIPTRACK_ARTIFACT_DIR}"
  local -a src=(
    "${AD}/freecad_tiptrack_frame_00_initial.png"
    "${AD}/freecad_tiptrack_frame_01_scrub_sketch.png"
    "${AD}/freecad_tiptrack_frame_02_scrub_pad.png"
    "${AD}/freecad_tiptrack_frame_03_hole_sketch_on_cube.png"
    "${AD}/freecad_tiptrack_frame_04_full_with_hole.png"
  )
  local i

  if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "tiptrack-docker: ffmpeg missing; skip MP4/GIF." >&2
    return 0
  fi

  for i in "${!src[@]}"; do
    if [[ ! -f "${src[i]}" ]]; then
      echo "tiptrack-docker: missing screenshot ${src[i]}; skip MP4/GIF." >&2
      return 1
    fi
    cp "${src[i]}" "${AD}/record_frame_$(printf '%02d' "${i}").png"
  done

  ffmpeg -y -hide_banner -loglevel warning \
    -framerate 1 -i "${AD}/record_frame_%02d.png" \
    -vf "fps=10,format=yuv420p" "${AD}/freecad-tiptrack-integration.mp4"

  ffmpeg -y -hide_banner -loglevel warning \
    -framerate 1 -i "${AD}/record_frame_%02d.png" \
    -vf "fps=5,scale=960:-2:flags=lanczos" "${AD}/freecad-tiptrack-integration.gif"

  rm -f "${AD}"/record_frame_*.png
  echo "tiptrack-docker: wrote integration MP4/GIF under ${AD}"
}

export DISPLAY="${DISPLAY:-:99}"
NUM="${DISPLAY#:}"
rm -f "/tmp/.X${NUM}-lock" || true

Xvfb "$DISPLAY" -screen 0 1280x820x24 -nolisten tcp &
XVFB_PID=$!

cleanup() {
  kill "$XVFB_PID" 2>/dev/null || true
}
trap cleanup EXIT

sleep 0.5
openbox &
sleep 0.5

mkdir -p "${TIPTRACK_ARTIFACT_DIR}"

export LIBGL_ALWAYS_SOFTWARE="${LIBGL_ALWAYS_SOFTWARE:-1}"
export GALLIUM_DRIVER="${GALLIUM_DRIVER:-llvmpipe}"

echo "tiptrack-docker: running ${FC_SCRIPT}"

EXIT_CODE=0
dbus-run-session -- env DISPLAY="$DISPLAY" \
  LIBGL_ALWAYS_SOFTWARE="$LIBGL_ALWAYS_SOFTWARE" \
  GALLIUM_DRIVER="$GALLIUM_DRIVER" \
  freecad "$FC_SCRIPT" || EXIT_CODE=$?

if [[ "${EXIT_CODE}" -eq 0 ]]; then
  tiptrack_encode_integration_media || EXIT_CODE=$?
fi

exit "${EXIT_CODE}"
