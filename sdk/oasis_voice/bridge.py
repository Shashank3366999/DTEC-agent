"""Robot bridge: AgiBot X2 microphone/speaker <-> ElevenLabs agent.

Based on the organisers' elevenlabs_robot_bridge.py (AimDK X2 docs 5.2.1 Voice
Control, examples mic_receiver / play_audio_stream). The ROS side is unchanged.
Added by the SDK:
  - client tools run on the robot (lookup_place, check-in, route, operator)
  - noise gate on the microphone (NOISE_GATE=0 to turn off)
  - latency log after every reply

Run on robot PC2, inside the container, after sourcing ROS 2 and AimDK:
  python3 -m oasis_voice bridge --profile profiles/dtec_navigator.json

Environment variables:
  ELEVENLABS_AGENT_ID   optional, defaults to the agent ID saved by `build`
  ELEVENLABS_API_KEY    only if the agent is private
  WEBAPP_URL            reception screen web app, for check-in/route/operator
  TOOL_SECRET           the web app's secret, if it has one
  HALF_DUPLEX=1         mute the mic while the robot speaks (if it interrupts itself)
  MIC_STREAM=1|2        1 built-in mic, 2 external mic (default: first that speaks)
  NOISE_GATE=0          turn the noise gate off
  NOISE_MIN_RMS=350     raise in very loud rooms (e.g. 600), lower if quiet speakers are missed
  VERBOSE=1             print every ElevenLabs event
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

import websocket  # pip3 install websocket-client

import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy

from aimdk_msgs.msg import (AudioData, AudioInfo, AudioPlayback,
                            AudioVadStateType, CommonState, FocusRequester,
                            FocusResponse, ProcessedAudioOutput)
from aimdk_msgs.srv import AbandonAudioFocus, RequestAudioFocus, StopAudioPlay

from .actions import ToolRouter
from .audio import LatencyMeter, NoiseGate

RATE = 16000
BYTES_PER_SEC = RATE * 2
CHUNK = BYTES_PER_SEC // 10  # 100 ms
SILENCE = bytes(CHUNK)
FOCUS_PRIORITY = 8

HALF_DUPLEX = os.environ.get("HALF_DUPLEX", "0") == "1"
MIC_STREAM = int(os.environ.get("MIC_STREAM", "0"))
VERBOSE = os.environ.get("VERBOSE", "0") == "1"


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def websocket_url(agent_id, api_key):
    if not api_key:
        return "wss://api.elevenlabs.io/v1/convai/conversation?agent_id=" + agent_id
    req = urllib.request.Request(
        "https://api.elevenlabs.io/v1/convai/conversation/get-signed-url?agent_id=" + agent_id,
        headers={"xi-api-key": api_key})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())["signed_url"]


def resample(pcm, src_rate):
    if src_rate == RATE or not pcm:
        return pcm
    import numpy as np
    x = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    n = int(len(x) * RATE / src_rate)
    y = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)
    return y.astype(np.int16).tobytes()


class Bridge(Node):
    def __init__(self, agent_id, api_key, router):
        super().__init__("voo_elevenlabs_bridge")
        self.agent_id = agent_id
        self.api_key = api_key
        self.router = router
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
        self.robot_vad = False
        self.gate = NoiseGate(min_rms=float(os.environ.get("NOISE_MIN_RMS", "350")),
                              enabled=os.environ.get("NOISE_GATE", "1") != "0")
        self.latency = LatencyMeter()

        mic_qos = QoSProfile(history=QoSHistoryPolicy.KEEP_LAST, depth=500,
                             reliability=QoSReliabilityPolicy.BEST_EFFORT)
        self.create_subscription(ProcessedAudioOutput, "/agent/process_audio_output", self.on_mic, mic_qos)
        self.create_subscription(FocusResponse, "/aima/hal/audio/focus_response", self.on_focus, 10)
        self.player = self.create_publisher(AudioPlayback, "/aima/hal/audio/playback", 10)
        self.focus_cli = self.create_client(RequestAudioFocus, "/aimdk_5Fmsgs/srv/RequestAudioFocus")
        self.abandon_cli = self.create_client(AbandonAudioFocus, "/aimdk_5Fmsgs/srv/AbandonAudioFocus")
        self.stop_cli = self.create_client(StopAudioPlay, "/aimdk_5Fmsgs/srv/StopAudioPlay")

    # ---------------------------------------------------------------- ROS side (as in the organisers' bridge)
    def call(self, client, req, tries=8, timeout=0.25):
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
        req.focus_requester = self.requester()
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
        end = getattr(AudioVadStateType, "AUDIO_VAD_STATE_END", None)
        if vad == AudioVadStateType.AUDIO_VAD_STATE_BEGIN:
            # Only trust the robot's voice detector if it also tells us when speech ends.
            self.robot_vad = end is not None
            if VERBOSE:
                log("speech start")
        elif end is not None and vad == end:
            self.robot_vad = False
        self.mic_q.put(bytes(msg.audio_data))

    def play(self, pcm):
        msg = AudioPlayback()
        msg.pkg_name = self.pkg
        msg.token_id = "%s-%d" % (self.pkg, self.token)
        msg.info = AudioInfo(channels=1, sample_rate=RATE)
        msg.data = AudioData(data=array.array("B", pcm))
        self.player.publish(msg)

    def speaker_loop(self):
        lead = 0.3
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
        self.token += 1
        self.call(self.stop_cli, StopAudioPlay.Request(), tries=2)
        self.speaking_until = 0.0

    # ---------------------------------------------------------------- ElevenLabs side
    def send(self, obj):
        try:
            self.ws.send(json.dumps(obj))
        except Exception as e:
            log("send failed:", e)

    def mic_loop(self):
        """Every 100 ms: pass speech through the noise gate, send silence otherwise."""
        buf = bytearray()
        nxt = time.monotonic()
        while self.running:
            try:
                while True:
                    buf += self.mic_q.get_nowait()
            except queue.Empty:
                pass
            if len(buf) >= CHUNK:
                chunk = bytes(buf[:len(buf) - len(buf) % 2])
                buf.clear()
                out = self.gate.process(chunk, vad_active=self.robot_vad)
            else:
                out = []
            if self.connected:
                for piece in out or [SILENCE]:
                    self.send({"user_audio_chunk": base64.b64encode(piece).decode()})
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
                log("WARNING: set the agent's input audio to PCM 16000 Hz (run the build again)")
            if fmt_out.startswith("pcm_"):
                self.out_rate = int(fmt_out.split("_")[1])
            else:
                log("ERROR: set the agent's output audio to PCM 16000 Hz (run the build again)")
        elif t == "audio":
            took = self.latency.agent_audio(self.gate.last_loud)
            if took is not None:
                log(f"latency {took:.2f}s  ({self.latency.summary()})")
            pcm = resample(base64.b64decode(ev["audio_event"]["audio_base_64"]), self.out_rate)
            with self.spk_lock:
                self.spk += pcm
        elif t == "interruption":
            log("interrupted by the visitor")
            self.stop_speaking()
        elif t == "user_transcript":
            self.latency.user_turn_ended()
            log("visitor:", ev["user_transcription_event"]["user_transcript"])
        elif t == "agent_response":
            log("robot:", ev["agent_response_event"]["agent_response"])
        elif t == "client_tool_call":
            threading.Thread(target=self.run_tool, args=(ev["client_tool_call"],), daemon=True).start()

    def run_tool(self, call):
        name, params = call.get("tool_name"), call.get("parameters") or {}
        started = time.monotonic()
        result, is_error = self.router.handle(name, params)
        log(f"tool {name} {json.dumps(params, ensure_ascii=False)} -> "
            f"{'ERROR ' if is_error else ''}{result[:160]} ({(time.monotonic() - started) * 1000:.0f} ms)")
        self.send({"type": "client_tool_result", "tool_call_id": call.get("tool_call_id"),
                   "result": result, "is_error": is_error})

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
                url = websocket_url(self.agent_id, self.api_key)
                self.ws = websocket.WebSocketApp(url, on_open=self.on_open, on_message=self.on_message,
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


def run(agent_id, api_key, router):
    if not agent_id:
        sys.exit("No agent ID. Run `python3 -m oasis_voice build` first, or set ELEVENLABS_AGENT_ID.")
    try:
        from rclpy.signals import SignalHandlerOptions
        rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    except (ImportError, TypeError):
        rclpy.init()
    node = Bridge(agent_id, api_key, router)
    ex = MultiThreadedExecutor()
    ex.add_node(node)
    threading.Thread(target=ex.spin, daemon=True).start()
    log(f"agent {agent_id} · noise gate {'on' if node.gate.enabled else 'off'} · "
        f"screen {router.webapp_url or 'not set (check-in/route/operator will say the screen is offline)'}")

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
        log("latency summary:", node.latency.summary())
        log("speaker released, bye")
        ex.shutdown()
        node.destroy_node()
        rclpy.shutdown()
