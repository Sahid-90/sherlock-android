"""
Sherlock Android App - built with Kivy
Search for usernames across social networks
"""

import threading
import requests
import json
import os

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


# ─── Sherlock data URL ───────────────────────────────────────────────────────
DATA_URL = (
    "https://raw.githubusercontent.com/sherlock-project/sherlock/"
    "main/sherlock/resources/data.json"
)
LOCAL_DATA = "data.json"


def load_sites():
    """Load site data from local cache or remote URL."""
    if os.path.exists(LOCAL_DATA):
        with open(LOCAL_DATA, "r", encoding="utf-8") as f:
            return json.load(f)
    try:
        resp = requests.get(DATA_URL, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        with open(LOCAL_DATA, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return data
    except Exception as e:
        return {}


def check_username(site_name, site_data, username, results, lock):
    """Check if username exists on a single site."""
    url_template = site_data.get("url", "")
    if not url_template:
        return

    url = url_template.format(username)
    error_type = site_data.get("errorType", "status_code")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        resp = requests.get(url, headers=headers, timeout=10, allow_redirects=True)

        found = False
        if error_type == "status_code":
            found = resp.status_code == 200
        elif error_type == "errorMsg":
            error_msg = site_data.get("errorMsg", "")
            found = error_msg not in resp.text
        elif error_type == "profilePresence":
            found = resp.status_code == 200

        if found:
            with lock:
                results.append({"site": site_name, "url": url, "status": "FOUND"})
    except Exception:
        pass  # Network errors are silently ignored


# ─── UI ──────────────────────────────────────────────────────────────────────

class ResultRow(BoxLayout):
    def __init__(self, site, url, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = dp(48)
        self.padding = [dp(8), dp(4)]
        self.spacing = dp(8)

        site_lbl = Label(
            text=f"[b]{site}[/b]",
            markup=True,
            size_hint_x=0.3,
            halign="left",
            valign="middle",
            color=get_color_from_hex("#4CAF50"),
        )
        site_lbl.bind(size=site_lbl.setter("text_size"))

        url_lbl = Label(
            text=url,
            size_hint_x=0.55,
            halign="left",
            valign="middle",
            color=get_color_from_hex("#ECEFF1"),
            font_size="12sp",
        )
        url_lbl.bind(size=url_lbl.setter("text_size"))

        copy_btn = Button(
            text="Copy",
            size_hint_x=0.15,
            background_color=get_color_from_hex("#37474F"),
            font_size="12sp",
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

        # ── Title ────────────────────────────────────────────────────────────
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
            height=dp(24),
            font_size="13sp",
            color=get_color_from_hex("#90A4AE"),
        )

        # ── Input row ────────────────────────────────────────────────────────
        input_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(48),
            spacing=dp(8),
        )
        self.username_input = TextInput(
            hint_text="Enter username...",
            multiline=False,
            size_hint_x=0.7,
            font_size="16sp",
            background_color=get_color_from_hex("#263238"),
            foreground_color=get_color_from_hex("#ECEFF1"),
        )
        self.username_input.bind(on_text_validate=self.start_search)

        self.search_btn = Button(
            text="Search",
            size_hint_x=0.3,
            background_color=get_color_from_hex("#1565C0"),
            font_size="15sp",
        )
        self.search_btn.bind(on_release=self.start_search)

        input_row.add_widget(self.username_input)
        input_row.add_widget(self.search_btn)

        # ── Progress bar ─────────────────────────────────────────────────────
        self.progress = ProgressBar(
            max=100, value=0, size_hint_y=None, height=dp(8)
        )
        self.status_label = Label(
            text="Enter a username and tap Search",
            size_hint_y=None,
            height=dp(24),
            font_size="12sp",
            color=get_color_from_hex("#78909C"),
        )

        # ── Results header ───────────────────────────────────────────────────
        header_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(32),
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

        # ── Scrollable results ────────────────────────────────────────────────
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

        # ── Add all to main layout ────────────────────────────────────────────
        self.add_widget(title)
        self.add_widget(sub)
        self.add_widget(input_row)
        self.add_widget(self.progress)
        self.add_widget(self.status_label)
        self.add_widget(header_row)
        self.add_widget(scroll)

        # ── State ─────────────────────────────────────────────────────────────
        self._running = False
        self._pending_rows = []
        self._lock = threading.Lock()
        Clock.schedule_interval(self._flush_results, 0.3)

    # ── Search logic ──────────────────────────────────────────────────────────

    def start_search(self, *args):
        if self._running:
            return
        username = self.username_input.text.strip()
        if not username:
            self.status_label.text = "⚠️  Please enter a username."
            return

        self.results_layout.clear_widgets()
        self._pending_rows.clear()
        self.progress.value = 0
        self.search_btn.disabled = True
        self._running = True
        self.status_label.text = "⏳ Loading site data..."

        threading.Thread(target=self._run_search, args=(username,), daemon=True).start()

    def _run_search(self, username):
        sites = load_sites()
        if not sites:
            Clock.schedule_once(
                lambda dt: setattr(
                    self.status_label, "text", "❌ Failed to load site data. Check internet."
                )
            )
            self._running = False
            return

        total = len(sites)
        results = []
        lock = threading.Lock()
        threads = []
        done = [0]

        def worker(name, data):
            check_username(name, data, username, results, lock)
            with lock:
                done[0] += 1
                pct = int(done[0] / total * 100)
            Clock.schedule_once(lambda dt, p=pct: self._update_progress(p, done[0], total))

        # Limit concurrency to 50 threads
        sem = threading.Semaphore(50)

        def sem_worker(name, data):
            with sem:
                worker(name, data)

        for name, data in sites.items():
            t = threading.Thread(target=sem_worker, args=(name, data), daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        with self._lock:
            self._pending_rows.extend(results)

        Clock.schedule_once(lambda dt: self._search_done(len(results), username))

    def _update_progress(self, pct, done, total):
        self.progress.value = pct
        self.status_label.text = f"🔍 Checking... {done}/{total} sites"

    def _flush_results(self, dt):
        with self._lock:
            rows = self._pending_rows[:]
            self._pending_rows.clear()
        for r in rows:
            self.results_layout.add_widget(ResultRow(r["site"], r["url"]))

    def _search_done(self, count, username):
        self.progress.value = 100
        self.status_label.text = f"✅ Done! Found [b]{count}[/b] results for '{username}'"
        self.search_btn.disabled = False
        self._running = False


# ─── App ─────────────────────────────────────────────────────────────────────

class SherlockApp(App):
    def build(self):
        from kivy.core.window import Window
        Window.clearcolor = get_color_from_hex("#1A2027")
        return SherlockLayout()


if __name__ == "__main__":
    SherlockApp().run()
