"""One-off: what can be read, from GitHub's network, about places that might carry Chinese Pokemon card lists, pictures and prices."""
import json, re, sys, urllib.request, urllib.error

UA = "Mozilla/5.0 (compatible; PokemonVaultResearch/1.0; +https://github.com/Swithers21/pokemon-vault)"

def get(url, limit=400000, headers=None):
    req = urllib.request.Request(url, headers=dict({"User-Agent": UA, "Accept-Language": "en"}, **(headers or {})))
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            body = r.read(limit).decode("utf-8", "replace")
            return r.status, body
    except urllib.error.HTTPError as e:
        return e.code, (e.read(2000).decode("utf-8", "replace") if e.fp else "")
    except Exception as e:
        return 0, "ERR %s" % e

def show(title, obj):
    print("\n=== %s ===" % title)
    print(obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, indent=1)[:6000])

# 1. TCGCSV categories
st, body = get("https://tcgcsv.com/tcgplayer/categories")
try:
    cats = json.loads(body)["results"]
    show("TCGCSV categories (%s)" % st, [(c["categoryId"], c["name"]) for c in cats])
except Exception as e:
    show("TCGCSV categories failed %s" % st, body[:300])

# 2. PriceCharting
st, robots = get("https://www.pricecharting.com/robots.txt")
show("pricecharting robots.txt %s" % st, robots[:2500])
st, cat = get("https://www.pricecharting.com/category/pokemon-cards")
links = sorted(set(re.findall(r'/console/(pokemon-[a-z0-9\-]+)', cat)))
chin = [l for l in links if "chinese" in l]
show("pricecharting pokemon consoles: status %s, total %d, chinese %d" % (st, len(links), len(chin)), chin[:200])
others = [l for l in links if any(k in l for k in ("taiwan", "traditional", "hong", "simplified", "cn", "tw"))]
show("pricecharting other asian-looking", others[:50])
st, page = get("https://www.pricecharting.com/console/pokemon-chinese-csv8c")
show("pricecharting csv8c page status %s len %d" % (st, len(page)), re.sub(r"\s+", " ", page[page.find("<table"):page.find("<table") + 3500]) if "<table" in page else page[:1500])
imgs = re.findall(r'https?://[^"\']+(?:images\.pricecharting|storage\.googleapis)[^"\']+', page)
show("pricecharting image urls sample", imgs[:6])
for u in ("https://www.pricecharting.com/api-documentation", "https://www.pricecharting.com/page/terms-of-service", "https://www.pricecharting.com/page/terms", "https://www.pricecharting.com/page/api-documentation"):
    st, doc = get(u)
    text = re.sub(r"<[^>]+>", " ", doc)
    text = re.sub(r"\s+", " ", text)
    hits = [text[max(0, m.start() - 160):m.end() + 200] for m in re.finditer(r"scrap|crawl|automated|robot|spider|bulk|image|subscription|\$\d", text, re.I)]
    show("%s status %s len %d" % (u, st, len(text)), hits[:14])

# 3. Pokemon Asia (official Traditional Chinese)
for u in ("https://asia.pokemon-card.com/robots.txt", "https://asia.pokemon-card.com/tw/card-search/", "https://asia.pokemon-card.com/hk/card-search/"):
    st, body = get(u, limit=200000)
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))
    show("%s status %s len %d" % (u, st, len(body)), text[:1200])
    if "card-search" in u:
        show("card/image links in " + u, sorted(set(re.findall(r'(?:/tw|/hk)/card-search/detail/\d+/?|https?://[^"\']+\.(?:png|jpg)', body)))[:12])

# 4. CardTrader / TCG Collector (public pages)
for u in ("https://www.cardtrader.com/en/games/pokemon/expansions", "https://www.tcgcollector.com/robots.txt", "https://www.tcgcollector.com/sets/intl"):
    st, body = get(u)
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))
    hits = [text[max(0, m.start() - 80):m.end() + 120] for m in re.finditer(r"Chinese|Disallow|scrap|crawl", text)]
    show("%s status %s len %d" % (u, st, len(body)), hits[:10] or text[:500])
