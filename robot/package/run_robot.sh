#!/usr/bin/env bash
# Start the voice guide on the robot (PC2, inside the container).
# Usage:  ./run_robot.sh            normal
#         ./run_robot.sh doctor     check everything first
set -e
cd "$(dirname "$0")"

if [ ! -f config.env ]; then
  cp config.env.example config.env
  echo "Created config.env. Open it, fill in AIMDK_PATH and WEBAPP_URL, then run this again."
  exit 1
fi
set -a; . ./config.env; set +a

if [ -f /opt/ros/humble/setup.bash ]; then
  # shellcheck disable=SC1091
  . /opt/ros/humble/setup.bash
else
  echo "WARNING: /opt/ros/humble/setup.bash not found (not on the robot?)"
fi
if [ -n "$AIMDK_PATH" ] && [ -f "$AIMDK_PATH/install/setup.bash" ]; then
  # shellcheck disable=SC1090
  . "$AIMDK_PATH/install/setup.bash"
else
  echo "WARNING: AIMDK_PATH not set or wrong in config.env (ask the MangoBot engineer for the path)"
fi

if [ "${1:-}" = "doctor" ]; then
  exec python3 -m oasis_voice doctor
fi
exec python3 -m oasis_voice bridge
