#!/usr/bin/env python3
"""Fee watch: has a grading company changed its prices?

Pokémon Vault has each grading company's price list built in (Settings > Grading fees). Companies change
their prices now and then, so once a day the website's update looks at each company's public price page and
remembers a "fingerprint" of the page: just the dollar amounts and the turnaround times on it, in order
(not the wording or the layout, so a new banner or a redesign doesn't count).

When the fingerprint changes, and the new one is still there on a later day (so a one-day banner or a page
glitch doesn't count), the website's Settings say "PSA's fees may have changed since <the day the list was
checked>". The app never reads prices off these pages itself; it only tells you to go and look.

This writes fee-watch.json, which the daily workflow publishes with the website. The file also carries what
the next run needs (the last fingerprints), and each run starts from the file it left behind: from the
workflow's saved copy, or else from the file on the live website. It never fails the daily update: a page
that is down or unreadable is just noted and tried again tomorrow.

Needs only Python 3.8 or newer, with nothing to install.
"""
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser

PAGES = {
    "PSA": "https://www.psacard.com/services/tradingcardgrading",
    "BGS": "https://www.beckett.com/grading",
    "CGC": "https://www.cgcgrading.com/submit/services/",
    "SGC": "https://gosgc.com/card-grading/services-pricing",
    "TAG": "https://taggrading.com/pages/pricing",
}
OUT = "fee-watch.json"
USER_AGENT = "Mozilla/5.0 (compatible; PokemonVaultFeeWatch/1.0)"
MIN_PRICES = 3   # a price page with fewer dollar amounts than this probably didn't load its prices (they may be added by script)
MONEY = re.compile(r"\$\s?\d[\d,]*(?:\.\d{1,2})?")
DAYS = re.compile(r"\b\d{1,3}(?:\s?[-–]\s?\d{1,3})?\+?\s*(?:business\s+)?days?\b", re.I)


class Text(HTMLParser):
    """The words a visitor sees on a page (no scripts, styles or page head)."""
    SKIP = {"script", "style", "noscript", "template", "svg", "head", "iframe"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.depth += 1
        elif tag in ("br", "p", "div", "li", "tr", "td", "th", "h1", "h2", "h3", "h4"):
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.depth:
            self.depth -= 1
        elif tag in ("p", "div", "li", "tr", "td", "th"):
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.depth:
            self.parts.append(data)


def fingerprint(html):
    """(hash, number of dollar amounts) of a price page, or (None, n) when it has too few amounts to be the price list."""
    p = Text()
    p.feed(html)
    text = re.sub(r"\s+", " ", " ".join(p.parts))
    prices = [re.sub(r"\s", "", m).lower() for m in MONEY.findall(text)]
    days = [re.sub(r"\s", "", m).lower() for m in DAYS.findall(text)]
    if len(prices) < MIN_PRICES:
        return None, len(prices)
    return hashlib.sha256("|".join(prices + ["//"] + days).encode()).hexdigest()[:16], len(prices)


def fetch(url, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.8"})
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read(5_000_000)
                charset = r.headers.get_content_charset() or "utf-8"
                return raw.decode(charset, errors="replace")
        except Exception as e:  # a page that's down is not our problem; try again tomorrow
            last = e
            time.sleep(2 + 3 * i)
    raise last


def load_prior():
    """What the last run left: the saved file here, else the live website's copy."""
    try:
        with open(OUT, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        pass
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    url = os.environ.get("FEE_WATCH_PRIOR_URL") or (("https://%s.github.io/%s/%s" % (repo.split("/")[0].lower(), repo.split("/")[1], OUT)) if "/" in repo else "")
    if url:
        try:
            return json.loads(fetch(url, tries=1))
        except Exception:
            pass
    return {}


def main():
    pages = json.loads(os.environ["FEE_WATCH_PAGES"]) if os.environ.get("FEE_WATCH_PAGES") else PAGES
    today = os.environ.get("FEE_WATCH_TODAY") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    prior = (load_prior().get("companies") or {})
    out = {}
    for co, url in pages.items():
        was = prior.get(co) if isinstance(prior.get(co), dict) else {}
        cur = {"status": "unreachable", "hash": was.get("hash"), "prices": was.get("prices"), "since": was.get("since"),
               "seen": was.get("seen"), "pending": was.get("pending"), "changed": was.get("changed")}
        try:
            h, n = fingerprint(fetch(url))
            if h is None:
                cur["status"] = "unreadable"
            else:
                cur.update(status="ok", seen=today, prices=n)
                if not was.get("hash"):
                    cur.update(hash=h, since=today, pending=None)   # the first look: this is what the list looks like now
                elif h == was["hash"]:
                    cur["pending"] = None
                else:
                    pend = was.get("pending") or {}
                    if pend.get("hash") == h and pend.get("first") and pend["first"] != today:
                        # the same new page on a second day: a real change, noticed on the first day it was seen
                        cur.update(hash=h, since=pend["first"], changed=pend["first"], pending=None)
                    elif pend.get("hash") == h:
                        pass   # (a second look on the same day)
                    else:
                        cur["pending"] = {"hash": h, "first": today}
        except Exception as e:
            print("%s: couldn't read %s (%s)" % (co, url, e))
        out[co] = cur
        print("%s: %s%s%s" % (co, cur["status"], ", %s dollar amounts" % cur["prices"] if cur["status"] == "ok" else "",
                              ", changed %s" % cur["changed"] if cur.get("changed") else ""))
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "companies": out}, f, indent=1)
        f.write("\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # never fail the daily update
        print("fee_watch.py: skipped (%s)" % e)
    sys.exit(0)
