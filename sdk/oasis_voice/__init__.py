"""Oasis Voice SDK: configurable voice reception bots on ElevenLabs Agents.

A bot is a data file (a "profile"). The SDK turns it into:
  - an ElevenLabs agent (prompt, voice, languages, tools)   -> builder.py
  - a deterministic place directory the agent must use      -> directory.py
  - on-device tool handlers (robot bridge, text chat, web)  -> actions.py
  - a robot bridge with a noise gate and latency logging    -> bridge.py
"""

__version__ = "1.0.0"
