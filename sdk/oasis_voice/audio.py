"""Audio helpers for the robot bridge: a noise gate and a latency meter.

Noise gate
  The lobby is loud. The gate learns the background noise level and only lets
  through sound that is clearly louder (a person talking to the robot). A short
  "pre-roll" keeps the first syllable, and a "hangover" keeps the end of a sentence.
  Everything else is replaced with silence, so ElevenLabs hears clean turns.

Latency meter
  Time from the visitor's last loud sound to the first audio of the reply.
"""

import array
import collections
import math
import time


def rms(pcm):
    """Loudness of 16-bit mono PCM bytes."""
    samples = array.array("h")
    samples.frombytes(pcm[: len(pcm) - len(pcm) % 2])
    if not samples:
        return 0.0
    return math.sqrt(sum(s * s for s in samples) / len(samples))


class NoiseGate:
    def __init__(self, min_rms=350.0, ratio=2.5, hangover_s=0.7, preroll_s=0.3, chunk_s=0.1, enabled=True):
        self.min_rms = min_rms
        self.ratio = ratio
        self.hang_chunks = max(1, int(hangover_s / chunk_s))
        self.preroll = collections.deque(maxlen=max(1, int(preroll_s / chunk_s)))
        self.enabled = enabled
        self.floor = min_rms / ratio
        self.open = False
        self.quiet_count = 0
        self.last_loud = 0.0

    @property
    def threshold(self):
        return max(self.min_rms, self.floor * self.ratio)

    def process(self, chunk, vad_active=None):
        """Return a list of chunks to send now (empty list = send silence instead)."""
        if not self.enabled:
            return [chunk]
        level = rms(chunk)
        loud = level > self.threshold or bool(vad_active)
        if loud:
            self.last_loud = time.monotonic()
        if not self.open:
            if loud:
                self.open = True
                self.quiet_count = 0
                out = list(self.preroll) + [chunk]
                self.preroll.clear()
                return out
            # learn the background level only while nobody is talking
            self.floor = 0.95 * self.floor + 0.05 * level
            self.preroll.append(chunk)
            return []
        if loud:
            self.quiet_count = 0
            return [chunk]
        self.quiet_count += 1
        if self.quiet_count > self.hang_chunks:
            self.open = False
            self.preroll.append(chunk)
            return []
        return [chunk]


class LatencyMeter:
    def __init__(self):
        self.waiting_since = None
        self.samples = []

    def user_turn_ended(self, at=None):
        """Call when the visitor's final transcript arrives."""
        self.waiting_since = at or time.monotonic()

    def agent_audio(self, last_loud=None):
        """Call on every agent audio chunk; returns seconds for the first chunk of a reply, else None."""
        if self.waiting_since is None:
            return None
        start = last_loud if last_loud and last_loud <= self.waiting_since else self.waiting_since
        took = time.monotonic() - start
        self.waiting_since = None
        self.samples.append(took)
        return took

    def summary(self):
        if not self.samples:
            return "no replies yet"
        s = sorted(self.samples)
        return f"{len(s)} replies, median {s[len(s) // 2]:.2f}s, worst {s[-1]:.2f}s"
