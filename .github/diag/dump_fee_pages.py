#!/usr/bin/env python3
"""One-off: save what the five grading companies' price pages say (their visible text), so the built-in fee table can be re-checked
against the real wording. Writes out/fee-pages.json. Reuses fee_watch.py's page reading (plain download first, then a browser)."""
import json
import os
import re
import sys

sys.path.insert(0, os.getcwd())
import fee_watch as fw

PAGES = dict(fw.PAGES)
PAGES["TAG_submit"] = "https://taggrading.com/pages/submit"
PAGES["BGS_maintenance"] = "https://maintenance.beckett.com/"
PAGES["PSA_updates"] = "https://www.psacard.com/info/submission-updates"
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
    except Exception as e:
        entry["error"] = str(e)[:120]
    if text is None or len(fw.MONEY.findall(text)) < fw.MIN_PRICES:
        try:
            t2 = fw.browser_text(url)
            if t2:
                text, entry["via"] = t2, "browser"
        except Exception as e:
            entry["error"] += " | browser: " + str(e)[:120]
    if text:
        text = re.sub(r"[ \t\r\f\v]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n", text).strip()
        entry["dollars"] = len(fw.MONEY.findall(text))
        entry["text"] = text[:30000]
    result[key] = entry
    print(key, entry["via"], entry["dollars"], len(entry["text"]), entry["error"])
json.dump(result, open("out/fee-pages.json", "w"), indent=1, ensure_ascii=False)
