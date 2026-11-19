#!/usr/bin/env python3
"""Copies what the grading companies' price pages say (only the parts near prices and notices about being paused, closed or
reopening), so the website's built-in fee table can be re-checked against the real wording. It reads the pages the same way the daily
fee watch does (fee_watch.py: a plain download first, then a real browser). Writes out/fee-pages.json.

Run by the "Copy the grading price pages" workflow (Actions tab > Run workflow), which keeps the copy on a branch called
"diagnostics". It doesn't change the website."""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fee_watch as fw  # noqa: E402

PAGES = dict(fw.PAGES)
PAGES["PSA_updates"] = "https://www.psacard.com/info/submission-updates"
PAGES["BGS_maintenance"] = "https://maintenance.beckett.com/"
NOTICE = re.compile(r"paused|pause|closed|sold out|reopen|re-open|resum|maintenance|unavailable|wait ?list|limited|membership|increas|price change|per card|per item|business days", re.I)
BEFORE, AFTER, LIMIT = 140, 120, 9000


def near_prices(text):
    """The stretches of the page around a dollar amount or a notice, joined up (the menus and footers fall away)."""
    spans = [(max(0, m.start() - BEFORE), min(len(text), m.end() + AFTER)) for m in list(fw.MONEY.finditer(text)) + list(NOTICE.finditer(text))]
    spans.sort()
    merged = []
    for a, b in spans:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    out = " [...] ".join(re.sub(r"\s+", " ", text[a:b]).strip() for a, b in merged)
    return out[:LIMIT]


def main():
    os.makedirs("out", exist_ok=True)
    result = {}
    for key, url in PAGES.items():
        entry = {"url": url, "via": None, "dollars": 0, "text": "", "error": ""}
        text = None
        try:
            html = fw.fetch(url, tries=2)
            p = fw.Text()
            p.feed(html)
            text = " ".join(p.parts)
            entry["via"] = "plain"
        except Exception as e:  # noqa: BLE001
            entry["error"] = str(e)[:120]
        if text is None or len(fw.MONEY.findall(text)) < fw.MIN_PRICES:
            try:
                t2 = fw.browser_text(url)
                if t2:
                    text, entry["via"] = t2, "browser"
            except Exception as e:  # noqa: BLE001
                entry["error"] += " | browser: " + str(e)[:120]
        if text:
            entry["dollars"] = len(fw.MONEY.findall(text))
            entry["text"] = near_prices(text)
        result[key] = entry
        print(key, entry["via"], entry["dollars"], len(entry["text"]), entry["error"])
    with open("out/fee-pages.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
