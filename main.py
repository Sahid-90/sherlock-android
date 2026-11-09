"""
Sherlock Android App - built with Kivy
Search for usernames across social networks
Stable version: crash-safe, Android-optimised
"""

import threading
import requests
import json
import os
import ssl

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.progressbar import ProgressBar
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.metrics import dp
from kivy.utils import get_color_from_hex

# ─── Constants ────────────────────────────────────────────────────────────────
DATA_URL = (
    "https://raw.githubusercontent.com/sherlock-project/sherlock/"
    "main/sherlock/resources/data.json"
)
LOCAL_DATA = "data.json"
MAX_THREADS = 20          # Safe for Android (was 50)
REQUEST_TIMEOUT = 8       # seconds


# ─── Helpers ──────────────────────────────────────────────────────────────────

def safe_get(url, headers, timeout):
    """HTTP GET that never raises — returns (status_code, text) or None."""
    try:
        # verify=False avoids SSL cert issues on some Android versions
        resp = requests.get(
            url, headers=headers, timeout=timeout,
            allow_redirects=True, verify=False
        )
        return resp.status_code, resp.text
    except Exception:
        return None


def load_sites():
    """Load site data from local cache or remote URL."""
    if os.path.exists(LOCAL_DATA):
        try:
            with open(LOCAL_DATA, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass  # Corrupted cache — re-download

    try:
        result = safe_get(DATA_URL, {}, 15)
        if result is None:
            return {}
        _, text = result
        data = json.loads(text)
        with open(LOCAL_DATA, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return data
    except Exception:
        return {}


def check_username(site_name, site_data, username, results, lock):
    """Check if username exists on a single site. Never raises."""
    url_template = site_data.get("url", "")
    if not url_template:
        return

    try:
        url = url_template.format(username)
    except Exception:
        return

    error_type = site_data.get("errorType", "status_code")
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 11) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Mobile Safari/537.36"
        )
    }

    result = safe_get(url, headers, REQUEST_TIMEOUT)
    if result is None:
        return

    status_code, text = result
    found = False

    if error_type == "status_code":
        found = (status_code == 200)
    elif error_type == "errorMsg":
        error_msg = site_data.get("errorMsg", "")
        found = bool(error_msg) and (error_msg not in text)
    elif error_type == "profilePresence":
        found = (status_code == 200)

    if found:
        with lock:
            results.append({"site": site_name, "url": url})


# ─── UI Components ────────────────────────────────────────────────────────────

class ResultRow(BoxLayout):
    def __init__(self, site, url, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = dp(50)
        self.padding = [dp(8), dp(4)]
        self.spacing = dp(6)

        site_lbl = Label(
            text=f"[b]{site}[/b]",
            markup=True,
            size_hint_x=0.3,
            halign="left",
            valign="middle",
            color=get_color_from_hex("#4CAF50"),
            font_size="13sp",
        )
        site_lbl.bind(size=site_lbl.setter("text_size"))

        url_lbl = Label(
            text=url,
            size_hint_x=0.55,
            halign="left",
            valign="middle",
            color=get_color_from_hex("#ECEFF1"),
            font_size="11sp",
        )
        url_lbl.bind(size=url_lbl.setter("text_size"))

        copy_btn = Button(
            text="Copy",
            size_hint_x=0.15,
            background_color=get_color_from_hex("#37474F"),
            font_size="11sp",
        )
        copy_btn.bind(on_release=lambda *a: Clipboard.copy(url))

        self.add_widget(site_lbl)
        self.add_widget(url_lbl)
        self.add_widget(copy_btn)


class SherlockLayout(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.padding = dp(12)
        self.spacing = dp(8)

        # Title
        title = Label(
            text="🔍 [b]Sherlock[/b]",
            markup=True,
            size_hint_y=None,
            height=dp(50),
            font_size="24sp",
            color=get_color_from_hex("#64B5F6"),
        )
        sub = Label(
            text="Username Search Across Social Networks",
            size_hint_y=None,
            height=dp(22),
            font_size="12sp",
            color=get_color_from_hex("#90A4AE"),
        )

        # Input row
        input_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(50),
            spacing=dp(8),
        )
        self.username_input = TextInput(
            hint_text="Enter username...",
            multiline=False,
            size_hint_x=0.68,
            font_size="16sp",
            background_color=get_color_from_hex("#263238"),
            foreground_color=get_color_from_hex("#ECEFF1"),
            cursor_color=get_color_from_hex("#64B5F6"),
        )
        self.username_input.bind(on_text_validate=self.start_search)

        self.search_btn = Button(
            text="Search",
            size_hint_x=0.32,
            background_color=get_color_from_hex("#1565C0"),
            font_size="15sp",
        )
        self.search_btn.bind(on_release=self.start_search)

        input_row.add_widget(self.username_input)
        input_row.add_widget(self.search_btn)

        # Progress
        self.progress = ProgressBar(
            max=100, value=0, size_hint_y=None, height=dp(8)
        )
        self.status_label = Label(
            text="Enter a username and tap Search",
            size_hint_y=None,
            height=dp(26),
            font_size="12sp",
            color=get_color_from_hex("#78909C"),
        )

        # Results header
        header_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(30),
            padding=[dp(8), 0],
        )
        for txt, sx in [("Site", 0.3), ("URL", 0.55), ("", 0.15)]:
            lbl = Label(
                text=f"[b]{txt}[/b]",
                markup=True,
                size_hint_x=sx,
                halign="left",
                valign="middle",
                color=get_color_from_hex("#78909C"),
                font_size="12sp",
            )
            lbl.bind(size=lbl.setter("text_size"))
            header_row.add_widget(lbl)

        # Scrollable results
        self.results_layout = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(2),
        )
        self.results_layout.bind(
            minimum_height=self.results_layout.setter("height")
        )
        scroll = ScrollView()
        scroll.add_widget(self.results_layout)

        self.add_widget(title)
        self.add_widget(sub)
        self.add_widget(input_row)
        self.add_widget(self.progress)
        self.add_widget(self.status_label)
        self.add_widget(header_row)
        self.add_widget(scroll)

        # State
        self._running = False
        self._pending_rows = []
        self._lock = threading.Lock()
        Clock.schedule_interval(self._flush_results, 0.5)

    def start_search(self, *args):
        if self._running:
            return
        username = self.username_input.text.strip()
        if not username:
            self.status_label.text = "⚠️  Please enter a username."
            return

        self.results_layout.clear_widgets()
        with self._lock:
            self._pending_rows.clear()
        self.progress.value = 0
        self.search_btn.disabled = True
        self._running = True
        self.status_label.text = "⏳ Loading site data..."

        t = threading.Thread(target=self._run_search, args=(username,), daemon=True)
        t.start()

    def _run_search(self, username):
        try:
            sites = load_sites()
            if not sites:
                Clock.schedule_once(lambda dt: self._set_status(
                    "❌ Could not load data. Check internet connection."
                ))
                self._finish()
                return

            total = len(sites)
            results = []
            lock = threading.Lock()
            done_count = [0]

            sem = threading.Semaphore(MAX_THREADS)

            def worker(name, data):
                try:
                    check_username(name, data, username, results, lock)
                finally:
                    with lock:
                        done_count[0] += 1
                        pct = int(done_count[0] / total * 100)
                        cnt = done_count[0]
                    Clock.schedule_once(
                        lambda dt, p=pct, c=cnt: self._update_progress(p, c, total)
                    )
                    sem.release()

            threads = []
            for name, data in sites.items():
                sem.acquire()
                t = threading.Thread(target=worker, args=(name, data), daemon=True)
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

            with self._lock:
                self._pending_rows.extend(results)

            found = len(results)
            Clock.schedule_once(lambda dt, f=found: self._search_done(f, username))

        except Exception as e:
            Clock.schedule_once(lambda dt, err=str(e): self._set_status(f"❌ Error: {err}"))
            self._finish()

    def _update_progress(self, pct, done, total):
        self.progress.value = pct
        self.status_label.text = f"🔍 Checking... {done}/{total} sites"

    def _set_status(self, msg):
        self.status_label.text = msg

    def _flush_results(self, dt):
        with self._lock:
            rows = self._pending_rows[:]
            self._pending_rows.clear()
        for r in rows:
            self.results_layout.add_widget(ResultRow(r["site"], r["url"]))

    def _search_done(self, count, username):
        self.progress.value = 100
        self.status_label.text = f"✅ Done! Found {count} results for '{username}'"
        self.search_btn.disabled = False
        self._running = False

    def _finish(self):
        Clock.schedule_once(lambda dt: self._do_finish())

    def _do_finish(self):
        self.search_btn.disabled = False
        self._running = False


# ─── App ─────────────────────────────────────────────────────────────────────

class SherlockApp(App):
    def build(self):
        # Suppress SSL warnings from requests (verify=False)
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        from kivy.core.window import Window
        Window.clearcolor = get_color_from_hex("#1A2027")
        return SherlockLayout()


if __name__ == "__main__":
    SherlockApp().run()
