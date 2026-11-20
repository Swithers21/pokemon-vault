#!/usr/bin/env python3
"""
Pokemon Vault - Chinese (Simplified) card list updater
======================================================

TCGplayer has no Chinese Pokemon cards, so the list of them (set, name, card number and the address of each card's
picture) comes from PriceCharting's public set pages ("Pokemon Chinese CSV8C" and so on) and is saved next to
index.html as zh-cards.js. Pokemon Vault reads that file when it opens.

What is NOT saved: prices. PriceCharting's terms only allow its price data in an app other people can open with their
permission, so Chinese prices are never kept on the website. Pokemon Vault asks PriceCharting for them from your own
browser, with your own PriceCharting key (Settings), and keeps them only on your device.

The updater is gentle: it pauses between requests, identifies itself, and only looks again once a week (new sets are
rare). If PriceCharting can't be read, or a page comes back with far fewer cards than before, the last good list is kept.

  python update_zh_cards.py            refresh if the list is older than a week
  python update_zh_cards.py --force    refresh now

Only Python's standard library is used.
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from datetime import datetime, timezone

VERSION = "1.0"
DATA_FORMAT = 1
OUT_FILE = os.environ.get("POKEVAULT_ZH_FILE", "zh-cards.js")
BASE = os.environ.get("POKEVAULT_PC_BASE", "https://www.pricecharting.com").rstrip("/")
USER_AGENT = "PokemonVault/%s (personal Pokemon card collection tracker; https://github.com/Swithers21/pokemon-vault)" % VERSION
PAUSE = float(os.environ.get("POKEVAULT_PC_PAUSE", "1.2"))
MAX_AGE_DAYS = 6
MAX_PAGES = 40         # pages per set (150 cards each); the biggest sets have a few hundred cards
KEEP_AT_LEAST = 0.7    # a new list with fewer than this share of the old cards is not trusted


def log(msg):
    print(msg, flush=True)


_last = [0.0]


def fetch(url, data=None, tries=3):
    """The page's text. Raises after a few tries."""
    last = None
    for attempt in range(tries):
        wait = _last[0] + PAUSE - time.time()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT, "Accept-Language": "en"})
        try:
            with urllib.request.urlopen(req, timeout=45) as res:
                return res.read(8_000_000).decode("utf-8", "replace")
        except (urllib.error.URLError, OSError) as e:
            last = e
            time.sleep(2 + attempt * 3)
    raise RuntimeError("couldn't read %s: %s" % (url, last))


def text_of(html):
    html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


ROW = re.compile(r'<tr id="product-(\d+)"(.*?)</tr>', re.S)
HREF = re.compile(r'/game/([a-z0-9\-.]+)/([a-z0-9\-.%]+)', re.I)
IMG = re.compile(r'images\.pricecharting\.com/([A-Za-z0-9]+)/\d+\.jpg')
TITLE = re.compile(r'<td class="title"[^>]*>\s*<a [^>]*>(.*?)</a>', re.S)
NEXT_FORM = re.compile(r'<form[^>]*class="[^"]*js-next-page[^"]*"[^>]*>(.*?)</form>', re.S)
HIDDEN = re.compile(r'<input type="hidden" name="([^"]*)" value="([^"]*)"')


def unescape(s):
    return (s.replace("&amp;", "&").replace("&#39;", "'").replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">")
            .replace("&eacute;", "e").replace("&#233;", "e"))


def split_title(title):
    """'Carmine #255' -> ('Carmine', '255'); 'Pikachu [Reverse Holo] #25' -> ('Pikachu (Reverse Holo)', '25'); sealed items have no number."""
    title = unescape(re.sub(r"<[^>]+>", "", title)).strip()
    m = re.search(r"#\s*([A-Za-z0-9][A-Za-z0-9.\-]*)\s*$", title)
    number = m.group(1) if m else ""
    base = title[:m.start()].strip() if m else title
    tags = re.findall(r"\[([^\]]+)\]", base)
    base = re.sub(r"\s*\[[^\]]*\]", "", base).strip()
    if tags:
        base += " (" + ", ".join(t.strip() for t in tags) + ")"
    return base, number


def parse_rows(html):
    """Every card or product in a set page: [{id, console, slug, name, number, image}]."""
    out = []
    for m in ROW.finditer(html):
        body = m.group(2)
        href = HREF.search(body)
        img = IMG.search(body)
        t = TITLE.search(body)
        if not (href and t):
            continue
        name, number = split_title(t.group(1))
        if not name:
            continue
        out.append({"id": int(m.group(1)), "console": href.group(1), "slug": href.group(2), "name": name, "number": number,
                    "image": img.group(1) if img else ""})
    return out


def next_page_fields(html):
    """The hidden fields of the 'more results' button, or None when there is no more."""
    m = NEXT_FORM.search(html)
    if not m:
        return None
    fields = [(k, unescape(v)) for k, v in HIDDEN.findall(m.group(1))]
    return fields if any(k == "cursor" for k, _ in fields) else None


def read_set(console):
    """All rows of one set page, following 'more results' until it stops giving new cards."""
    url = "%s/console/%s" % (BASE, console)
    html = fetch(url)
    title = re.search(r"<title>(.*?)</title>", html, re.S)
    rows, seen = [], set()
    for _ in range(MAX_PAGES):
        fresh = [r for r in parse_rows(html) if r["id"] not in seen]
        for r in fresh:
            seen.add(r["id"])
        rows.extend(fresh)
        fields = next_page_fields(html)
        if not fresh or not fields:
            break
        html = fetch(url, data=urllib.parse.urlencode(fields).encode("ascii"))
    return rows, (unescape(re.sub(r"\s+", " ", title.group(1))).strip() if title else "")


def set_name(page_title, console):
    """'Pokemon Chinese CSV8C Card Prices | Holo...' -> 'CSV8C'."""
    m = re.match(r"\s*Pokemon Chinese\s+(.+?)\s+Card Prices", page_title or "", re.I)
    if m:
        return m.group(1).strip()
    return re.sub(r"^pokemon-chinese-", "", console).replace("-", " ").upper()


MONTHS = {m: i + 1 for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August", "September",
                                          "October", "November", "December"])}


def release_day(row):
    """The set's release date, read from one of its card pages ('Release Date: March 13, 2026'), as 2026-03-13 or ''."""
    try:
        html = fetch("%s/game/%s/%s" % (BASE, row["console"], row["slug"]))
    except RuntimeError:
        return ""
    m = re.search(r"Release Date:\s*([A-Z][a-z]+)\s+(\d{1,2}),\s*(\d{4})", text_of(html))
    if not m or m.group(1) not in MONTHS:
        return ""
    return "%04d-%02d-%02d" % (int(m.group(3)), MONTHS[m.group(1)], int(m.group(2)))


def chinese_sets():
    html = fetch(BASE + "/category/pokemon-cards")
    return sorted(set(re.findall(r"/console/(pokemon-chinese-[a-z0-9\-.]+)", html)))


def read_old(path):
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        i = text.index("=")
        body = text[i + 1:].strip().rstrip(";")
        return json.loads(body)
    except (OSError, ValueError):
        return None


GROUP_ID_START = 5000000   # Chinese sets get ids from here up, far from TCGplayer's, and keep the same id from one update to the next
GROUP_ID_SPAN = 4000000


def new_group_id(console, used):
    """A set's id comes from its page name, so it is the same even if the saved list is ever lost (goals and saved cards point at it)."""
    gid = GROUP_ID_START + zlib.crc32(console.encode("utf-8")) % GROUP_ID_SPAN
    while gid in used:
        gid += 1
    return gid


def group_ids(old):
    """{set page name: id} of the sets in the last list, so a set keeps its id (goals and saved cards point at it)."""
    ids = {}
    for g in (old or {}).get("groups", []):
        if len(g) > 3 and isinstance(g[3], int):
            ids[g[0]] = g[3]
    return ids


def build(old=None):
    """The new data, or raises. old is the last list, whose set ids are kept."""
    ids = group_ids(old)
    groups, cards = [], []
    for console in chinese_sets():
        rows, title = read_set(console)
        if not rows:
            log("  %s: no cards found, skipped" % console)
            continue
        day = release_day(next((r for r in rows if r["number"]), rows[0]))
        gi = len(groups)
        if console not in ids:
            ids[console] = new_group_id(console, set(ids.values()))
        groups.append([console, set_name(title, console), day, ids[console]])
        for r in rows:
            cards.append([r["id"], gi, r["name"], r["number"], r["image"], r["slug"], 0 if r["number"] else 1])
        log("  %s: %d cards (%s)" % (console, len(rows), day or "no date"))
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return {"format": DATA_FORMAT, "source": "PriceCharting public set pages (names, numbers, pictures; no prices)",
            "generated": now, "builtAt": now, "groups": groups, "cards": cards}


def write(data, path):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("window.ZH_DATA = ")
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    os.replace(tmp, path)


def main(argv):
    force = "--force" in argv
    old = read_old(OUT_FILE)
    if old and not force:
        try:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(old["builtAt"])).days
        except (KeyError, ValueError):
            age = 999
        if age < MAX_AGE_DAYS and old.get("cards"):
            log("The Chinese card list is %d day(s) old (%d cards): nothing to do." % (age, len(old["cards"])))
            return 0
    log("Reading PriceCharting's Chinese set pages...")
    try:
        data = build(old)
    except RuntimeError as e:
        log("FAILED: %s" % e)
        log("Keeping the last Chinese card list." if old else "No Chinese card list this time.")
        return 1
    n = len(data["cards"])
    if not n:
        log("PriceCharting gave no Chinese cards: keeping the last list.")
        return 1
    if old and old.get("cards") and n < len(old["cards"]) * KEEP_AT_LEAST:
        log("The new list has %d cards against %d before: not trusted, keeping the last list." % (n, len(old["cards"])))
        return 1
    write(data, OUT_FILE)
    log("Saved %d cards in %d sets to %s." % (n, len(data["groups"]), OUT_FILE))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
