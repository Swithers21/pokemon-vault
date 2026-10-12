"""One-off: run the app's Pokémon-name matching on the REAL TCGplayer card list (downloaded from the live site) and write a report."""
import json, subprocess, sys, time, threading, http.server, socketserver, os, functools
from playwright.sync_api import sync_playwright

ROOT = sys.argv[1]
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
handler = functools.partial(Q, directory=ROOT)
srv = socketserver.ThreadingTCPServer(("127.0.0.1", 8811), handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()

NAMES = ["Pikachu", "Mew", "Mewtwo", "Charizard", "Mr. Mime", "Eevee", "Ho-Oh", "Farfetch'd", "Nidoran", "Flabébé", "Gardevoir", "Lugia"]
TYPED = ["pika", "mew", "char", "mime", "eevee", "mega", "nidor", "porygon", "ash", "farfetch"]
report = {}
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_context(viewport={"width": 1280, "height": 900}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    t0 = time.time()
    pg.goto("http://127.0.0.1:8811/index.html", wait_until="load", timeout=180000)
    pg.wait_for_function("() => window.CardVault && window.CardVault.state().catalog", timeout=180000)
    report["load_seconds"] = round(time.time() - t0, 1)
    report["products"] = pg.evaluate("() => window.CardVault.state().catalog.products.length")
    report["groups"] = pg.evaluate("() => window.CardVault.state().catalog.groups.length")
    report["names"] = {}
    for n in NAMES:
        r = pg.evaluate("""n => { const C = window.CardVault; const t0 = performance.now();
          const all = C.monPrints(n, ''); const ms = performance.now() - t0;
          const en = C.monPrints(n, 'en').length, jp = C.monPrints(n, 'jp').length;
          const names = {}; for (const p of all) { const k = p.name.replace(/\\s+-\\s+[A-Za-z]{0,6}\\s?\\d{1,4}[A-Za-z]{0,2}(?:\\s?\\/\\s?[A-Za-z]{0,6}\\d{1,4}[A-Za-z]{0,2})?\\s*$/, ''); names[k] = (names[k] || 0) + 1; }
          const types = {}; for (const p of all) types[p.ctype || '(none)'] = (types[p.ctype || '(none)'] || 0) + 1;
          return {total: all.length, en, jp, sets: new Set(all.map(p => p.group.id)).size, first_ms: Math.round(ms), distinct: Object.keys(names).length,
                  names: Object.entries(names).sort((a, b) => b[1] - a[1]).slice(0, 70), types}; }""", n)
        report["names"][n] = r
    report["typed"] = {}
    for t in TYPED:
        r = pg.evaluate("""t => { const t0 = performance.now(); const c = window.CardVault.monCandidates(t); return {ms: Math.round(performance.now() - t0), c: c.map(x => x.name + ' (' + x.n + ')')}; }""", t)
        report["typed"][t] = r
    report["errors"] = errs
    b.close()
os.makedirs("out", exist_ok=True)
json.dump(report, open("out/mon-report.json", "w"), indent=1, ensure_ascii=False)
print("report written; products", report["products"])
