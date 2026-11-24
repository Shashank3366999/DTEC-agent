#!/usr/bin/env python3
"""
Voice of the Oasis: ElevenLabs Agent <-> AgiBot X2 bridge (starter code)

What it does
  robot microphone  /agent/process_audio_output  (16 kHz, 16-bit, mono)
        -> your ElevenLabs Agent over WebSocket
        -> robot speaker  /aima/hal/audio/playback

Run it on the robot's development computer (PC2) in your team folder.
The MangoBot engineer switches the robot to voice-only mode and gives
PC2 internet access at your orientation slot.

  pip3 install websocket-client numpy
  source /opt/ros/humble/setup.bash
  source <path to aimdk>/install/setup.bash      # ask MangoBot for the path
  export ELEVENLABS_AGENT_ID=your_agent_id
  export ELEVENLABS_API_KEY=your_key             # only if your agent is private
  python3 elevenlabs_robot_bridge.py

Then say the robot's wake word once and start talking.

Options (environment variables)
  HALF_DUPLEX=1   mute the microphone while the robot speaks. Use this if
                  the robot hears itself and interrupts its own answers.
  MIC_STREAM=1    only use one microphone stream (1 built-in, 2 external).
                  Default: use whichever stream speaks first.
  VERBOSE=1       print every event from ElevenLabs.

Where to add your own logic: on_agent_text(), on_user_text() and
on_tool_call() at the bottom of the Bridge class. Movement stays with
MangoBot: do not publish to any motion topic.

Message types from AimDK X2 docs (x2-aimdk.agibot.com, 5.2.1 Voice Control
and the Python examples mic_receiver / play_audio_stream).
"""

import array
import base64
import json
import os
import queue
import signal
import sys
import threading
import time
import urllib.request

import numpy as np
import websocket  # pip3 install websocket-client

import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy

from aimdk_msgs.msg import (AudioData, AudioInfo, AudioPlayback,
                            AudioVadStateType, CommonState, FocusRequester,
                            FocusResponse, ProcessedAudioOutput)
from aimdk_msgs.srv import AbandonAudioFocus, RequestAudioFocus, StopAudioPlay

RATE = 16000                 # Hz, what the robot gives and takes
BYTES_PER_SEC = RATE * 2     # 16-bit mono
CHUNK = BYTES_PER_SEC // 10  # 100 ms
SILENCE = bytes(CHUNK)
FOCUS_PRIORITY = 8           # same value as AgiBot's stream example

AGENT_ID = os.environ.get("ELEVENLABS_AGENT_ID", "").strip()
API_KEY = os.environ.get("ELEVENLABS_API_KEY", "").strip()
HALF_DUPLEX = os.environ.get("HALF_DUPLEX", "0") == "1"
MIC_STREAM = int(os.environ.get("MIC_STREAM", "0"))
VERBOSE = os.environ.get("VERBOSE", "0") == "1"


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def websocket_url():
    """Public agent: connect with the agent ID. Private agent: get a signed URL."""
    if not API_KEY:
        return "wss://api.elevenlabs.io/v1/convai/conversation?agent_id=" + AGENT_ID
    req = urllib.request.Request(
        "https://api.elevenlabs.io/v1/convai/conversation/get-signed-url?agent_id=" + AGENT_ID,
        headers={"xi-api-key": API_KEY})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())["signed_url"]


def resample(pcm, src_rate):
    """Agent audio in another PCM rate -> 16 kHz. Better: set the agent to PCM 16000."""
    if src_rate == RATE or not pcm:
        return pcm
    x = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    n = int(len(x) * RATE / src_rate)
    y = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)
    return y.astype(np.int16).tobytes()


class Bridge(Node):
    def __init__(self):
        super().__init__("voo_elevenlabs_bridge")
        self.pkg = "voo_bridge%d" % os.getpid()
        self.mic_q = queue.Queue()
        self.spk = bytearray()
        self.spk_lock = threading.Lock()
        self.speaking_until = 0.0
        self.mic_stream = MIC_STREAM
        self.out_rate = RATE
        self.token = 0
        self.ws = None
        self.connected = False
        self.running = True

        mic_qos = QoSProfile(history=QoSHistoryPolicy.KEEP_LAST, depth=500,
                             reliability=QoSReliabilityPolicy.BEST_EFFORT)
        self.create_subscription(ProcessedAudioOutput, "/agent/process_audio_output",
                                 self.on_mic, mic_qos)
        self.create_subscription(FocusResponse, "/aima/hal/audio/focus_response",
                                 self.on_focus, 10)
        self.player = self.create_publisher(AudioPlayback, "/aima/hal/audio/playback", 10)
        self.focus_cli = self.create_client(RequestAudioFocus, "/aimdk_5Fmsgs/srv/RequestAudioFocus")
        self.abandon_cli = self.create_client(AbandonAudioFocus, "/aimdk_5Fmsgs/srv/AbandonAudioFocus")
        self.stop_cli = self.create_client(StopAudioPlay, "/aimdk_5Fmsgs/srv/StopAudioPlay")

    # ---------------------------------------------------------------- ROS side
    def call(self, client, req, tries=8, timeout=0.25):
        """AgiBot's advice: cross-host ROS services need retries."""
        for _ in range(tries):
            if not client.wait_for_service(timeout_sec=timeout):
                continue
            fut = client.call_async(req)
            done = threading.Event()
            fut.add_done_callback(lambda f: done.set())
            if done.wait(timeout * 4) and fut.result() is not None:
                return fut.result()
        return None

    def requester(self):
        return FocusRequester(pkg_name=self.pkg, priority=FOCUS_PRIORITY)

    def take_focus(self):
        req = RequestAudioFocus.Request()
        req.focus_requester = self.requester()
        res = self.call(self.focus_cli, req)
        ok = (res is not None and res.reponse.status.value == CommonState.SUCCESS
              and res.focus_response.focus_gain)
        log("speaker focus:", "yes" if ok else "NO (ask MangoBot to check the agent module)")
        return ok

    def drop_focus(self):
        req = AbandonAudioFocus.Request()
        req.focus_requester = self.requester()  # must match the request exactly
        self.call(self.abandon_cli, req, tries=3)

    def on_focus(self, msg):
        if msg.pkg_name == self.pkg and not msg.focus_gain:
            log("speaker focus lost, asking again")
            threading.Thread(target=self.take_focus, daemon=True).start()

    def on_mic(self, msg):
        if self.mic_stream == 0:
            self.mic_stream = msg.stream_id
            log("listening on mic stream", msg.stream_id)
        if msg.stream_id != self.mic_stream:
            return
        if HALF_DUPLEX and time.monotonic() < self.speaking_until:
            return
        vad = msg.audio_vad_state.value
        if vad == AudioVadStateType.AUDIO_VAD_STATE_BEGIN and VERBOSE:
            log("speech start")
        self.mic_q.put(bytes(msg.audio_data))

    def play(self, pcm):
        """Speaker loop, paced at real time with a small lead."""
        msg = AudioPlayback()
        msg.pkg_name = self.pkg
        msg.token_id = "%s-%d" % (self.pkg, self.token)
        msg.info = AudioInfo(channels=1, sample_rate=RATE)
        msg.data = AudioData(data=array.array("B", pcm))
        self.player.publish(msg)

    def speaker_loop(self):
        lead = 0.3   # seconds of audio queued ahead in the robot's buffer
        clock = None
        sent = 0
        while self.running:
            with self.spk_lock:
                have = len(self.spk)
            if not have:
                clock, sent = None, 0
                time.sleep(0.02)
                continue
            if clock is None:
                clock = time.monotonic()
            allowed = int((time.monotonic() - clock + lead) * BYTES_PER_SEC) - sent
            if allowed >= CHUNK or (allowed > 0 and have < CHUNK):
                n = min(have, max(CHUNK, allowed - allowed % 2))
                with self.spk_lock:
                    pcm = bytes(self.spk[:n])
                    del self.spk[:n]
                self.play(pcm)
                sent += len(pcm)
                self.speaking_until = time.monotonic() + lead + 0.5
            time.sleep(0.05)

    def stop_speaking(self):
        with self.spk_lock:
            self.spk.clear()
        self.token += 1  # a new token_id clears the robot's playback buffer
        self.call(self.stop_cli, StopAudioPlay.Request(), tries=2)
        self.speaking_until = 0.0

    # ---------------------------------------------------------- ElevenLabs side
    def send(self, obj):
        try:
            self.ws.send(json.dumps(obj))
        except Exception as e:
            log("send failed:", e)

    def mic_loop(self):
        """Stream the mic every 100 ms; send silence when the robot hears nothing,
        so ElevenLabs can tell when the person stopped talking."""
        buf = bytearray()
        nxt = time.monotonic()
        while self.running:
            try:
                while True:
                    buf += self.mic_q.get_nowait()
            except queue.Empty:
                pass
            if len(buf) >= CHUNK:
                out = bytes(buf[:len(buf) - len(buf) % 2])
                buf.clear()
            else:
                out = SILENCE
            if self.connected:
                self.send({"user_audio_chunk": base64.b64encode(out).decode()})
            nxt += 0.1
            time.sleep(max(0.0, nxt - time.monotonic()))

    def on_message(self, ws, raw):
        ev = json.loads(raw)
        t = ev.get("type")
        if VERBOSE and t != "audio":
            log("event:", raw[:300])
        if t == "ping":
            self.send({"type": "pong", "event_id": ev["ping_event"]["event_id"]})
        elif t == "conversation_initiation_metadata":
            m = ev["conversation_initiation_metadata_event"]
            fmt_out = m.get("agent_output_audio_format", "")
            fmt_in = m.get("user_input_audio_format", "")
            log("connected. agent speaks", fmt_out, "and listens to", fmt_in)
            if fmt_in != "pcm_16000":
                log("WARNING: set the agent's input audio to PCM 16000 Hz")
            if fmt_out.startswith("pcm_"):
                self.out_rate = int(fmt_out.split("_")[1])
            else:
                log("ERROR: set the agent's output audio to PCM 16000 Hz")
        elif t == "audio":
            pcm = resample(base64.b64decode(ev["audio_event"]["audio_base_64"]), self.out_rate)
            with self.spk_lock:
                self.spk += pcm
        elif t == "interruption":
            log("interrupted by the user")
            self.stop_speaking()
        elif t == "user_transcript":
            self.on_user_text(ev["user_transcription_event"]["user_transcript"])
        elif t == "agent_response":
            self.on_agent_text(ev["agent_response_event"]["agent_response"])
        elif t == "client_tool_call":
            self.on_tool_call(ev["client_tool_call"])

    # ----------------------------------------------------- your logic goes here
    def on_user_text(self, text):
        log("visitor:", text)

    def on_agent_text(self, text):
        log("robot:", text)

    def on_tool_call(self, call):
        # A client tool defined in your agent. Reply with a result, for example:
        # self.send({"type": "client_tool_result", "tool_call_id": call["tool_call_id"],
        #            "result": "done", "is_error": False})
        log("tool call:", call.get("tool_name"), call.get("parameters"))

    # ------------------------------------------------------------------- main
    def on_open(self, ws):
        self.connected = True
        self.send({"type": "conversation_initiation_client_data"})

    def on_close(self, ws, code, msg):
        self.connected = False
        log("conversation closed", code or "", msg or "")

    def run_ws(self):
        backoff = 1
        while self.running:
            try:
                url = websocket_url()
                self.ws = websocket.WebSocketApp(
                    url,
                    on_open=self.on_open,
                    on_message=self.on_message,
                    on_error=lambda ws, e: log("websocket error:", e),
                    on_close=self.on_close)
                self.ws.run_forever(ping_interval=20, ping_timeout=10)
                backoff = 1
            except Exception as e:
                log("cannot reach ElevenLabs:", e, "(does PC2 have internet?)")
            self.ws = None
            self.connected = False
            if self.running:
                time.sleep(backoff)
                backoff = min(backoff * 2, 15)
                log("reconnecting")


def main():
    if not AGENT_ID:
        sys.exit("Set ELEVENLABS_AGENT_ID first.")
    try:
        from rclpy.signals import SignalHandlerOptions
        rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    except (ImportError, TypeError):
        rclpy.init()
    node = Bridge()
    ex = MultiThreadedExecutor()
    ex.add_node(node)
    threading.Thread(target=ex.spin, daemon=True).start()

    if not node.take_focus():
        log("continuing without confirmed focus; the speaker may stay silent")

    def shutdown(*_):
        node.running = False
        try:
            if node.ws:
                node.ws.close()
        except Exception:
            pass

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    threading.Thread(target=node.mic_loop, daemon=True).start()
    threading.Thread(target=node.speaker_loop, daemon=True).start()
    try:
        node.run_ws()
    finally:
        node.running = False
        node.stop_speaking()
        node.drop_focus()
        log("speaker released, bye")
        ex.shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
