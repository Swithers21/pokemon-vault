#!/usr/bin/env python3
"""
Pokemon Vault - TCGplayer data updater
======================================

Downloads TCGplayer's Pokemon catalogs, English and Japanese (every printing,
with its card number and rarity) plus current TCGplayer market prices, and
saves them next to index.html as tcgplayer-data.js. Pokemon Vault
reads that file when it opens.

English cards are TCGplayer's "Pokemon" category and Japanese cards are its
"Pokemon Japan" category. Both come through the same TCGCSV files, so one daily
run prices both languages. (There are no other languages.)

Every run also keeps a small snapshot of that day's prices, so
Pokemon Vault can show how prices changed since the last update, over 7 days and
over 30 days.

The data comes from TCGCSV (https://tcgcsv.com), a free mirror of TCGplayer's
official API that refreshes once a day. This script follows TCGCSV's usage
guidelines (https://tcgcsv.com/docs):
  * it checks last-updated.txt first and stops right away if nothing changed,
  * it identifies itself with its own User-Agent,
  * it pauses between requests and stays far below 10,000 requests a day,
  * it keeps each set's card list on your computer and only downloads it
    again when TCGplayer changes that set.

How to run it
  python update_tcgplayer_data.py
  Options:  --force      rebuild everything, even if TCGCSV hasn't changed
            --scheduled  quiet mode for automatic runs (writes a log
                         to tcgplayer-cache/update-log.txt instead of the screen)

On GitHub, the daily workflow runs this for the website (see SETUP.md).

Only Python's standard library is used, so there is nothing extra to install.
"""

import gzip
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

VERSION = "1.0"
DATA_FORMAT = 5  # tcgplayer-data.js layout; 2 added the older prices for price history, 3 sealed products, 4 marks products with no photo, 5 adds the language of each set and each card's type and stage
PRODUCT_LIST_VERSION = 4  # cached set lists; 2 keeps sealed products (booster boxes, tins, decks...) too, 3 notes missing photos, 4 keeps each card's type and stage
BASE_URL = os.environ.get("POKEVAULT_TCGCSV_BASE", "https://tcgcsv.com").rstrip("/")
# TCGplayer's category IDs: 3 is "Pokemon" (English cards) and 85 is "Pokemon Japan" (Japanese cards). The updater looks
# both up by name in TCGCSV's category list first, and falls back on these if the list can't be read.
CATEGORY_EN = int(os.environ.get("POKEVAULT_CATEGORY_EN", "3"))
CATEGORY_JP = int(os.environ.get("POKEVAULT_CATEGORY_JP", "85"))
USER_AGENT = "PokemonVault/%s (personal Pokemon card collection tracker)" % VERSION
PAUSE_SECONDS = float(os.environ.get("POKEVAULT_PAUSE", "0.15"))
PRODUCT_CACHE_MAX_AGE_DAYS = 30
HISTORY_KEEP_ALL_DAYS = 120     # keep every daily snapshot this recent (the website charts each card's price)...
HISTORY_KEEP_MONTHLY_DAYS = 400  # ...then one per month back this far

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, "tcgplayer-cache")
HISTORY_DIR = os.path.join(CACHE_DIR, "history")
STATE_FILE = os.path.join(CACHE_DIR, "state.json")
LOG_FILE = os.path.join(CACHE_DIR, "update-log.txt")
OUT_FILE = os.path.join(HERE, "tcgplayer-data.js")
# A tiny file an open Pokemon Vault checks now and then, to notice new prices without reloading the big one.
VERSION_FILE = os.path.join(HERE, "tcgplayer-data-version.js")

request_count = 0
SCHEDULED = "--scheduled" in sys.argv


class Throttled(Exception):
    """TCGCSV asked us to slow down (or blocked us for a while)."""


class Missing(Exception):
    """The file doesn't exist on TCGCSV (it answers 403/404 for missing files)."""


def say(msg=""):
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def open_log():
    """In scheduled mode there's no window, so send all output to a log file."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as handle:
            old = handle.readlines()[-400:]  # keep the log small
    except OSError:
        old = []
    log = open(LOG_FILE, "w", encoding="utf-8")
    log.writelines(old)
    log.write("\n=== %s ===\n" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    log.flush()
    sys.stdout = log
    sys.stderr = log


def fetch(path, retries=3):
    """GET a TCGCSV path and return the body as bytes."""
    global request_count
    url = BASE_URL + path
    last_error = None
    for attempt in range(1, retries + 1):
        request = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"}
        )
        request_count += 1
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read()
                if (response.headers.get("Content-Encoding") or "").lower() == "gzip":
                    body = gzip.decompress(body)
                return body
        except urllib.error.HTTPError as error:
            if error.code == 429:
                raise Throttled()
            if error.code in (403, 404):
                # TCGCSV sits behind CloudFront + S3, which answers 403 for a
                # missing file. Treat it as missing; the caller decides whether
                # too many of these in a row means we're being blocked.
                raise Missing(url)
            last_error = "HTTP %s" % error.code
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as error:
            last_error = getattr(error, "reason", None) or error
        time.sleep(2 * attempt)
    raise RuntimeError("Couldn't download %s (%s)" % (url, last_error))


def fetch_json(path):
    return json.loads(fetch(path).decode("utf-8"))


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return default


def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, separators=(",", ":"))
    os.replace(tmp, path)


def iso_timestamp(raw):
    """TCGCSV writes '2026-09-24T20:05:50+0000'; browsers want '+00:00'."""
    raw = (raw or "").strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            return datetime.strptime(raw, fmt).astimezone(timezone.utc).isoformat()
        except ValueError:
            pass
    return raw


def friendly_date(raw):
    try:
        return datetime.fromisoformat(iso_timestamp(raw)).strftime("%b %d, %Y")
    except ValueError:
        return raw or "unknown date"


def progress(done, total, label):
    if SCHEDULED:
        return
    width = 28
    filled = int(width * done / max(total, 1))
    bar = "#" * filled + "-" * (width - filled)
    label = (label or "")[:38]
    sys.stdout.write("\r  [%s] %3d%%  %-38s" % (bar, int(100 * done / max(total, 1)), label))
    sys.stdout.flush()


def compact_products(results):
    """Every product of a set as [id, name, number, rarity, sealed, no photo, card type, stage]:
      - a single card has a card number (TCGplayer's "Number", like "025/198" or "SWSH123");
      - everything else (booster boxes and packs, Elite Trainer Boxes, tins, decks, code cards...) is sealed: 1;
      - "no photo" is 1 for a product TCGplayer has no photo of yet (new sets, promos);
      - card type and stage are TCGplayer's own words ("Fire", "Trainer", "Energy"; "Basic", "Stage 1"...), for the deck check."""
    items = []
    for product in results or []:
        extended = {}
        for item in product.get("extendedData") or []:
            extended[item.get("name")] = (item.get("value") or "").strip()
        number = extended.get("Number", "")
        name = (product.get("name") or "").strip()
        if not name:
            continue
        sealed = 0 if number else 1
        no_photo = 1 if product.get("imageCount") == 0 else 0
        card_type = extended.get("Card Type", "") if number else ""
        stage = extended.get("Stage", "") if number else ""
        items.append([int(product["productId"]), name, number, extended.get("Rarity", "") if number else "", sealed, no_photo,
                      card_type, stage])
    return items


def money(value):
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- price history
def snapshot_path(day):
    return os.path.join(HISTORY_DIR, "%s.json.gz" % day.isoformat())


def saved_snapshot_days():
    days = []
    try:
        names = os.listdir(HISTORY_DIR)
    except OSError:
        return days
    for name in names:
        if name.endswith(".json.gz"):
            try:
                days.append(date.fromisoformat(name[:10]))
            except ValueError:
                pass
    return sorted(days)


def write_snapshot(day, market_by_subtype):
    """market_by_subtype: {"1st Edition": {"714648": 0.41, ...}, ...}"""
    os.makedirs(HISTORY_DIR, exist_ok=True)
    path = snapshot_path(day)
    tmp = path + ".tmp"
    with gzip.open(tmp, "wt", encoding="utf-8") as handle:
        json.dump({"date": day.isoformat(), "prices": market_by_subtype}, handle, separators=(",", ":"))
    os.replace(tmp, path)


def read_snapshot(day):
    try:
        with gzip.open(snapshot_path(day), "rt", encoding="utf-8") as handle:
            return (json.load(handle) or {}).get("prices") or {}
    except (OSError, ValueError, EOFError):
        return {}


def pick_reference_days(today, days):
    """Which saved snapshots to compare today's prices against."""
    past = [d for d in days if d < today]

    def closest(target, earliest, latest):
        window = [d for d in past if earliest <= d <= latest]
        return min(window, key=lambda d: (abs((d - target).days), d)) if window else None

    return {
        "d1": past[-1] if past else None,  # the previous update, however long ago
        "d7": closest(today - timedelta(days=7), today - timedelta(days=10), today - timedelta(days=5)),
        "d30": closest(today - timedelta(days=30), today - timedelta(days=37), today - timedelta(days=24)),
    }


def prune_snapshots(today):
    """Keep every snapshot from the last 40 days, then the first of each month for ~13 months."""
    seen_months = set()
    for day in saved_snapshot_days():
        age = (today - day).days
        keep = age <= HISTORY_KEEP_ALL_DAYS
        if not keep and age <= HISTORY_KEEP_MONTHLY_DAYS:
            month = (day.year, day.month)
            keep = month not in seen_months
            seen_months.add(month)
        if not keep:
            try:
                os.remove(snapshot_path(day))
            except OSError:
                pass

def find_categories():
    """TCGplayer's category IDs for English and Japanese Pokemon, by name (with the usual IDs as the fallback)."""
    english, japanese = CATEGORY_EN, CATEGORY_JP
    try:
        for category in fetch_json("/tcgplayer/categories").get("results") or []:
            name = re.sub(r"[^a-z ]", "", str(category.get("name") or "").lower().replace("\u00e9", "e")).strip()
            if name == "pokemon":
                english = int(category["categoryId"])
            elif name.startswith("pokemon") and "japan" in name:
                japanese = int(category["categoryId"])
    except (Missing, RuntimeError, ValueError, KeyError, TypeError):
        pass
    return english, japanese


def main():
    force = "--force" in sys.argv
    started = time.time()
    os.makedirs(CACHE_DIR, exist_ok=True)
    state = load_json(STATE_FILE, {})
    product_state = state.get("products", {})

    say("")
    say("  Pokemon Vault - TCGplayer data updater")
    say("  --------------------------------------")
    say("  Checking TCGCSV for new TCGplayer data...")

    try:
        last_updated = fetch("/last-updated.txt").decode("utf-8").strip()
    except Missing:
        last_updated = ""

    # (A data file from an older version of this updater is rebuilt, so it gets the price history.)
    if (not force and last_updated and last_updated == state.get("lastUpdated")
            and state.get("format") == DATA_FORMAT and os.path.exists(OUT_FILE)):
        say("  Already up to date. Your prices are from %s." % friendly_date(last_updated))
        say("  TCGCSV refreshes once a day, so try again tomorrow for newer prices.")
        return 0

    say("  Downloading the lists of Pokemon sets (English and Japanese)...")
    category_en, category_jp = find_categories()
    groups = []   # (language, category, group): language 0 is English, 1 is Japanese
    for language, category in ((0, category_en), (1, category_jp)):
        try:
            found = fetch_json("/tcgplayer/%d/groups" % category).get("results") or []
        except Missing:
            if language == 0:
                raise RuntimeError("TCGCSV refused the request. Wait 10 minutes and try again; "
                                   "if it keeps happening, TCGCSV may be down for maintenance")
            found = []   # (the Japanese list missing shouldn't spoil the English prices)
            say("  (TCGCSV has no Japanese Pokemon sets right now; keeping the English ones.)")
        groups.extend((language, category, g) for g in found)
        time.sleep(PAUSE_SECONDS)
    if not any(lang == 0 for lang, _c, _g in groups):
        raise RuntimeError("TCGCSV returned no Pokemon sets. Try again later.")
    say("  Found %d sets (%d English, %d Japanese). Downloading card lists and prices (this takes a few minutes"
        " the first time, then only prices are downloaded)..." % (len(groups), sum(1 for x in groups if x[0] == 0), sum(1 for x in groups if x[0] == 1)))

    now_iso = datetime.now(timezone.utc).isoformat()
    now_ts = time.time()
    set_rows = []       # [groupId, name, abbreviation, publishedOn(, 1 for a Japanese set)]
    card_rows = []      # [productId, groupIndex, name, number, rarityIndex, prices, sealed, no photo, card type, stage]
    sealed_ids = set()
    no_photo_ids = set()  # products TCGplayer has no photo of (the website shows a stand-in)
    rarity_index = {}
    rarities = []
    skipped_sets = 0
    missing_in_a_row = 0
    today_prices = {}   # {productId: [(subtype, market, low), ...]}

    card_types, stages = [], []
    card_kinds = {}      # {productId: (card type index, stage index)}
    card_type_index, stage_index = {}, {}
    for position, (language, category, group) in enumerate(groups, start=1):
        group_id = int(group["groupId"])
        progress(position - 1, len(groups), group.get("name", ""))

        # 1) The set's card list, reused from the cache unless the set changed.
        cache_path = os.path.join(CACHE_DIR, "products-%d.json" % group_id)
        cached = product_state.get(str(group_id)) or {}
        fresh_enough = (
            not force
            and cached.get("modifiedOn") == group.get("modifiedOn")
            and cached.get("v") == PRODUCT_LIST_VERSION
            and now_ts - cached.get("fetchedAt", 0) < PRODUCT_CACHE_MAX_AGE_DAYS * 86400
            and os.path.exists(cache_path)
        )
        cards = load_json(cache_path, None) if fresh_enough else None
        if cards is None:
            try:
                cards = compact_products(
                    fetch_json("/tcgplayer/%d/%d/products" % (category, group_id)).get("results"))
                missing_in_a_row = 0
            except Missing:
                cards = None
                missing_in_a_row += 1
                skipped_sets += 1
            time.sleep(PAUSE_SECONDS)
            if missing_in_a_row >= 5:
                raise Throttled()
            if cards is None:
                continue
            save_json(cache_path, cards)
            product_state[str(group_id)] = {"modifiedOn": group.get("modifiedOn"), "fetchedAt": now_ts, "v": PRODUCT_LIST_VERSION}
            if position % 50 == 0:  # so an interrupted run doesn't re-download finished sets
                state["products"] = product_state
                save_json(STATE_FILE, state)

        if not cards:
            continue  # nothing in this set to price

        # 2) Today's prices for the set (always downloaded; they change daily).
        try:
            price_results = fetch_json("/tcgplayer/%d/%d/prices" % (category, group_id)).get("results") or []
            missing_in_a_row = 0
        except Missing:
            price_results = []
            missing_in_a_row += 1
            if missing_in_a_row >= 5:
                raise Throttled()
        time.sleep(PAUSE_SECONDS)
        for row in price_results:
            subtype = (row.get("subTypeName") or "").strip() or "Normal"
            # Market price is what cards actually sell for. highPrice is ignored on
            # purpose: sellers "price park" listings at absurd amounts.
            today_prices.setdefault(int(row["productId"]), []).append(
                (subtype, money(row.get("marketPrice")), money(row.get("lowPrice"))))

        group_index = len(set_rows)
        set_rows.append([group_id, (group.get("name") or "").strip(),
                         (group.get("abbreviation") or "").strip(),
                         (group.get("publishedOn") or "")[:10]] + ([1] if language else []))
        for item in cards:
            product_id, name, number, rarity = item[:4]
            sealed, no_photo = (item + [0] * 8)[4:6]
            card_type, stage = (item + ["", ""])[6:8] if len(item) >= 8 else ("", "")
            if sealed:
                sealed_ids.add(product_id)
            if no_photo:
                no_photo_ids.add(product_id)
            if rarity not in rarity_index:
                rarity_index[rarity] = len(rarities)
                rarities.append(rarity)
            ct = st = -1
            if card_type:
                ct = card_type_index.setdefault(card_type, len(card_types))
                if ct == len(card_types):
                    card_types.append(card_type)
            if stage:
                st = stage_index.setdefault(stage, len(stages))
                if st == len(stages):
                    stages.append(stage)
            card_rows.append([product_id, group_index, name, number, rarity_index[rarity]])
            card_kinds[product_id] = (ct, st)

    progress(len(groups), len(groups), "done")
    if not SCHEDULED:
        say("")

    if not card_rows:
        raise RuntimeError("No cards were downloaded, so your existing data was left unchanged.")

    # 3) Price history: save today's snapshot, then look up the comparison days.
    generated = iso_timestamp(last_updated) or now_iso
    try:
        price_day = datetime.fromisoformat(generated).date()
    except ValueError:
        price_day = datetime.now(timezone.utc).date()
    snapshot = {}
    card_ids = {row[0] for row in card_rows}
    for product_id, entries in today_prices.items():
        if product_id not in card_ids:
            continue  # (not in the catalog)
        for subtype, market, _low in entries:
            if market is not None:
                snapshot.setdefault(subtype, {})[str(product_id)] = market
    write_snapshot(price_day, snapshot)
    prune_snapshots(price_day)
    reference_days = pick_reference_days(price_day, saved_snapshot_days())
    references = {key: read_snapshot(day) if day else {} for key, day in reference_days.items()}

    subtypes = []
    subtype_index = {}
    for row in card_rows:
        product_id = row[0]
        prices = []
        for subtype, market, low in today_prices.get(product_id, []):
            if subtype not in subtype_index:
                subtype_index[subtype] = len(subtypes)
                subtypes.append(subtype)
            key = str(product_id)
            prices.extend([subtype_index[subtype], market, low,
                           references["d1"].get(subtype, {}).get(key),
                           references["d7"].get(subtype, {}).get(key),
                           references["d30"].get(subtype, {}).get(key)])
        ct, st = card_kinds.get(product_id, (-1, -1))
        row.append(prices)
        # after the prices: 1 for a sealed product, 1 for a product with no photo, then the card type and stage
        # (indexes into "cardTypes" and "stages", -1 for none); trailing blanks are left off to keep the file small
        extra = [1 if product_id in sealed_ids else 0, 1 if product_id in no_photo_ids else 0, ct, st]
        defaults = [0, 0, -1, -1]
        while extra and extra[-1] == defaults[len(extra) - 1]:
            extra.pop()
        row.extend(extra)

    data = {
        "format": DATA_FORMAT,
        "source": "TCGCSV (TCGplayer)",
        "generated": generated,
        "builtAt": now_iso,
        "history": {key: day.isoformat() if day else None for key, day in reference_days.items()},
        "groups": set_rows,
        "rarities": rarities,
        "subtypes": subtypes,
        "cardTypes": card_types,
        "stages": stages,
        # each price entry: subtype, market, low, market at d1, at d7, at d30; after the prices, 1 marks a sealed
        # product, a second 1 a product TCGplayer has no photo of, then the card type and stage
        "products": card_rows,
    }
    tmp_path = OUT_FILE + ".tmp"
    with open(tmp_path, "w", encoding="ascii") as handle:
        handle.write("/* Pokemon Vault: TCGplayer Pokemon data (English and Japanese) from TCGCSV. Rebuilt by update_tcgplayer_data.py */\n")
        handle.write("window.TCG_DATA = ")
        json.dump(data, handle, ensure_ascii=True, separators=(",", ":"))
        handle.write(";\n")
    os.replace(tmp_path, OUT_FILE)
    with open(VERSION_FILE + ".tmp", "w", encoding="ascii") as handle:
        handle.write("window.TCG_DATA_VERSION = ")
        json.dump({"generated": generated, "builtAt": now_iso}, handle, ensure_ascii=True, separators=(",", ":"))
        handle.write(";\n")
    os.replace(VERSION_FILE + ".tmp", VERSION_FILE)

    state["lastUpdated"] = last_updated
    state["format"] = DATA_FORMAT
    state["lastRun"] = now_iso
    state["products"] = product_state
    save_json(STATE_FILE, state)

    size_mb = os.path.getsize(OUT_FILE) / (1024 * 1024)
    say("  Done! Saved %s card printings and %s sealed products from %d sets (%.1f MB)."
        % (format(len(card_rows) - len(sealed_ids), ","), format(len(sealed_ids), ","), len(set_rows), size_mb))
    say("  Prices are TCGplayer market prices from %s." % friendly_date(last_updated or now_iso))
    compared = [label for key, label in (("d1", "your last update"), ("d7", "7 days ago"), ("d30", "30 days ago"))
                if reference_days[key]]
    if compared:
        say("  Price changes are compared with %s." % ", ".join(compared))
    else:
        say("  Price changes will show up after the updater has run on another day.")
    if skipped_sets:
        say("  (%d %s no card list on TCGCSV and %s skipped.)"
            % (skipped_sets, "set had" if skipped_sets == 1 else "sets had",
               "was" if skipped_sets == 1 else "were"))
    say("  %d requests in %.0f seconds." % (request_count, time.time() - started))
    say("")
    say("  Now open index.html, or press F5 if it's already open.")
    return 0


if __name__ == "__main__":
    if SCHEDULED:
        open_log()
    try:
        sys.exit(main())
    except Throttled:
        say("")
        say("  TCGCSV asked this computer to slow down. Nothing was changed.")
        say("  Wait about 10 minutes, then run the updater again.")
        sys.exit(1)
    except KeyboardInterrupt:
        say("")
        say("  Stopped. Your existing data was left unchanged.")
        sys.exit(1)
    except Exception as error:  # show a readable message instead of a traceback
        say("")
        say("  Something went wrong: %s" % error)
        say("  Check your internet connection and try again. Your existing data was left unchanged.")
        sys.exit(1)
