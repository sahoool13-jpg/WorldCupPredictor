"""Minimal stdlib HTTP JSON fetch. Fails loudly on transport/JSON errors (no stale
fallback). Kept tiny and dependency-free so the data layer needs no third-party install.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from .errors import DataError


def get_bytes(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "WorldCupPredictor/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                raise DataError(f"HTTP {resp.status} for {url}")
            return resp.read()
    except urllib.error.URLError as e:  # includes HTTPError
        raise DataError(f"fetch failed for {url}: {e}") from e


def get_text(url: str, timeout: int = 30) -> str:
    return get_bytes(url, timeout).decode("utf-8")


def get_json(url: str, timeout: int = 30) -> dict:
    raw = get_bytes(url, timeout)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise DataError(f"non-JSON response from {url}: {e}") from e
