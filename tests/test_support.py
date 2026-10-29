import pathlib
import socket
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from support import FakeClient, NoNetworkAttempt, NoNetworkCase, TempRepo  # noqa: E402


class GuardTests(NoNetworkCase):
    """The guard must catch DNS before connect and fail loudly."""

    def _guard_case(self):
        case = NoNetworkCase(methodName="runTest")
        case.setUp()
        return case

    def test_unresolvable_host_is_recorded_as_dns_attempt(self):
        case = self._guard_case()
        try:
            with self.assertRaises(NoNetworkAttempt):
                socket.getaddrinfo("no-such-host.invalid", 443)
            self.assertEqual(case.network_attempts, [("dns", "no-such-host.invalid")])
            case.network_attempts.clear()
        finally:
            case.tearDown()

    def test_literal_ip_is_recorded_as_dns_attempt(self):
        case = self._guard_case()
        try:
            with self.assertRaises(NoNetworkAttempt):
                socket.getaddrinfo("192.0.2.1", 80)
            self.assertEqual(case.network_attempts, [("dns", "192.0.2.1")])
            case.network_attempts.clear()
        finally:
            case.tearDown()

    def test_connect_without_dns_is_recorded(self):
        case = self._guard_case()
        try:
            with self.assertRaises(NoNetworkAttempt):
                socket.socket.connect(object(), ("192.0.2.1", 80))
            self.assertEqual(case.network_attempts, [("connect", ("192.0.2.1", 80))])
            case.network_attempts.clear()
        finally:
            case.tearDown()

    def test_http_client_is_stopped_at_dns_not_turned_into_urlerror(self):
        from ipo_agent.net import Client

        with self.assertRaises(NoNetworkAttempt):
            Client(retries=0).get("https://no-such-host.invalid/")
        self.assertEqual(self.network_attempts, [("dns", "no-such-host.invalid")])
        self.network_attempts.clear()

    def test_teardown_fails_when_an_attempt_is_left_behind(self):
        case = self._guard_case()
        case.network_attempts.append(("dns", "example.invalid"))
        with self.assertRaises(AssertionError):
            case.tearDown()


class FakeClientTests(NoNetworkCase):
    def test_text_and_bytes_bodies(self):
        client = FakeClient({"https://example.invalid/a": "text", "https://example.invalid/b": b"bytes"})
        self.assertEqual(client.get_text("https://example.invalid/a"), "text")
        self.assertEqual(client.get("https://example.invalid/b"), b"bytes")
        self.assertEqual(client.calls, [("get_text", "https://example.invalid/a"), ("get", "https://example.invalid/b")])

    def test_unknown_url_and_injected_error(self):
        client = FakeClient({"https://example.invalid/boom": RuntimeError("down")})
        with self.assertRaises(AssertionError):
            client.get_text("https://example.invalid/other")
        with self.assertRaises(RuntimeError):
            client.get_text("https://example.invalid/boom")


class TempRepoTests(NoNetworkCase):
    def test_layout_and_writes(self):
        with TempRepo() as repo:
            self.assertTrue(repo.path("data", "snapshots").is_dir())
            self.assertTrue(repo.path("analysis").is_dir())
            self.assertTrue(repo.path("reports").is_dir())
            repo.card("acme", {"verdict": "apply"})
            self.assertEqual((repo.path("analysis", "acme.json")).read_text(), '{\n "verdict": "apply"\n}')


if __name__ == "__main__":
    unittest.main()
