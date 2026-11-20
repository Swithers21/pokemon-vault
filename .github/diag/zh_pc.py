"""One-off: read PriceCharting's terms in full, and how its Chinese set pages and API are laid out."""
import json, re, time, urllib.request, urllib.error

UA = "Mozilla/5.0 (compatible; PokemonVaultResearch/1.0; +https://github.com/Swithers21/pokemon-vault)"

def get(url, limit=4000000, headers=None, method="GET"):
    req = urllib.request.Request(url, headers=dict({"User-Agent": UA, "Accept-Language": "en"}, **(headers or {})), method=method)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, dict(r.headers), (r.read(limit).decode("utf-8", "replace") if method == "GET" else "")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), (e.read(3000).decode("utf-8", "replace") if e.fp and method == "GET" else "")
    except Exception as e:
        return 0, {}, "ERR %s" % e

def text_of(html):
    html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()

def show(title, body):
    print("\n=== %s ===" % title)
    print(body)

# 1. Terms of service, whole
st, h, html = get("https://www.pricecharting.com/page/terms-of-service")
t = text_of(html)
i = t.find("Terms of Service")
show("TERMS (status %s, %d chars)" % (st, len(t)), t[i:i + 14000] if i >= 0 else t[:14000])

# 2. API docs: the part about products, fields, search
st, h, html = get("https://www.pricecharting.com/api-documentation")
t = text_of(html)
i = t.find("Prices API")
show("API DOCS (status %s)" % st, t[i:i + 9000])

# 3. a console page: structure
time.sleep(1.5)
st, h, page = get("https://www.pricecharting.com/console/pokemon-chinese-csv8c")
rows = re.findall(r'<tr id="product-\d+".*?</tr>', page, re.S)
show("csv8c page status %s len %d rows %d" % (st, len(page), len(rows)), "")
for r in (rows[:2] + rows[-1:]):
    print(re.sub(r"\s+", " ", r)[:1800]); print("--")
print("title:", re.findall(r"<title>(.*?)</title>", page, re.S)[:1])
print("cursor/pagination hints:", sorted(set(re.findall(r'(?:cursor|offset|page)=[^"&\s]{1,30}', page)))[:10], "| load more:", bool(re.search(r"load more|js-more|more-results", page, re.I)))
print("canonical/robots meta:", re.findall(r'<meta name="robots"[^>]*>', page))

# 4. every Chinese console: card counts
st, h, cat = get("https://www.pricecharting.com/category/pokemon-cards")
chin = sorted(set(re.findall(r'/console/(pokemon-chinese-[a-z0-9\-]+)', cat)))
total = 0
lines = []
for c in chin:
    time.sleep(1.2)
    st, h, p = get("https://www.pricecharting.com/console/" + c)
    n = len(re.findall(r'<tr id="product-\d+"', p))
    title = re.findall(r"<title>(.*?)</title>", p, re.S)
    lines.append("%s status %s rows %d  title=%s" % (c, st, n, re.sub(r"\s+", " ", title[0])[:70] if title else ""))
    total += n
show("all Chinese consoles (%d), total rows %d" % (len(chin), total), "\n".join(lines))

# 5. one product page
time.sleep(1.2)
st, h, p = get("https://www.pricecharting.com/game/pokemon-chinese-csv8c/carmine-255")
show("product page status %s len %d" % (st, len(p)), "")
print("title:", re.findall(r"<title>(.*?)</title>", p, re.S)[:1])
print("og:image:", re.findall(r'<meta property="og:image"[^>]*>', p))
print("images:", sorted(set(re.findall(r'https://storage\.googleapis\.com/images\.pricecharting\.com/[^"\'\s]+', p)))[:10])
tx = text_of(p)
j = tx.find("Card Number")
print("details:", tx[max(0, j - 300):j + 700] if j >= 0 else tx[:600])

# 6. image sizes + CORS
imgs = re.findall(r'https://storage\.googleapis\.com/images\.pricecharting\.com/([a-z0-9]+)/60\.jpg', page)
if imgs:
    for size in ("60", "240", "1600"):
        u = "https://storage.googleapis.com/images.pricecharting.com/%s/%s.jpg" % (imgs[0], size)
        st, h, _ = get(u, method="HEAD")
        print("image", size, st, h.get("Content-Type"), h.get("Content-Length"), "ACAO=", h.get("Access-Control-Allow-Origin"))
for u in ("https://www.pricecharting.com/api/products?q=carmine&t=0000", "https://www.pricecharting.com/console/pokemon-chinese-csv8c"):
    st, h, body = get(u, headers={"Origin": "https://swithers21.github.io"}, limit=2000)
    print("CORS", u[:60], st, "ACAO=", h.get("Access-Control-Allow-Origin"), "body:", body[:160].replace("\n", " "))
