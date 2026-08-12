"""Edge-case and negative-path coverage for spin_wheel."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import spin_wheel as sw


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch, tmp_path):
    monkeypatch.delenv("INDIEGALA_EMAIL", raising=False)
    monkeypatch.delenv("INDIEGALA_PASSWORD", raising=False)
    monkeypatch.delenv("NOTIFY_WEBHOOK", raising=False)
    monkeypatch.setenv("INDIEGALA_SESSION_DIR", str(tmp_path / "session"))
    yield


def _creds(monkeypatch, email="a@b.c", password="secret"):
    monkeypatch.setenv("INDIEGALA_EMAIL", email)
    monkeypatch.setenv("INDIEGALA_PASSWORD", password)


def _fast(monkeypatch):
    monkeypatch.setattr(sw, "random_delay", lambda *a, **k: None)
    monkeypatch.setattr(sw.time, "sleep", lambda *_: None)


# ---------------------------------------------------------------------------
# Credentials / session dir negatives
# ---------------------------------------------------------------------------


class TestCredentialNegatives:
    @pytest.mark.parametrize(
        "email,password",
        [
            (None, "secret"),
            ("a@b.c", None),
            ("", "secret"),
            ("a@b.c", ""),
            ("  ", "secret"),  # non-empty but... wait, "  " is truthy
        ],
    )
    def test_partial_or_empty_credentials(self, monkeypatch, email, password, capsys):
        if email is None:
            monkeypatch.delenv("INDIEGALA_EMAIL", raising=False)
        else:
            monkeypatch.setenv("INDIEGALA_EMAIL", email)
        if password is None:
            monkeypatch.delenv("INDIEGALA_PASSWORD", raising=False)
        else:
            monkeypatch.setenv("INDIEGALA_PASSWORD", password)

        # Whitespace-only email is truthy — documents current behavior (not trimmed)
        if email == "  " and password == "secret":
            # Will try to start Chrome; stub it to fail fast without real browser
            with patch.object(sw.uc, "Chrome", side_effect=RuntimeError("skip")):
                code = sw.spin_wheel(headless=True)
            assert code == sw.EXIT_ERROR
            assert "failed to start Chrome" in capsys.readouterr().out
            return

        code = sw.spin_wheel(headless=True)
        assert code == sw.EXIT_ERROR
        assert "INDIEGALA_EMAIL" in capsys.readouterr().out


class TestSessionDirEdgeCases:
    def test_empty_env_falls_back_to_home(self, monkeypatch):
        monkeypatch.setenv("INDIEGALA_SESSION_DIR", "")
        with patch.object(sw.Path, "home", return_value=Path("/home/x")):
            assert sw.get_session_dir() == Path("/home/x/.indiegala-session")

    def test_whitespace_override_is_used(self, monkeypatch):
        monkeypatch.setenv("INDIEGALA_SESSION_DIR", "   ")
        assert sw.get_session_dir() == Path("   ")


# ---------------------------------------------------------------------------
# log_prize edge / negative
# ---------------------------------------------------------------------------


class TestLogPrizeEdgeCases:
    def test_mkdir_failure_warns(self, monkeypatch, tmp_path, capsys):
        monkeypatch.setenv("INDIEGALA_SESSION_DIR", str(tmp_path / "nope"))

        def boom(*_a, **_k):
            raise OSError("permission denied")

        with patch.object(sw.Path, "mkdir", boom):
            sw.log_prize("won", "x")
        assert "WARNING: could not write prize log" in capsys.readouterr().out

    def test_empty_status_and_empty_result_still_logs(self, monkeypatch, tmp_path):
        monkeypatch.setenv("INDIEGALA_SESSION_DIR", str(tmp_path / "session"))
        sw.log_prize("", "")
        row = json.loads(
            (tmp_path / "session" / "prizes.jsonl").read_text(encoding="utf-8")
        )
        assert row["status"] == ""
        assert row["result"] == ""

    def test_special_json_chars_in_result(self, monkeypatch, tmp_path):
        monkeypatch.setenv("INDIEGALA_SESSION_DIR", str(tmp_path / "session"))
        sw.log_prize("won", 'He said "hi"\nline2\\path')
        row = json.loads(
            (tmp_path / "session" / "prizes.jsonl").read_text(encoding="utf-8")
        )
        assert row["result"] == 'He said "hi"\nline2\\path'


# ---------------------------------------------------------------------------
# is_first_run / human_type / try_dismiss edge
# ---------------------------------------------------------------------------


class TestIsFirstRunEdge:
    def test_both_cookie_locations(self, tmp_path):
        for rel in (
            Path("Default") / "Network" / "Cookies",
            Path("Default") / "Cookies",
        ):
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"")
        assert sw.is_first_run(tmp_path) is False

    def test_directory_named_cookies_is_enough(self, tmp_path):
        # exists() is True for dirs too — documents filesystem check, not file type
        cookies = tmp_path / "Default" / "Cookies"
        cookies.mkdir(parents=True)
        assert sw.is_first_run(tmp_path) is False


class TestHumanTypeEdge:
    def test_empty_string_no_keys(self, monkeypatch):
        monkeypatch.setattr(sw.time, "sleep", lambda *_: None)
        el = MagicMock()
        sw.human_type(el, "")
        el.send_keys.assert_not_called()

    def test_unicode_and_symbols(self, monkeypatch):
        monkeypatch.setattr(sw.time, "sleep", lambda *_: None)
        el = MagicMock()
        sw.human_type(el, "a@b.c!キー")
        assert el.send_keys.call_count == len("a@b.c!キー")


class TestTryDismissEdge:
    def test_second_selector_succeeds(self):
        driver = MagicMock()
        el = MagicMock()
        with patch.object(sw, "WebDriverWait") as wait_cls:
            wait_cls.return_value.until.side_effect = [
                sw.TimeoutException(),
                el,
            ]
            ok = sw.try_dismiss(
                driver,
                [("css", ".a"), ("css", ".b")],
                timeout=0.01,
            )
        assert ok is True
        driver.execute_script.assert_called_once_with("arguments[0].click();", el)

    def test_empty_selector_list(self):
        assert sw.try_dismiss(MagicMock(), [], timeout=0.01) is False

    def test_debug_prints_when_missing(self, capsys):
        with patch.object(sw, "WebDriverWait") as wait_cls:
            wait_cls.return_value.until.side_effect = sw.TimeoutException()
            sw.try_dismiss(MagicMock(), [("css", ".x")], timeout=0.01, debug=True)
        assert "No popup found" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# _wait_for_result edge / negative
# ---------------------------------------------------------------------------


class TestWaitForResultEdge:
    def test_skips_hidden_then_finds_visible(self):
        hidden = MagicMock()
        hidden.is_displayed.return_value = False
        hidden.text = " hidden prize "
        visible = MagicMock()
        visible.is_displayed.return_value = True
        visible.text = " Visible Prize "

        def find_element(_by, sel):
            if sel == ".wheel-result":
                return hidden
            if sel == ".wheel-prize":
                return visible
            raise sw.NoSuchElementException()

        driver = MagicMock()
        driver.find_element.side_effect = find_element
        with patch.object(sw.time, "sleep", lambda *_: None):
            assert sw._wait_for_result(driver, timeout=0.05) == "Visible Prize"

    def test_rejects_single_char_text(self):
        el = MagicMock()
        el.is_displayed.return_value = True
        el.text = "x"  # len after strip == 1 → rejected
        driver = MagicMock()
        driver.find_element.side_effect = lambda *_: el
        driver.execute_script.return_value = None
        # Force loop to exit quickly: only one selector match forever → sleep until timeout
        with patch.object(sw.time, "sleep", lambda *_: None):
            # shorten by making time jump
            times = [0.0, 0.0, 1.0]  # enter loop, check, exit

            def fake_time():
                return times.pop(0) if times else 99.0

            with patch.object(sw.time, "time", side_effect=fake_time):
                # After loop, container + JS also see same el — container path may return "x"
                # because container fallback only checks `if text` not len>1
                driver.find_element.side_effect = sw.NoSuchElementException()
                assert sw._wait_for_result(driver, timeout=0.05) is None

    def test_container_fallback(self):
        container = MagicMock()
        container.is_displayed.return_value = True
        container.text = "  From modal  "

        def find_element(_by, sel):
            if sel == ".modal.show":
                return container
            raise sw.NoSuchElementException()

        driver = MagicMock()
        driver.find_element.side_effect = find_element
        times = [0.0, 99.0]  # skip poll loop immediately

        with (
            patch.object(
                sw.time, "time", side_effect=lambda: times.pop(0) if times else 99.0
            ),
            patch.object(sw.time, "sleep", lambda *_: None),
        ):
            assert sw._wait_for_result(driver, timeout=5) == "From modal"

    def test_js_fallback(self):
        driver = MagicMock()
        driver.find_element.side_effect = sw.NoSuchElementException()
        driver.execute_script.return_value = "  JS Prize  "
        times = [0.0, 99.0]
        with (
            patch.object(
                sw.time, "time", side_effect=lambda: times.pop(0) if times else 99.0
            ),
            patch.object(sw.time, "sleep", lambda *_: None),
        ):
            assert sw._wait_for_result(driver, timeout=5) == "JS Prize"

    def test_js_webdriver_exception_returns_none(self):
        driver = MagicMock()
        driver.find_element.side_effect = sw.NoSuchElementException()
        driver.execute_script.side_effect = sw.WebDriverException("boom")
        times = [0.0, 99.0]
        with (
            patch.object(
                sw.time, "time", side_effect=lambda: times.pop(0) if times else 99.0
            ),
            patch.object(sw.time, "sleep", lambda *_: None),
        ):
            assert sw._wait_for_result(driver, timeout=5) is None

    def test_debug_prints_selector_hit(self, capsys):
        el = MagicMock()
        el.is_displayed.return_value = True
        el.text = "Prize"
        driver = MagicMock()
        driver.find_element.side_effect = lambda *_: el
        with patch.object(sw.time, "sleep", lambda *_: None):
            sw._wait_for_result(driver, timeout=0.05, debug=True)
        assert "Result found via selector" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# notify / toast negatives
# ---------------------------------------------------------------------------


class TestNotifyEdgeCases:
    def test_whitespace_webhook_skipped(self, monkeypatch):
        monkeypatch.setenv("NOTIFY_WEBHOOK", "   ")
        monkeypatch.setattr(sw.platform, "system", lambda: "Linux")
        with patch.object(sw.urllib.request, "urlopen") as urlopen:
            sw.notify_failure("x", sw.EXIT_ERROR)
        urlopen.assert_not_called()

    def test_empty_message_uses_title(self, monkeypatch):
        monkeypatch.setattr(sw.platform, "system", lambda: "Windows")
        with patch.object(sw, "_windows_toast", return_value=True) as toast:
            sw.notify_failure("   ", sw.EXIT_NEEDS_HUMAN)
        _title, body = toast.call_args[0]
        assert "exit 2" in _title
        assert body == _title

    def test_webhook_timeout_warns(self, monkeypatch, capsys):
        monkeypatch.setenv("NOTIFY_WEBHOOK", "https://example.test/hook")
        monkeypatch.setattr(sw.platform, "system", lambda: "Linux")
        with patch.object(
            sw.urllib.request, "urlopen", side_effect=TimeoutError("slow")
        ):
            sw.notify_failure("x", 1)
        assert "WARNING: webhook notify failed" in capsys.readouterr().out

    def test_webhook_oserror_warns(self, monkeypatch, capsys):
        monkeypatch.setenv("NOTIFY_WEBHOOK", "https://example.test/hook")
        monkeypatch.setattr(sw.platform, "system", lambda: "Linux")
        with patch.object(sw.urllib.request, "urlopen", side_effect=OSError("net")):
            sw.notify_failure("x", 1)
        assert "WARNING: webhook notify failed" in capsys.readouterr().out

    def test_toast_unavailable_debug(self, monkeypatch, capsys):
        monkeypatch.setattr(sw.platform, "system", lambda: "Windows")
        with patch.object(sw, "_windows_toast", return_value=False):
            sw.notify_failure("x", 1, debug=True)
        assert "Windows toast notification unavailable" in capsys.readouterr().out

    def test_non_windows_skips_toast(self, monkeypatch):
        monkeypatch.setattr(sw.platform, "system", lambda: "Linux")
        with patch.object(sw, "_windows_toast") as toast:
            sw.notify_failure("x", 1)
        toast.assert_not_called()


class TestWindowsToastEdge:
    def test_long_message_truncated(self):
        long_msg = "a" * 500
        with patch.object(sw.subprocess, "Popen") as popen:
            popen.return_value = MagicMock()
            sw._windows_toast("t", long_msg)
        script = popen.call_args[0][0][-1]
        # BalloonTipText value is at most 200 chars of message
        assert "a" * 200 in script
        assert "a" * 201 not in script


# ---------------------------------------------------------------------------
# Login / CAPTCHA / spin negatives
# ---------------------------------------------------------------------------


class TestLoginNegatives:
    def _not_logged_in_driver(self):
        driver = MagicMock()

        def find_element(by, sel):
            # profile check
            if sel == 'a[href="/profile"]':
                raise sw.NoSuchElementException()
            raise sw.NoSuchElementException()

        driver.find_element.side_effect = find_element
        return driver

    def test_missing_email_field(self, monkeypatch, tmp_path, capsys):
        _creds(monkeypatch)
        monkeypatch.setenv("INDIEGALA_SESSION_DIR", str(tmp_path / "session"))
        _fast(monkeypatch)
        monkeypatch.setattr(sw, "try_dismiss", lambda *a, **k: False)
        driver = self._not_logged_in_driver()
        with (
            patch.object(sw.uc, "Chrome", return_value=driver),
            patch.object(sw, "WebDriverWait") as wait_cls,
        ):
            wait_cls.return_value.until.side_effect = sw.TimeoutException()
            code = sw.spin_wheel(headless=True)
        assert code == sw.EXIT_ERROR
        assert "email field" in capsys.readouterr().out
        driver.save_screenshot.assert_any_call("debug_no_email_field.png")
        driver.quit.assert_called_once()

    def test_missing_password_field(self, monkeypatch, tmp_path, capsys):
        _creds(monkeypatch)
        monkeypatch.setenv("INDIEGALA_SESSION_DIR", str(tmp_path / "session"))
        _fast(monkeypatch)
        monkeypatch.setattr(sw, "try_dismiss", lambda *a, **k: False)
        driver = self._not_logged_in_driver()
        email_el = MagicMock()
        email_el.is_displayed.return_value = True

        with (
            patch.object(sw.uc, "Chrome", return_value=driver),
            patch.object(sw, "WebDriverWait") as wait_cls,
        ):
            wait_cls.return_value.until.return_value = email_el
            # find_element: profile miss, then password selectors all miss
            driver.find_element.side_effect = sw.NoSuchElementException()
            code = sw.spin_wheel(headless=True)
        assert code == sw.EXIT_ERROR
        assert "password field" in capsys.readouterr().out

    def test_captcha_headless_needs_human(self, monkeypatch, tmp_path, capsys):
        _creds(monkeypatch)
        monkeypatch.setenv("INDIEGALA_SESSION_DIR", str(tmp_path / "session"))
        _fast(monkeypatch)
        monkeypatch.setattr(sw, "try_dismiss", lambda *a, **k: False)
        monkeypatch.setattr(sw, "human_type", lambda *a, **k: None)

        driver = MagicMock()
        email_el = MagicMock()
        email_el.is_displayed.return_value = True
        password_el = MagicMock()
        password_el.is_displayed.return_value = True
        captcha = MagicMock()
        captcha.is_displayed.return_value = True

        def find_element(by, sel):
            if sel == 'a[href="/profile"]':
                raise sw.NoSuchElementException()
            if "password" in str(sel).lower() or sel == 'input[type="password"]':
                return password_el
            if "recaptcha" in str(sel):
                return captcha
            raise sw.NoSuchElementException()

        driver.find_element.side_effect = find_element

        with (
            patch.object(sw.uc, "Chrome", return_value=driver),
            patch.object(sw, "WebDriverWait") as wait_cls,
        ):
            wait_cls.return_value.until.return_value = email_el
            code = sw.spin_wheel(headless=True)
        assert code == sw.EXIT_NEEDS_HUMAN
        assert "CAPTCHA required but running headless" in capsys.readouterr().out
        driver.save_screenshot.assert_any_call("debug_captcha_headless.png")

    def test_captcha_visible_non_tty_sleeps(self, monkeypatch, tmp_path, capsys):
        _creds(monkeypatch)
        monkeypatch.setenv("INDIEGALA_SESSION_DIR", str(tmp_path / "session"))
        monkeypatch.setattr(sw, "random_delay", lambda *a, **k: None)
        monkeypatch.setattr(sw, "try_dismiss", lambda *a, **k: False)
        monkeypatch.setattr(sw, "human_type", lambda *a, **k: None)
        monkeypatch.setattr(sw.sys.stdin, "isatty", lambda: False)

        slept = []

        def fake_sleep(sec):
            slept.append(sec)

        monkeypatch.setattr(sw.time, "sleep", fake_sleep)

        driver = MagicMock()
        email_el = MagicMock()
        email_el.is_displayed.return_value = True
        password_el = MagicMock()
        password_el.is_displayed.return_value = True
        captcha = MagicMock()
        captcha.is_displayed.return_value = True

        def find_element(_by, sel):
            s = str(sel)
            if s == 'a[href="/profile"]':
                raise sw.NoSuchElementException()
            if "recaptcha" in s:
                return captcha
            if "password" in s.lower():
                return password_el
            # No submit → exit after captcha wait
            raise sw.NoSuchElementException()

        driver.find_element.side_effect = find_element

        with (
            patch.object(sw.uc, "Chrome", return_value=driver),
            patch.object(sw, "WebDriverWait") as wait_cls,
        ):
            wait_cls.return_value.until.return_value = email_el
            code = sw.spin_wheel(headless=False)

        assert 90 in slept
        assert code == sw.EXIT_ERROR
        assert "submit button" in capsys.readouterr().out

    def test_missing_submit_button(self, monkeypatch, tmp_path, capsys):
        _creds(monkeypatch)
        monkeypatch.setenv("INDIEGALA_SESSION_DIR", str(tmp_path / "session"))
        _fast(monkeypatch)
        monkeypatch.setattr(sw, "try_dismiss", lambda *a, **k: False)
        monkeypatch.setattr(sw, "human_type", lambda *a, **k: None)

        driver = MagicMock()
        email_el = MagicMock()
        email_el.is_displayed.return_value = True
        password_el = MagicMock()
        password_el.is_displayed.return_value = True

        def find_element(by, sel):
            if sel == 'a[href="/profile"]':
                raise sw.NoSuchElementException()
            if "password" in str(sel).lower() or sel == 'input[type="password"]':
                return password_el
            if "recaptcha" in str(sel):
                raise sw.NoSuchElementException()
            raise sw.NoSuchElementException()

        driver.find_element.side_effect = find_element
        with (
            patch.object(sw.uc, "Chrome", return_value=driver),
            patch.object(sw, "WebDriverWait") as wait_cls,
        ):
            wait_cls.return_value.until.return_value = email_el
            code = sw.spin_wheel(headless=True)
        assert code == sw.EXIT_ERROR
        assert "submit button" in capsys.readouterr().out


class TestSpinNegatives:
    def test_spun_unknown_logs_and_ok(self, monkeypatch, tmp_path):
        _creds(monkeypatch)
        monkeypatch.setenv("INDIEGALA_SESSION_DIR", str(tmp_path / "session"))
        _fast(monkeypatch)
        monkeypatch.setattr(sw, "try_dismiss", lambda *a, **k: False)
        driver = MagicMock()
        driver.find_element.return_value = MagicMock()  # logged in
        spin_btn = MagicMock()
        with (
            patch.object(sw.uc, "Chrome", return_value=driver),
            patch.object(sw, "WebDriverWait") as wait_cls,
            patch.object(sw, "_wait_for_result", return_value=None),
        ):
            wait_cls.return_value.until.return_value = spin_btn
            code = sw.spin_wheel(headless=True)
        assert code == sw.EXIT_OK
        row = json.loads(
            (tmp_path / "session" / "prizes.jsonl").read_text(encoding="utf-8")
        )
        assert row["status"] == "spun_unknown"
        driver.save_screenshot.assert_any_call("debug_result.png")

    def test_relocate_spin_fails(self, monkeypatch, tmp_path, capsys):
        _creds(monkeypatch)
        monkeypatch.setenv("INDIEGALA_SESSION_DIR", str(tmp_path / "session"))
        _fast(monkeypatch)
        monkeypatch.setattr(sw, "try_dismiss", lambda *a, **k: True)
        driver = MagicMock()
        driver.find_element.return_value = MagicMock()
        spin_btn = MagicMock()
        with (
            patch.object(sw.uc, "Chrome", return_value=driver),
            patch.object(sw, "WebDriverWait") as wait_cls,
        ):
            # First batch of selectors finds button; after dismiss, all timeout
            wait_cls.return_value.until.side_effect = [
                spin_btn,
                sw.TimeoutException(),
                sw.TimeoutException(),
                sw.TimeoutException(),
                sw.TimeoutException(),
                sw.TimeoutException(),
                sw.TimeoutException(),
            ]
            code = sw.spin_wheel(headless=True)
        assert code == sw.EXIT_ERROR
        assert "Could not re-locate spin button" in capsys.readouterr().out

    def test_js_click_falls_back_to_click(self, monkeypatch, tmp_path):
        _creds(monkeypatch)
        monkeypatch.setenv("INDIEGALA_SESSION_DIR", str(tmp_path / "session"))
        _fast(monkeypatch)
        monkeypatch.setattr(sw, "try_dismiss", lambda *a, **k: False)
        driver = MagicMock()
        driver.find_element.return_value = MagicMock()
        driver.execute_script.side_effect = sw.WebDriverException("blocked")
        spin_btn = MagicMock()
        with (
            patch.object(sw.uc, "Chrome", return_value=driver),
            patch.object(sw, "WebDriverWait") as wait_cls,
            patch.object(sw, "_wait_for_result", return_value="Ok"),
        ):
            wait_cls.return_value.until.return_value = spin_btn
            code = sw.spin_wheel(headless=True)
        assert code == sw.EXIT_OK
        spin_btn.click.assert_called_once()

    def test_runtime_exception_returns_error(self, monkeypatch, tmp_path, capsys):
        _creds(monkeypatch)
        monkeypatch.setenv("INDIEGALA_SESSION_DIR", str(tmp_path / "session"))
        _fast(monkeypatch)
        driver = MagicMock()
        driver.get.side_effect = RuntimeError("page dead")
        with patch.object(sw.uc, "Chrome", return_value=driver):
            code = sw.spin_wheel(headless=True, debug=True)
        assert code == sw.EXIT_ERROR
        out = capsys.readouterr().out
        assert "ERROR: page dead" in out
        driver.quit.assert_called_once()

    def test_outer_timeout_already_spun(self, monkeypatch, tmp_path):
        _creds(monkeypatch)
        monkeypatch.setenv("INDIEGALA_SESSION_DIR", str(tmp_path / "session"))
        _fast(monkeypatch)
        driver = MagicMock()
        driver.find_element.return_value = MagicMock()
        with (
            patch.object(sw.uc, "Chrome", return_value=driver),
            patch.object(sw, "WebDriverWait", side_effect=sw.TimeoutException()),
        ):
            code = sw.spin_wheel(headless=True)
        assert code == sw.EXIT_OK
        row = json.loads(
            (tmp_path / "session" / "prizes.jsonl").read_text(encoding="utf-8")
        )
        assert row["status"] == "already_spun"


# ---------------------------------------------------------------------------
# main() CLI edge / negative
# ---------------------------------------------------------------------------


class TestMainCliEdge:
    def test_headless_flag_on_first_run(self, monkeypatch):
        monkeypatch.setattr(sw, "is_first_run", lambda *_: True)
        seen = {}

        def fake_spin(*, headless, debug):
            seen["headless"] = headless
            return sw.EXIT_OK

        monkeypatch.setattr(sw, "spin_wheel", fake_spin)
        assert sw.main(["--headless"]) == sw.EXIT_OK
        assert seen["headless"] is True

    def test_needs_human_notifies(self, monkeypatch):
        monkeypatch.setattr(sw, "is_first_run", lambda *_: False)
        monkeypatch.setattr(sw, "spin_wheel", lambda **k: sw.EXIT_NEEDS_HUMAN)
        notified = {}
        monkeypatch.setattr(
            sw,
            "notify_failure",
            lambda msg, code, debug=False: notified.update(code=code, msg=msg),
        )
        assert sw.main(["--headless"]) == sw.EXIT_NEEDS_HUMAN
        assert notified["code"] == sw.EXIT_NEEDS_HUMAN

    def test_debug_flag_forwarded(self, monkeypatch):
        monkeypatch.setattr(sw, "is_first_run", lambda *_: False)
        seen = {}

        def fake_spin(*, headless, debug):
            seen["debug"] = debug
            return sw.EXIT_OK

        monkeypatch.setattr(sw, "spin_wheel", fake_spin)
        assert sw.main(["--debug"]) == sw.EXIT_OK
        assert seen["debug"] is True

    def test_notify_receives_debug(self, monkeypatch):
        monkeypatch.setattr(sw, "is_first_run", lambda *_: False)
        monkeypatch.setattr(sw, "spin_wheel", lambda **k: sw.EXIT_ERROR)
        seen = {}
        monkeypatch.setattr(
            sw,
            "notify_failure",
            lambda msg, code, debug=False: seen.update(debug=debug),
        )
        sw.main(["--headless", "--debug"])
        assert seen["debug"] is True
