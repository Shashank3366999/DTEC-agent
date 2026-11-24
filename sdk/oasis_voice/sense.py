"""Camera markers: the robot knows where it is without asking anyone.

We print one QR code per map node (web app page /markers) and stick it next to that spot. This module only
READS the head camera (it never publishes), and only reports a marker that looks big enough, i.e. close.
Optional: needs OpenCV in the container (pip3 install opencv-python-headless). Without it, the robot counts steps.

Topic (AimDK X2 docs, sensor page): /aima/hal/sensor/rgbd_head_front/rgb_image/compressed, on PC2, 30 Hz.
A BEST_EFFORT + VOLATILE subscriber matches every publisher setting, so the QoS differences in the docs don't matter.

  MARKERS=0           turn it off
  CAMERA_TOPIC=...    another compressed camera topic
  MARKER_MIN_PX=70    smallest marker side in pixels that counts as "here" (higher = must be closer)
"""

import math
import os
import time

PREFIX = "DTEC:"
DEFAULT_TOPIC = "/aima/hal/sensor/rgbd_head_front/rgb_image/compressed"


class MarkerFilter:
    """Report a marker once it was seen big enough in 2 looks in a row, and again only after another one."""

    def __init__(self, min_px=70, looks=2):
        self.min_px, self.looks = min_px, looks
        self.candidate, self.count, self.last = None, 0, None

    def look(self, seen):
        """seen: list of (text, side in pixels). Returns a node id or None."""
        close = [(px, text[len(PREFIX):].strip()) for text, px in seen if text.startswith(PREFIX) and px >= self.min_px]
        node = max(close)[1] if close else None
        if node is None:
            self.candidate, self.count = None, 0
            return None
        self.count = self.count + 1 if node == self.candidate else 1
        self.candidate = node
        if self.count >= self.looks and node != self.last:
            self.last = node
            return node
        return None


def start(node, on_marker, log=print):
    """Subscribe to the camera on an existing ROS node. Returns True if it is running."""
    if os.environ.get("MARKERS", "1") == "0":
        log("camera markers: off")
        return False
    try:
        import cv2
        import numpy as np
        from rclpy.qos import QoSDurabilityPolicy, QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy
        from sensor_msgs.msg import CompressedImage
    except ImportError as e:
        log(f"camera markers: off ({e}). Counting steps instead.")
        return False

    detector = cv2.QRCodeDetector()
    filt = MarkerFilter(min_px=float(os.environ.get("MARKER_MIN_PX", "70")))
    state = {"next": 0.0}

    def on_image(msg):
        now = time.monotonic()
        if now < state["next"]:
            return
        state["next"] = now + 0.3
        try:
            img = cv2.imdecode(np.frombuffer(bytes(msg.data), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
            if img is None:
                return
            ok, texts, points, _ = detector.detectAndDecodeMulti(img)
            seen = []
            if ok:
                for text, q in zip(texts, points):
                    side = sum(math.dist(q[i], q[(i + 1) % 4]) for i in range(4)) / 4
                    seen.append((text, side))
            found = filt.look(seen)
        except Exception as e:  # a bad frame must never hurt the conversation
            log("camera frame skipped:", e)
            return
        if found:
            on_marker(found)

    qos = QoSProfile(history=QoSHistoryPolicy.KEEP_LAST, depth=1, reliability=QoSReliabilityPolicy.BEST_EFFORT,
                     durability=QoSDurabilityPolicy.VOLATILE)
    topic = os.environ.get("CAMERA_TOPIC") or DEFAULT_TOPIC
    from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
    node.create_subscription(CompressedImage, topic, on_image, qos, callback_group=MutuallyExclusiveCallbackGroup())
    log("camera markers: on,", topic)
    return True
