"""Shared pieces for the automatic checks: a local copy of the website to open, and a browser (desktop or phone size)
with a pretend camera and a pretend text reader, so the card scanner can be tried without a real card.
"""
import contextlib
import functools
import http.server
import json
import os
import shutil
import tempfile
import threading
import urllib.parse

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SITE_FILES = ["index.html", "config.js", "manifest.webmanifest", "oauth.html", "share.html", "sw.js"]

# What the page gets in place of the real text reader: it "reads" whatever the test put in window.__ocrText.
FAKE_READER = """
window.__ocrText = "";
window.Tesseract = {createWorker: async () => ({
  setParameters: async () => {},
  recognize: async () => ({data: {text: window.__ocrText || ""}})
})};
"""


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@contextlib.contextmanager
def serve(directory):
    handler = functools.partial(Quiet, directory=directory)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:%d/" % server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()


def make_site(dest, mock=True, data_dir=None, zh=True):
    """Copy the website into dest. With mock data (the default) or the data files found in data_dir. zh=False leaves the Chinese list out."""
    os.makedirs(os.path.join(dest, "icons"), exist_ok=True)
    for name in SITE_FILES:
        shutil.copy(os.path.join(ROOT, name), dest)
    icons = os.path.join(ROOT, "icons")
    for name in os.listdir(icons):
        shutil.copy(os.path.join(icons, name), os.path.join(dest, "icons"))
    if data_dir:
        for name in ("tcgplayer-data.js", "tcgplayer-data-version.js", "zh-cards.js"):
            if os.path.exists(os.path.join(data_dir, name)):
                shutil.copy(os.path.join(data_dir, name), dest)
    elif mock:
        import make_mock_data
        make_mock_data.write(dest, zh=zh)
    else:
        # no card list at all: the website has to cope
        pass


class Browser:
    """One browser for the whole run; every test gets a fresh page (empty storage) at desktop or phone size."""

    def __init__(self, base_url, headless=True):
        self.base = base_url
        self.pw = sync_playwright().start()
        self.chromium = self.pw.chromium.launch(headless=headless, args=[
            "--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream", "--autoplay-policy=no-user-gesture-required"])

    def close(self):
        self.chromium.close()
        self.pw.stop()

    @contextlib.contextmanager
    def page(self, kind="desktop", seed=None, fake_reader=True, camera=True, path="", base=None):
        """seed: {"collection": [...], "settings": {...}, "wants": [...], "goals": [...]} written to storage before the page starts."""
        if kind == "phone":
            ctx = self.chromium.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True,
                                            service_workers="block", permissions=["camera"] if camera else [])
        else:
            ctx = self.chromium.new_context(viewport={"width": 1280, "height": 900}, service_workers="block",
                                            permissions=["camera"] if camera else [])
        base = base or self.base
        errors = []
        page = ctx.new_page()
        page.problems = errors
        page.on("pageerror", lambda e: errors.append("page error: %s" % e))
        page.on("console", lambda m: errors.append("console error: %s" % m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)
        # nothing outside the local copy is reachable (pictures, fonts, the real text reader): answer those with nothing.
        # PriceCharting is pretended: page.pc_key is the one key it accepts, page.pc_items maps a PriceCharting id to the fields
        # of its answer, and page.pc_calls lists what was asked.
        page.pc_key, page.pc_items, page.pc_calls = "TESTKEY", {}, []
        def outside(route):
            url = route.request.url
            if url.startswith(base) or url.startswith("data:") or url.startswith("blob:"):
                route.continue_()
            elif url.startswith("https://www.pricecharting.com/api/"):
                parts = urllib.parse.urlparse(url)
                q = urllib.parse.parse_qs(parts.query)
                page.pc_calls.append(url)
                if (q.get("t") or [""])[0] != page.pc_key:
                    status, body = 403, {"error": "Unknown access token", "error-message": "Unknown access token", "status": "error"}
                elif parts.path.endswith("/product"):
                    item = page.pc_items.get(int((q.get("id") or ["0"])[0]))
                    status, body = (200, dict(item, status="success")) if item else (404, {"status": "error", "error-message": "No such product"})
                else:
                    status, body = 200, {"status": "success", "products": []}
                route.fulfill(status=status, headers={"access-control-allow-origin": "*"}, content_type="application/json", body=json.dumps(body))
            else:
                route.abort()
        page.route("**/*", outside)
        if fake_reader:
            page.add_init_script(FAKE_READER)
        if not camera:
            # a browser with no camera at all: typing the number is the only way
            page.add_init_script("Object.defineProperty(navigator, 'mediaDevices', {get: () => undefined});")
        if seed:
            keys = {"collection": "pokevault.v1.collection", "settings": "pokevault.v1.settings", "wants": "pokevault.v1.wants",
                    "decks": "pokevault.v1.decks", "goals": "pokevault.v1.goals", "sales": "pokevault.v1.sales",
                    "valueHistory": "pokevault.v1.valueHistory"}
            sets = {keys[k]: json.dumps(v) for k, v in seed.items()}
            page.add_init_script("(() => { try { if (sessionStorage.getItem('__seeded')) return; sessionStorage.setItem('__seeded', '1'); "
                                 "const s = %s; for (const k in s) localStorage.setItem(k, s[k]); } catch (e) {} })();" % json.dumps(sets))
        page.goto(base + path)
        page.wait_for_function("window.CardVault && window.CardVault.state().catalog !== undefined", timeout=20000)
        try:
            yield page
        finally:
            ctx.close()


# ---- a very small test runner: @test registers a function that gets (browser, kind); phone=True runs it on both sizes
TESTS = []


def test(name=None, phone=False, slow=False, smoke=False):
    def wrap(fn):
        TESTS.append({"name": name or fn.__name__, "fn": fn, "phone": phone, "slow": slow, "smoke": smoke})
        return fn
    return wrap


def check(cond, message):
    if not cond:
        raise AssertionError(message)


def no_problems(page):
    check(not page.problems, "the page reported problems: %s" % "; ".join(page.problems[:3]))
