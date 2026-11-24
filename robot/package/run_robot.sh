#!/usr/bin/env bash
# Start the voice guide on the robot (host, in your own folder, as user "run").
# Usage:  ./run_robot.sh setup      once: python packages into ./pylib
#         ./run_robot.sh doctor     check everything
#         ./run_robot.sh takeover   silence the built-in assistant (Lumi), volume up, check the speaker is free
#         ./run_robot.sh            run the bridge
#         ./run_robot.sh restore    before you leave: Lumi back on, volume back
set -e
cd "$(dirname "$0")"

if [ ! -f config.env ]; then
  cp config.env.example config.env
  echo "Created config.env. Check it, then run this again."
  exit 1
fi
set -a; . ./config.env; set +a

if [ -f /opt/ros/humble/setup.bash ]; then
  # shellcheck disable=SC1091
  . /opt/ros/humble/setup.bash
else
  echo "WARNING: /opt/ros/humble/setup.bash not found (not on the robot?)"
fi
AIMDK_PATH="${AIMDK_PATH:-/agibot/software/common}"
if [ -f "$AIMDK_PATH/install/setup.bash" ]; then
  # shellcheck disable=SC1090
  . "$AIMDK_PATH/install/setup.bash"
elif [ -d "$AIMDK_PATH/local/lib" ]; then
  # the built AimDK as the organisers found it on 24 Nov (no container, /agibot/software/common)
  export PYTHONPATH="$AIMDK_PATH/local/lib/python3.10/dist-packages:${PYTHONPATH:-}"
  export LD_LIBRARY_PATH="$AIMDK_PATH/lib:${LD_LIBRARY_PATH:-}"
  export AMENT_PREFIX_PATH="$AIMDK_PATH:${AMENT_PREFIX_PATH:-}"
else
  echo "WARNING: AIMDK_PATH=$AIMDK_PATH has neither install/setup.bash nor local/lib (ask the MangoBot engineer)"
fi
export PYTHONPATH="$PWD/pylib:${PYTHONPATH:-}"

set_lumi() {  # only_voice = the built-in assistant keeps quiet; normal = back to normal
  ros2 service call /aimdk_5Fmsgs/srv/SetAgentPropertiesRequest aimdk_msgs/srv/SetAgentPropertiesRequest \
    "{contents: {properties: [{key: {value: 2}, value: $1}]}}" | grep -oE 'status.*' | head -1 || true
  # restarting the "agent" app is only possible where that app exists (not on robot 2); never fail on it
  (aima em stop-app agent && aima em start-app agent) </dev/null >/dev/null 2>&1 || echo "(no 'agent' app to restart here, fine)"
}
set_volume() { ros2 service call /aimdk_5Fmsgs/srv/SetVolume aimdk_msgs/srv/SetVolume "{audio_volume: $1}" | grep -oE 'status.*' | head -1 || true; }

case "${1:-}" in
  update)
    # pull the newest package from the live site and unpack it over this folder (config.env is kept)
    cd .. && curl -fsSL "${WEBAPP_URL%/}/oasis_voice_robot.zip" -o new.zip && unzip -oq new.zip && rm new.zip \
      && echo "updated. now run: ./run_robot.sh" ;;
  setup)
    # the user "run" is shared by every team and by the robot's own software: never pip --user, never sudo pip
    python3 -m pip install --no-deps --target ./pylib websocket-client
    python3 -c "import numpy" 2>/dev/null || python3 -m pip install --no-deps --target ./pylib numpy
    if [ "${MARKERS:-1}" != "0" ]; then
      python3 -c "import cv2" 2>/dev/null || python3 -m pip install --no-deps --target ./pylib opencv-python-headless || echo "OpenCV not installed: the robot will count steps (fine)"
    fi
    echo "setup done" ;;
  doctor)
    exec python3 -m oasis_voice doctor ;;
  volume)
    set_volume "${2:-${VOLUME:-95}}" ;;
  takeover)
    echo "Other bridges on the speaker (should be none but the robot's own):"
    ros2 topic info -v --no-daemon /aima/hal/audio/playback | grep -E "Node name|Publisher count" || true
    set_lumi only_voice
    set_volume "${VOLUME:-95}"
    echo "Lumi is quiet, volume ${VOLUME:-95}. Now: ./run_robot.sh" ;;
  restore)
    set_volume 72
    set_lumi normal
    echo "Robot is back to normal. Thank you." ;;
  "")
    exec python3 -m oasis_voice bridge ;;
  *)
    echo "usage: ./run_robot.sh [update|setup|doctor|takeover|volume N|restore]"; exit 1 ;;
esac
