"""Shared helpers for the agent tests.

Every test case inherits from :class:`NoNetworkCase`, which blocks DNS lookups and
socket connections and fails the test if any were attempted. Use :class:`FakeClient`
at the network boundary instead.

:class:`TempRepo` builds a throwaway repo root.  Paths that the modules bind at
import time have to be redirected explicitly:

* pass ``root`` / ``snap_dir`` explicitly to ``outcomes.load``/``update`` and
  ``trends.load``/``attach``; their defaults were evaluated at import, so patching
  ``outcomes.ROOT`` or ``trends.SNAP_DIR`` does not move them

Patch all of these for a test that touches the module:

* ``snapshot.ROOT`` **and** ``cards.DIR`` together for ``snapshot.build`` (the build
  does ``cards.path(key).relative_to(ROOT)``); set ``cards.DIR = root / "analysis"``
* ``quiet.ROOT``, ``quiet.REPORTS``, ``email_render.ROOT`` and ``cards.DIR`` for
  ``quiet.main``
* ``email_render.ROOT`` for ``email_render.main``
* ``outcomes.ROOT`` for ``outcomes.main``

Nothing here performs I/O outside a ``TempRepo`` directory.
"""

import json
import pathlib
import socket
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class NoNetworkAttempt(BaseException):
    """Raised by the guard. A BaseException so no ``except Exception`` swallows it."""


class NoNetworkCase(unittest.TestCase):
    """Fail if the test performs a DNS lookup or opens a socket connection."""

    def setUp(self):
        super().setUp()
        self.network_attempts = []
        self._network_patchers = [
            mock.patch("socket.getaddrinfo", side_effect=self._blocked_dns),
            mock.patch("socket.socket.connect", side_effect=self._blocked_connect),
        ]
        for patcher in self._network_patchers:
            patcher.start()

    def _blocked_dns(self, host, *args, **kwargs):
        self.network_attempts.append(("dns", host))
        raise NoNetworkAttempt(f"blocked DNS lookup for {host}")

    def _blocked_connect(self, *args, **kwargs):
        address = args[-1] if args else None
        self.network_attempts.append(("connect", address))
        raise NoNetworkAttempt(f"blocked socket connect to {address}")

    def tearDown(self):
        for patcher in reversed(self._network_patchers):
            patcher.stop()
        self.assertEqual(
            self.network_attempts, [], "test attempted real network access"
        )
        super().tearDown()


class FakeClient:
    """Stand-in for ``ipo_agent.net.Client`` that answers exact URLs from a dict.

    A value may be ``str``/``bytes`` (the response body) or an exception instance
    (raised instead, to exercise a source-error path).  Calls are recorded in
    ``self.calls`` so a test can assert the cookie-priming order.
    """

    def __init__(self, routes):
        self.routes = dict(routes)
        self.calls = []

    def _response(self, url):
        if url not in self.routes:
            raise AssertionError(f"unexpected URL: {url}")
        value = self.routes[url]
        if isinstance(value, BaseException):
            raise value
        return value

    def get(self, url, referer=None, accept="*/*"):
        self.calls.append(("get", url))
        value = self._response(url)
        return value.encode() if isinstance(value, str) else value

    def get_text(self, url, referer=None, accept="*/*"):
        self.calls.append(("get_text", url))
        value = self._response(url)
        return value.decode() if isinstance(value, bytes) else value


def fixture(name):
    """Read a file from ``tests/fixtures/`` as text."""
    return (pathlib.Path(__file__).resolve().parent / "fixtures" / name).read_text()


def snapshot(generated_at, ipos, date=None, errors=None):
    """A snapshot dict in the shape ``trends``/``quiet``/``outcomes`` read."""
    return {
        "generated_at": generated_at,
        "date": date or generated_at[:10],
        "ipos": list(ipos),
        "errors": errors or {},
    }


class TempRepo:
    """A throwaway repo root with ``data/snapshots``, ``analysis`` and ``reports``."""

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name)
        (self.root / "data" / "snapshots").mkdir(parents=True)
        (self.root / "analysis").mkdir()
        (self.root / "reports").mkdir()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.cleanup()

    def cleanup(self):
        self._tmp.cleanup()

    def path(self, *parts):
        return self.root.joinpath(*parts)

    def write_text(self, rel, text):
        target = self.root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        return target

    def write_json(self, rel, value):
        target = self.root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value, indent=1, ensure_ascii=False))
        return target

    def snapshot(self, stamp, ipos, date=None, errors=None):
        """Write a snapshot. ``stamp`` is the file stem, e.g. ``2026-10-29T0907``."""
        date_part, _, clock = stamp.partition("T")
        clock = clock or "09:07"
        if ":" not in clock:
            clock = f"{clock[:2]}:{clock[2:4]}"
        generated_at = f"{date_part}T{clock}+05:30"
        return self.write_json(
            f"data/snapshots/{stamp}.json",
            snapshot(generated_at, ipos, date=date, errors=errors),
        )

    def latest(self, snap):
        return self.write_json("data/latest.json", snap)

    def card(self, key, payload):
        return self.write_json(f"analysis/{key}.json", payload)

    def analysis(self, key, text):
        return self.write_text(f"analysis/{key}.md", text)

    def report(self, stem, payload):
        return self.write_json(f"reports/{stem}.json", payload)
