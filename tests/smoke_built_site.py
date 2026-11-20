"""Opens the finished website (the folder the daily update puts together, with today's real card list) in a browser and
makes sure it still works. Only things that mean "this must not go live" fail it; anything else is printed as a warning.

    python tests/smoke_built_site.py _site

Exit code 0: fine (or skipped because no browser is installed). 1: broken, don't publish it.
"""
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def warn(msg):
    print("::warning::" + msg)


def main(site):
    try:
        import harness
    except ImportError as e:  # no Playwright here: nothing to check with, and that must not stop the daily update
        print("SKIPPED: the browser tools aren't installed (%s)." % e)
        return 0
    problems = []
    has_data = os.path.exists(os.path.join(site, "tcgplayer-data.js"))
    if not os.path.exists(os.path.join(site, "index.html")):
        print("FAIL: the website folder has no index.html")
        return 1
    # the small files the website reads must be valid
    if os.path.exists(os.path.join(site, "fee-watch.json")):
        try:
            json.load(open(os.path.join(site, "fee-watch.json"), encoding="utf-8"))
        except ValueError as e:
            problems.append("fee-watch.json isn't valid: %s" % e)
    with harness.serve(site) as url:
        try:
            browser = harness.Browser(url)
        except Exception as e:  # noqa: BLE001
            print("SKIPPED: couldn't start a browser (%s)." % e)
            return 0
        try:
            for kind in ("desktop", "phone"):
                with browser.page(kind, fake_reader=True) as page:
                    if harness_problems(page, kind, problems):
                        continue
                    info = page.evaluate("""() => {
                      const cat = CardVault.state().catalog;
                      if (!cat) return null;
                      const withPrice = cat.products.filter(p => p.number && !p.sealed && Object.values(p.prices).some(s => s.market != null)).slice(0, 4000);
                      const p = withPrice[Math.floor(withPrice.length / 2)];
                      return {n: cat.products.length, generated: cat.generated && cat.generated.toISOString(), id: p && p.id, number: p && p.number, name: p && p.name};
                    }""")
                    if has_data and not info:
                        problems.append("[%s] the card list file is there but the website didn't load it" % kind)
                        continue
                    if not has_data:
                        warn("[%s] no card list in this build (the website will say so)" % kind)
                        continue
                    if info["n"] < 5000:
                        problems.append("[%s] the card list has only %s products" % (kind, info["n"]))
                        continue
                    if kind == "desktop" and info["generated"]:
                        age = (datetime.now(timezone.utc) - datetime.fromisoformat(info["generated"].replace("Z", "+00:00"))).days
                        if age > 4:
                            warn("the card prices are %s days old (TCGCSV may be behind)" % age)
                    if kind == "desktop":
                        check_zh(page, os.path.exists(os.path.join(site, "zh-cards.js")))
                    # a real card: found by its number, read from a scan, added, valued
                    out = page.evaluate("""(info) => {
                      const CV = CardVault, res = {};
                      res.byNumber = CV.findByNumber(info.number).some(p => p.id === info.id);
                      const m = CV.matchScanned(info.number);
                      res.scan = !!(m && m.sure && m.products.some(p => p.id === info.id));
                      res.byName = CV.searchByName(info.name, 50).items.some(p => p.id === info.id);
                      const p = CV.state().catalog.byId.get(info.id);
                      const ed = Object.keys(p.prices)[0];
                      CV.state().collection.push({id: 'smoke1', productId: p.id, name: p.name, productName: p.name, setName: p.group.name, number: p.number,
                        rarity: p.rarity, edition: ed, condition: 'Near Mint', language: 'English', qty: 2, added: new Date().toISOString()});
                      CV.save(); CV.render();
                      res.value = CV.totals(CV.state().collection).value;
                      res.expected = 2 * (p.prices[ed].market != null ? p.prices[ed].market : p.prices[ed].low);
                      res.shown = document.getElementById('totalValue').textContent;
                      for (const t of ['search', 'insights', 'sets', 'wants', 'decks', 'trades', 'market', 'collection']) CV.setTab(t);
                      return res;
                    }""", info)
                    for key, label in (("byNumber", "finding a card by number"), ("scan", "reading a scanned number"), ("byName", "finding a card by name")):
                        if not out[key]:
                            problems.append("[%s] %s doesn't work (%s %s)" % (kind, label, info["name"], info["number"]))
                    # (condition adjustment leaves Near Mint as is)
                    if abs(out["value"] - out["expected"]) > 0.011 or "$" not in out["shown"]:
                        problems.append("[%s] the total is wrong: %s shown, %.2f counted, %.2f expected" % (kind, out["shown"], out["value"], out["expected"]))
                    harness_problems(page, kind, problems)
        finally:
            browser.close()
    for p in problems:
        print("FAIL: " + p)
    if not problems:
        print("The built website opens and works (%s)." % ("real card list" if has_data else "no card list"))
    return 1 if problems else 0


def check_zh(page, has_file):
    """The Chinese card list is a bonus: when it is missing or odd the website just has no Chinese cards, so this only warns."""
    if not has_file:
        warn("no Chinese card list in this build (the website works without Chinese cards)")
        return
    z = page.evaluate("""() => {
      const zh = CardVault.state().catalog.products.filter(p => p.zh), c = zh.find(p => !p.sealed && !p.noImg);
      return {n: zh.length, sets: CardVault.state().catalog.groups.filter(g => g.zh).length, pic: c ? CardVault.productPics(c, 'in_400x400').list[0] : '',
              priced: zh.some(p => Object.keys(p.prices).length)};
    }""")
    if not z["n"]:
        warn("zh-cards.js is in the build but the website found no Chinese cards in it")
    elif not str(z["pic"]).startswith("https://storage.googleapis.com/images.pricecharting.com/"):
        warn("Chinese cards have no picture address: %r" % z["pic"])
    elif z["priced"]:
        warn("Chinese cards carry prices in the build: PriceCharting's prices must not be published")
    else:
        print("Chinese card list: %d cards in %d sets." % (z["n"], z["sets"]))


def harness_problems(page, kind, problems):
    if page.problems:
        problems.append("[%s] the page reported problems: %s" % (kind, "; ".join(page.problems[:3])))
        return True
    return False


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "_site"))
