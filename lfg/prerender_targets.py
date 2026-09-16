"""The LFG shell is prerendered; the list itself is always live (13.13.1)."""

from __future__ import annotations


def lfg_targets() -> dict:
    return {"/lfg/": "lfg_shell"}
