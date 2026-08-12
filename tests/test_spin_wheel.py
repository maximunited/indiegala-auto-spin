"""Unit tests for IndieGala auto-spin helpers and control flow."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import spin_wheel as sw


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch, tmp_path):
    """Keep tests off the real home session and credentials."""
    monkeypatch.delenv("INDIEGALA_EMAIL", raising=False)
    monkeypatch.delenv("INDIEGALA_PASSWORD", raising=False)
    monkeypatch.delenv("NOTIFY_WEBHOOK", raising=False)
    monkeypatch.setenv("INDIEGALA_SESSION_DIR", str(tmp_path / "session"))
    yield


class TestExitCodes:
    def test_constants(self):
        assert sw.EXIT_OK == 0
        assert sw.EXIT_ERROR == 1
        assert sw.EXIT_NEEDS_HUMAN == 2


class TestGetSessionDir:
    def test_override(self, monkeypatch, tmp_path):
        target = tmp_path / "custom"
        monkeypatch.setenv("INDIEGALA_SESSION_DIR", str(target))
        assert sw.get_session_dir() == target

    def test_default_home(self, monkeypatch):
        monkeypatch.delenv("INDIEGALA_SESSION_DIR", raising=False)
        with patch.object(sw.Path, "home", return_value=Path("/fake/home")):
            assert sw.get_session_dir() == Path("/fake/home/.indiegala-session")


class TestLogPrize:
    def test_creates_jsonl_and_appends(self, tmp_path, monkeypatch):
        session = tmp_path / "session"
        monkeypatch.setenv("INDIEGALA_SESSION_DIR", str(session))
        sw.log_prize("won", "50 Galagems")
        sw.log_prize("already_spun", None)

        path = session / "prizes.jsonl"
        assert path.exists()
        rows = [
            json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
        ]
        assert len(rows) == 2
        assert rows[0]["status"] == "won"
        assert rows[0]["result"] == "50 Galagems"
        assert rows[1]["status"] == "already_spun"
        assert rows[1]["result"] is None
        assert "ts" in rows[0] and "date" in rows[0]

    def test_unicode_result(self, tmp_path, monkeypatch):
        monkeypatch.setenv("INDIEGALA_SESSION_DIR", str(tmp_path / "session"))
        sw.log_prize("won", "キー — 日本語")
        row = json.loads(
            (tmp_path / "session" / "prizes.jsonl").read_text(encoding="utf-8")
        )
        assert row["result"] == "キー — 日本語"

    def test_debug_prints(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("INDIEGALA_SESSION_DIR", str(tmp_path / "session"))
        sw.log_prize("won", "x", debug=True)
        assert "Logged prize" in capsys.readouterr().out


class TestIsFirstRun:
    def test_empty_dir_is_first(self, tmp_path):
        assert sw.is_first_run(tmp_path) is True

    def test_network_cookies(self, tmp_path):
        cookies = tmp_path / "Default" / "Network" / "Cookies"
        cookies.parent.mkdir(parents=True)
        cookies.write_bytes(b"x")
        assert sw.is_first_run(tmp_path) is False

    def test_legacy_cookies(self, tmp_path):
        cookies = tmp_path / "Default" / "Cookies"
        cookies.parent.mkdir(parents=True)
        cookies.write_bytes(b"x")
        assert sw.is_first_run(tmp_path) is False


class TestHumanType:
    def test_types_each_char(self, monkeypatch):
        monkeypatch.setattr(sw.time, "sleep", lambda *_: None)
        el = MagicMock()
        sw.human_type(el, "ab", debug=False)
        assert el.send_keys.call_count == 2
        el.send_keys.assert_any_call("a")
        el.send_keys.assert_any_call("b")

    def test_debug_message(self, monkeypatch, capsys):
        monkeypatch.setattr(sw.time, "sleep", lambda *_: None)
        sw.human_type(MagicMock(), "x", debug=True)
        assert "Filled field" in capsys.readouterr().out


class TestTryDismiss:
    def test_clicks_first_match(self):
        driver = MagicMock()
        el = MagicMock()
        with patch.object(sw, "WebDriverWait") as wait_cls:
            wait_cls.return_value.until.return_value = el
            ok = sw.try_dismiss(
                driver,
                [("css", ".close")],
                timeout=0.1,
                debug=True,
            )
        assert ok is True
        driver.execute_script.assert_called_once()

    def test_returns_false_when_all_timeout(self):
        driver = MagicMock()
        with patch.object(sw, "WebDriverWait") as wait_cls:
            wait_cls.return_value.until.side_effect = sw.TimeoutException()
            ok = sw.try_dismiss(driver, [("css", ".a"), ("css", ".b")], timeout=0.01)
        assert ok is False


class TestWaitForResult:
    def test_returns_text_from_selector(self):
        driver = MagicMock()
        el = MagicMock()
        el.is_displayed.return_value = True
        el.text = "  100 Galagems  "

        def find_element(by, sel):
            if sel == ".wheel-result":
                return el
            raise sw.NoSuchElementException()

        driver.find_element.side_effect = find_element

        with patch.object(sw.time, "sleep", lambda *_: None):
            result = sw._wait_for_result(driver, timeout=0.05, debug=False)
        assert result == "100 Galagems"

    def test_returns_none_when_empty(self):
        driver = MagicMock()
        driver.find_element.side_effect = sw.NoSuchElementException()
        driver.execute_script.return_value = None
        with patch.object(sw.time, "sleep", lambda *_: None):
            assert sw._wait_for_result(driver, timeout=0.05) is None


class TestWindowsToast:
    def test_escapes_quotes_and_invokes_powershell(self):
        with patch.object(sw.subprocess, "Popen") as popen:
            popen.return_value = MagicMock()
            assert sw._windows_toast("T'title", "msg'here") is True
            args = popen.call_args[0][0]
            assert args[0] == "powershell"
            script = args[-1]
            assert "T''title" in script
            assert "msg''here" in script

    def test_oserror_returns_false(self):
        with patch.object(sw.subprocess, "Popen", side_effect=OSError("no pe")):
            assert sw._windows_toast("t", "m") is False


class TestNotifyFailure:
    def test_posts_webhook_payload(self, monkeypatch):
        monkeypatch.setenv("NOTIFY_WEBHOOK", "https://example.test/hook")
        monkeypatch.setattr(sw.platform, "system", lambda: "Linux")

        captured = {}

        class FakeResp:
            status = 204

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def fake_urlopen(req, timeout=10):
            captured["url"] = req.full_url
            captured["body"] = json.loads(req.data.decode("utf-8"))
            captured["method"] = req.get_method()
            return FakeResp()

        with patch.object(sw.urllib.request, "urlopen", side_effect=fake_urlopen):
            sw.notify_failure("boom", sw.EXIT_ERROR, debug=True)

        assert captured["url"] == "https://example.test/hook"
        assert captured["method"] == "POST"
        assert "exit 1" in captured["body"]["content"]
        assert "boom" in captured["body"]["text"]

    def test_webhook_failure_warns_not_raises(self, monkeypatch, capsys):
        monkeypatch.setenv("NOTIFY_WEBHOOK", "https://example.test/hook")
        monkeypatch.setattr(sw.platform, "system", lambda: "Linux")
        with patch.object(
            sw.urllib.request,
            "urlopen",
            side_effect=sw.urllib.error.URLError("down"),
        ):
            sw.notify_failure("x", sw.EXIT_NEEDS_HUMAN)
        assert "WARNING: webhook notify failed" in capsys.readouterr().out

    def test_windows_toast_called(self, monkeypatch):
        monkeypatch.setattr(sw.platform, "system", lambda: "Windows")
        with patch.object(sw, "_windows_toast", return_value=True) as toast:
            sw.notify_failure("fail", sw.EXIT_ERROR)
        toast.assert_called_once()
        assert "exit 1" in toast.call_args[0][0]


class TestSpinWheelCredentials:
    def test_missing_credentials_returns_error(self, capsys):
        code = sw.spin_wheel(headless=True, debug=False)
        assert code == sw.EXIT_ERROR
        assert "INDIEGALA_EMAIL" in capsys.readouterr().out


class TestSpinWheelFlow:
    def _chrome_mock(self):
        driver = MagicMock()
        # Already logged in via profile link
        profile = MagicMock()
        driver.find_element.return_value = profile
        return driver

    def test_already_spun_logs_and_ok(self, monkeypatch, tmp_path):
        monkeypatch.setenv("INDIEGALA_EMAIL", "a@b.c")
        monkeypatch.setenv("INDIEGALA_PASSWORD", "secret")
        monkeypatch.setenv("INDIEGALA_SESSION_DIR", str(tmp_path / "session"))
        monkeypatch.setattr(sw, "random_delay", lambda *a, **k: None)

        driver = self._chrome_mock()

        with (
            patch.object(sw.uc, "Chrome", return_value=driver),
            patch.object(sw, "WebDriverWait") as wait_cls,
        ):
            wait_cls.return_value.until.side_effect = sw.TimeoutException()
            code = sw.spin_wheel(headless=True, debug=False)

        assert code == sw.EXIT_OK
        driver.quit.assert_called_once()
        log_path = tmp_path / "session" / "prizes.jsonl"
        row = json.loads(log_path.read_text(encoding="utf-8"))
        assert row["status"] == "already_spun"

    def test_successful_spin_logs_prize(self, monkeypatch, tmp_path):
        monkeypatch.setenv("INDIEGALA_EMAIL", "a@b.c")
        monkeypatch.setenv("INDIEGALA_PASSWORD", "secret")
        monkeypatch.setenv("INDIEGALA_SESSION_DIR", str(tmp_path / "session"))
        monkeypatch.setattr(sw, "random_delay", lambda *a, **k: None)
        monkeypatch.setattr(sw, "try_dismiss", lambda *a, **k: False)

        driver = self._chrome_mock()
        spin_btn = MagicMock()

        with (
            patch.object(sw.uc, "Chrome", return_value=driver),
            patch.object(sw, "WebDriverWait") as wait_cls,
            patch.object(sw, "_wait_for_result", return_value="Cool Game"),
        ):
            # First wait loop finds button; re-locate after dismiss also finds it
            wait_cls.return_value.until.return_value = spin_btn
            code = sw.spin_wheel(headless=True, debug=False)

        assert code == sw.EXIT_OK
        row = json.loads(
            (tmp_path / "session" / "prizes.jsonl").read_text(encoding="utf-8")
        )
        assert row["status"] == "won"
        assert row["result"] == "Cool Game"

    def test_chrome_crash_returns_error(self, monkeypatch, tmp_path, capsys):
        monkeypatch.setenv("INDIEGALA_EMAIL", "a@b.c")
        monkeypatch.setenv("INDIEGALA_PASSWORD", "secret")
        monkeypatch.setenv("INDIEGALA_SESSION_DIR", str(tmp_path / "session"))
        with patch.object(sw.uc, "Chrome", side_effect=RuntimeError("chrome died")):
            code = sw.spin_wheel(headless=True, debug=False)
        assert code == sw.EXIT_ERROR
        assert "failed to start Chrome" in capsys.readouterr().out


class TestMainCli:
    def test_nonzero_triggers_notify(self, monkeypatch):
        monkeypatch.setattr(sw, "is_first_run", lambda *_: False)
        monkeypatch.setattr(sw, "spin_wheel", lambda **kwargs: sw.EXIT_ERROR)
        notified = {}

        def fake_notify(msg, code, debug=False):
            notified["code"] = code
            notified["msg"] = msg

        monkeypatch.setattr(sw, "notify_failure", fake_notify)
        assert sw.main(["--headless"]) == sw.EXIT_ERROR
        assert notified["code"] == sw.EXIT_ERROR

    def test_ok_skips_notify(self, monkeypatch):
        called = {"n": 0}
        monkeypatch.setattr(sw, "is_first_run", lambda *_: False)
        monkeypatch.setattr(sw, "spin_wheel", lambda **k: sw.EXIT_OK)
        monkeypatch.setattr(
            sw,
            "notify_failure",
            lambda *a, **k: called.__setitem__("n", called["n"] + 1),
        )
        assert sw.main(["--headless"]) == sw.EXIT_OK
        assert called["n"] == 0

    def test_first_run_auto_visible(self, monkeypatch, capsys):
        monkeypatch.setattr(sw, "is_first_run", lambda *_: True)
        seen = {}

        def fake_spin(*, headless, debug):
            seen["headless"] = headless
            return sw.EXIT_OK

        monkeypatch.setattr(sw, "spin_wheel", fake_spin)
        assert sw.main([]) == sw.EXIT_OK
        assert seen["headless"] is False
        assert "First run detected" in capsys.readouterr().out

    def test_visible_overrides_first_run_false(self, monkeypatch):
        monkeypatch.setattr(sw, "is_first_run", lambda *_: True)
        seen = {}

        def fake_spin(*, headless, debug):
            seen["headless"] = headless
            return sw.EXIT_OK

        monkeypatch.setattr(sw, "spin_wheel", fake_spin)
        assert sw.main(["--visible"]) == sw.EXIT_OK
        assert seen["headless"] is False
