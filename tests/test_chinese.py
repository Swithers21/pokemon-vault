"""Checks of Chinese (Simplified) card support: the card list and pictures from zh-cards.js, finding a card by its number,
prices from PriceCharting with the person's own key (a pretend PriceCharting answers here, nothing leaves the computer),
goals, sets, and that nothing of PriceCharting's prices is shared or kept without a key."""
import json

from harness import test, check, no_problems
from test_core import record

ZH_BASE = 10 ** 9
ZH = "Chinese (Simplified)"
CARMINE, MILOTIC, JOLTIK, PIKACHU_A, PIKACHU_B, PIKACHU_RH, BOX = (ZH_BASE + n for n in (12353505, 12353504, 13643801, 14000001, 14000002, 14000003, 14000010))


def item(pc_id, name, loose, grade10=None, vol=30):
    """What PriceCharting's product call answers (prices are in cents)."""
    out = {"id": pc_id, "product-name": name, "console-name": "Pokemon Chinese CSV8C", "loose-price": loose, "sales-volume": vol}
    if grade10:
        out["manual-only-price"] = grade10
    return out


def zh_record(pid, name, number, qty=1, **extra):
    return record(productId=pid, name=name, number=number, edition="Normal", qty=qty, language=ZH, **extra)


def seed_one(**settings):
    return {"collection": [zh_record(CARMINE, "Carmine", "255", 2, setName="CSV8C")], "settings": dict(settings)}


def total_text(page):
    return page.inner_text("#totalValue").strip()


# ---------------------------------------------------------------- the card list and its pictures
@test("Chinese cards are in the card list, in their own sets, with their own language", phone=True, smoke=True)
def zh_catalog(browser, kind):
    with browser.page(kind) as page:
        info = page.evaluate("""() => {
          const c = CardVault.state().catalog, zh = c.products.filter(p => p.zh), en = c.products.filter(p => !p.zh);
          const carmine = zh.find(p => p.name === 'Carmine');
          return {zh: zh.length, en: en.length, sets: c.groups.filter(g => g.zh).map(g => g.name + '|' + g.id + '|' + g.jp),
                  lang: CardVault.productLanguage(carmine), id: carmine.id, number: carmine.number, sealed: zh.filter(p => p.sealed).map(p => p.name),
                  prices: zh.some(p => Object.keys(p.prices).length), mk: c.groups.filter(g => g.zh).some(g => CardVault.mkLangOK(g)),
                  enLang: CardVault.productLanguage(en[0])}; }""")
        check(info["zh"] == 7, "Chinese products: %s" % info["zh"])
        check(info["en"] >= 30, "English and Japanese products are still all there: %s" % info["en"])
        check(sorted(info["sets"]) == ["CSV8C|5000001|false", "Gem Pack|5000002|false"], "sets: %s" % info["sets"])
        check(info["lang"] == ZH and info["id"] == CARMINE, "language %r, id %s" % (info["lang"], info["id"]))
        check(info["sealed"] == ["Gem Pack Booster Box"], "sealed products: %s" % info["sealed"])
        check(not info["prices"], "the card list carries no prices, those come from your own key")
        check(not info["mk"], "the Market tab compares TCGplayer prices: it has no Chinese sets")
        check(info["enLang"] in ("English", "Japanese"), "an English card's language is %r" % info["enLang"])
        no_problems(page)


@test("each Chinese card has its own picture: small in lists, large when opened; none is made up", phone=True)
def zh_pictures(browser, kind):
    with browser.page(kind) as page:
        pics = page.evaluate("""() => {
          const c = CardVault.state().catalog, by = (n, num) => c.products.find(p => p.zh && p.name === n && p.number === num);
          const out = {};
          for (const [k, n, num] of [['carmine', 'Carmine', '255'], ['rh', 'Pikachu (Reverse Holo)', '26'], ['box', 'Gem Pack Booster Box', '']]) {
            const p = by(n, num);
            out[k] = {small: CardVault.productPics(p, 'in_400x400').list, big: CardVault.productPics(p, 'in_1000x1000').list, noImg: !!p.noImg,
                      rec: CardVault.recordPics({productId: p.id, name: p.name, number: p.number}, 'in_400x400').list};
          }
          return out; }""")
        base = "https://storage.googleapis.com/images.pricecharting.com/inbukwejsstzqsxh/"
        check(pics["carmine"]["small"][0] == base + "240.jpg", "small picture: %s" % pics["carmine"]["small"][:1])
        check(pics["carmine"]["big"][0] == base + "1600.jpg", "large picture: %s" % pics["carmine"]["big"][:1])
        check(base + "240.jpg" in pics["carmine"]["rec"], "a card in the collection shows the same picture: %s" % pics["carmine"]["rec"])
        check(not any("tcgplayer" in u for u in pics["carmine"]["small"][:1]), "a Chinese card never points at TCGplayer's photo for it")
        # a card PriceCharting has no picture for: no picture of its own, and anything else shown is marked as a stand-in (starts with ~)
        check(pics["rh"]["noImg"], "no picture, so noImg")
        check(all(str(u).startswith("~") or not u for u in pics["rh"]["small"]), "pictures for a card with none: %s" % pics["rh"]["small"])
        check(not [u for u in pics["box"]["small"] if u and not str(u).startswith("~")], "a sealed product with no picture: %s" % pics["box"]["small"])
        no_problems(page)


# ---------------------------------------------------------------- finding a card by its number
@test("a Chinese card is found by its number, English results stay as they were", phone=True)
def zh_numbers(browser, kind):
    with browser.page(kind) as page:
        r = page.evaluate("""() => {
          const f = CardVault.findByNumber, names = l => l.map(p => (p.zh ? 'zh:' : '') + p.name + ' ' + p.number + ' ' + p.group.name);
          return {en: names(f('025/165')), plain25: names(f('25')), zh255: names(f('255')), slash: names(f('255/204')), zhOnly: names(f('25', 'zh')),
                  noZh: names(f('25', 'noZh')), noZhSlash: names(f('255/204', 'noZh')), noZhPlain: names(f('255', 'noZh')), none: names(f('999')),
                  letter: names(f('9'))}; }""")
        check(r["en"] and not any(x.startswith("zh:") for x in r["en"]), "a full English number still finds only the English printings: %s" % r["en"])
        zh25 = [x for x in r["plain25"] if x.startswith("zh:")]
        check(len(zh25) == 2 and any("CSV8C" in x for x in zh25) and any("Gem Pack" in x for x in zh25), "25 finds both Chinese Pikachu: %s" % r["plain25"])
        check(len(r["plain25"]) > len(zh25), "and the English ones too: %s" % r["plain25"])
        check(r["zh255"] == ["zh:Carmine 255 CSV8C"], "255: %s" % r["zh255"])
        check(r["slash"] == ["zh:Carmine 255 CSV8C"], "255/204 falls back on the Chinese card: %s" % r["slash"])
        check(sorted(r["zhOnly"]) == sorted(zh25), "Chinese only: %s" % r["zhOnly"])
        check(r["noZh"] and not any(x.startswith("zh:") for x in r["noZh"]), "camera mode leaves Chinese out: %s" % r["noZh"])
        check(r["noZhSlash"] == [] and r["noZhPlain"] == [], "and a Chinese number alone finds nothing there: %s / %s" % (r["noZhSlash"], r["noZhPlain"]))
        check(r["none"] == [], "an unknown number finds nothing: %s" % r["none"])
        check(any("Joltik" in x for x in r["letter"]), "9: %s" % r["letter"])
        no_problems(page)


@test("the scanner reads English numbers as before, and Chinese ones once told they are Chinese", phone=True)
def zh_scanner(browser, kind):
    with browser.page(kind) as page:
        r = page.evaluate("""() => {
          const names = x => x ? (x.products || []).map(p => (p.zh ? 'zh:' : '') + p.name + ' ' + p.number).concat([x.sure ? 'sure' : 'unsure']) : null;
          const out = {off: names(CardVault.matchScanned('025/165')), offZhNumber: names(CardVault.matchScanned('255/204'))};
          CardVault.openScanner();
          return out; }""")
        check(r["off"] and "sure" in r["off"] and not any(x.startswith("zh:") for x in r["off"]), "English scan: %s" % r["off"])
        check(r["offZhNumber"] is not None and not any(x.startswith("zh:") for x in r["offZhNumber"]), "a Chinese number is not guessed when the scanner isn't told: %s" % r["offZhNumber"])
        page.wait_for_selector("#scanZh")
        check(not page.is_checked("#scanZh"), "the Chinese switch starts off")
        page.check("#scanZh")
        check(page.evaluate("CardVault.state().settings.scanZh") is True, "the switch is kept in settings")
        r = page.evaluate("""() => {
          const names = x => x ? (x.products || []).map(p => (p.zh ? 'zh:' : '') + p.name + ' ' + p.number).concat([x.sure ? 'sure' : 'unsure']) : null;
          return {on: names(CardVault.matchScanned('255/204')), none: names(CardVault.matchScanned('777/204'))}; }""")
        check(r["on"] == ["zh:Carmine 255", "sure"], "Chinese scan: %s" % r["on"])
        check(r["none"] == ["unsure"], "an unknown Chinese number is offered to be checked by hand: %s" % r["none"])
        page.uncheck("#scanZh")
        check(page.evaluate("CardVault.state().settings.scanZh") is False, "and back off")
        no_problems(page)


@test("adding a Chinese card by its number: asks for a key, then shows the price, then adds it", phone=True)
def zh_add_flow(browser, kind):
    with browser.page(kind, seed={"settings": {"pcToken": "TESTKEY"}}) as page:
        page.pc_items[12353505] = item(12353505, "Carmine #255", 13000, 52000)
        page.evaluate("CardVault.openAdd()")
        page.fill("#lookupNumber", "255")
        page.press("#lookupNumber", "Enter")
        page.wait_for_selector("#lookupOut .result")
        check(page.locator("#lookupOut .result").count() == 1, "printings: %s" % page.locator("#lookupOut .result").count())
        text = page.inner_text("#lookupOut")
        check("Carmine" in text and "CSV8C" in text and "Chinese" in text, "the result says what it is: %r" % text)
        page.click("#lookupOut .result")
        page.wait_for_selector("#pickedForm")
        check(page.input_value("#fLanguage") == ZH, "language is %r" % page.input_value("#fLanguage"))
        check(page.locator("#fEd option").count() == 1, "a Chinese card has the one printing")
        page.wait_for_function("document.getElementById('pickedPrice').innerText.includes('$130.00')", timeout=8000)
        check("PriceCharting" in page.inner_text("#pickedPrice"), "the price names its source: %r" % page.inner_text("#pickedPrice"))
        check(any("id=12353505" in u and "t=TESTKEY" in u for u in page.pc_calls), "asked PriceCharting for that card with your key: %s" % page.pc_calls)
        page.click("#pickedForm button[type=submit]")
        recs = page.evaluate("CardVault.state().collection.map(r => ({id: r.productId, lang: r.language, name: r.name, number: r.number, set: r.setName}))")
        check(recs == [{"id": CARMINE, "lang": ZH, "name": "Carmine", "number": "255", "set": "CSV8C"}], "added: %s" % recs)
        no_problems(page)


# ---------------------------------------------------------------- prices
@test("without a PriceCharting key a Chinese card has no price, says why, and nothing is asked", phone=True)
def zh_no_key(browser, kind):
    with browser.page(kind, seed=seed_one()) as page:
        page.wait_for_timeout(1800)   # (longer than the pause before an automatic lookup)
        check(page.pc_calls == [], "nothing may be asked without a key: %s" % page.pc_calls)
        check(total_text(page) == "$0.00", "total %s" % total_text(page))
        rid = page.evaluate("CardVault.state().collection[0].id")
        page.evaluate("id => CardVault.openDetails(id)", rid)
        text = page.inner_text("#drawerBody")
        check("PriceCharting key" in text, "the details page asks for a key: %r" % text[:400])
        check("TCGplayer" not in text, "a Chinese card never says TCGplayer: %r" % text[:400])
        no_problems(page)


@test("with a key the price comes from PriceCharting, counts in the totals and is kept on the device", phone=True)
def zh_with_key(browser, kind):
    with browser.page(kind, seed=seed_one(pcToken="TESTKEY")) as page:
        page.pc_items[12353505] = item(12353505, "Carmine #255", 13000, 52000)
        # (the page looked for it at startup, before the pretend PriceCharting knew the card: ask again)
        done = page.evaluate("CardVault.refreshGradedPrices(true)")
        check(done >= 1, "looked up: %s" % done)
        page.wait_for_function("document.getElementById('totalValue').innerText.trim() === '$260.00'", timeout=8000)
        calls = [u for u in page.pc_calls if "id=12353505" in u]
        check(calls and all("t=TESTKEY" in u and u.startswith("https://www.pricecharting.com/api/product?") for u in calls), "calls: %s" % page.pc_calls)
        rid = page.evaluate("CardVault.state().collection[0].id")
        page.evaluate("id => CardVault.openDetails(id)", rid)
        page.wait_for_selector("#zhPriceBox table")
        text = page.inner_text("#zhPriceBox")
        check("$130.00" in text and "PSA 10" in text and "$520.00" in text, "price box: %r" % text)
        check("PriceCharting" in page.inner_text("#drawerBody"), "the source is named")
        link = page.get_attribute("#drawerBody a[href*='pricecharting.com/game/']", "href")
        check(link == "https://www.pricecharting.com/game/pokemon-chinese-csv8c/carmine-255", "link to the card's page: %s" % link)
        # kept on this device (not in the card list), and gone from the cards when the key goes
        stored = page.evaluate("localStorage.getItem('pokevault.v1.pricecharting')")
        check(stored and '"raw":130' in stored, "kept for later: %r" % (stored or "")[:200])
        no_problems(page)


@test("a key PriceCharting refuses is reported, and the page keeps working", phone=True)
def zh_bad_key(browser, kind):
    with browser.page(kind, seed=seed_one(pcToken="WRONGKEY")) as page:
        page.pc_items[12353505] = item(12353505, "Carmine #255", 13000)
        page.evaluate("CardVault.refreshGradedPrices(true)")
        check(total_text(page) == "$0.00", "no price from a refused key: %s" % total_text(page))
        rid = page.evaluate("CardVault.state().collection[0].id")
        page.evaluate("id => CardVault.openDetails(id)", rid)
        check("didn't accept your key" in page.inner_text("#drawerBody"), "the details page says so: %r" % page.inner_text("#drawerBody")[:400])
        before = len(page.pc_calls)
        page.evaluate("CardVault.refreshGradedPrices(true)")
        check(len(page.pc_calls) == before, "it doesn't keep asking with a key that was refused: %s -> %s" % (before, len(page.pc_calls)))
        page.wait_for_timeout(300)
        no_problems(page)


@test("removing the key takes PriceCharting's prices off the device", phone=True)
def zh_remove_key(browser, kind):
    with browser.page(kind, seed=seed_one(pcToken="TESTKEY")) as page:
        page.pc_items[12353505] = item(12353505, "Carmine #255", 13000)
        page.evaluate("CardVault.refreshGradedPrices(true)")
        page.wait_for_function("document.getElementById('totalValue').innerText.trim() === '$260.00'", timeout=8000)
        page.evaluate("CardVault.openSettings()")
        page.wait_for_selector("#sPcToken")
        page.fill("#sPcToken", "")
        page.dispatch_event("#sPcToken", "change")
        page.wait_for_function("document.getElementById('totalValue').innerText.trim() === '$0.00'", timeout=5000)
        check(page.evaluate("localStorage.getItem('pokevault.v1.pricecharting')") is None, "the saved prices are gone")
        check(page.evaluate("CardVault.state().catalog.products.filter(p => p.zh).every(p => !Object.keys(p.prices).length)"), "the cards carry no prices")
        check(page.evaluate("CardVault.state().collection.length") == 1, "the card itself stays")
        no_problems(page)


@test("a Chinese card's price card says PriceCharting and has no TCGplayer table", phone=True)
def zh_price_card(browser, kind):
    with browser.page(kind, seed={"settings": {"pcToken": "TESTKEY"}}) as page:
        page.pc_items[12353505] = item(12353505, "Carmine #255", 13000, 52000)
        page.evaluate("pid => CardVault.openPriceCard(pid)", CARMINE)
        page.wait_for_selector("#zhPriceBox table", timeout=8000)
        body = page.inner_text("#drawerBody")
        check("PriceCharting price" in body and "$130.00" in body, "price card: %r" % body[:500])
        check("TCGplayer price" not in body and "Price over time" not in body, "no TCGplayer sections: %r" % body[:500])
        check("View on PriceCharting" in body, "link names PriceCharting")
        no_problems(page)


@test("Chinese prices are never put on a share page", phone=True)
def zh_share(browser, kind):
    with browser.page(kind, seed=seed_one(pcToken="TESTKEY")) as page:
        page.pc_items[12353505] = item(12353505, "Carmine #255", 13000)
        page.evaluate("CardVault.refreshGradedPrices(true)")
        page.wait_for_function("document.getElementById('totalValue').innerText.trim() === '$260.00'", timeout=8000)
        out = page.evaluate("""() => {
          const r = CardVault.state().collection[0];
          return {priced: CardVault.shareItem(r, {prices: true}), plain: CardVault.shareItem(r, {}),
                  want: CardVault.shareWant({id: 'w1', productId: %d, name: 'Carmine', number: '255', qty: 1}, {prices: true})}; }""" % CARMINE)
        check("v" not in out["priced"], "no price in a shared card: %s" % out["priced"])
        check(out["priced"].get("l") == ZH and out["priced"].get("p") == CARMINE, "language and card kept: %s" % out["priced"])
        check("i" not in out["priced"], "no picture address of its own is added: %s" % out["priced"])
        check(out["want"].get("l") == ZH, "a shared want knows it is Chinese: %s" % out["want"])
        no_problems(page)


# ---------------------------------------------------------------- goals, sets, wants
@test("Pokémon goals can count Chinese cards: only, with the others, or not at all", phone=True)
def zh_goals(browser, kind):
    with browser.page(kind) as page:
        r = page.evaluate("""() => { const f = (l) => CardVault.monPrints('Pikachu', l).map(p => (p.zh ? 'zh:' : '') + p.number);
          return {def: f(''), en: f('en'), jp: f('jp'), zh: f('zh'), all: f('all')}; }""")
        check(not any(x.startswith("zh:") for x in r["def"]), "the default doesn't change: %s" % r["def"])
        check(not any(x.startswith("zh:") for x in r["en"]) and not any(x.startswith("zh:") for x in r["jp"]), "English only, Japanese only: %s / %s" % (r["en"], r["jp"]))
        check(r["zh"] and all(x.startswith("zh:") for x in r["zh"]) and len(r["zh"]) == 3, "Chinese only: %s" % r["zh"])
        check(len(r["all"]) == len(r["def"]) + 3, "all adds the three Chinese Pikachu: %s vs %s" % (len(r["all"]), len(r["def"])))
        no_problems(page)


@test("a Chinese set counts in the Sets tab and shows its picture and language", phone=True)
def zh_sets(browser, kind):
    seed = {"collection": [zh_record(CARMINE, "Carmine", "255", setName="CSV8C"), zh_record(PIKACHU_A, "Pikachu", "25", setName="CSV8C")]}
    with browser.page(kind, seed=seed) as page:
        sets = page.evaluate("CardVault.setsData().map(s => ({name: s.group.name, total: s.total, have: s.have, zh: !!s.group.zh}))")
        check(sets == [{"name": "CSV8C", "total": 4, "have": 2, "zh": True}], "sets: %s" % sets)
        page.evaluate("CardVault.setTab('sets')")
        page.wait_for_selector("#setsList")
        text = page.inner_text("#setsList")
        check("CSV8C" in text and "Chinese" in text, "the Sets tab names the set and its language: %r" % text[:300])
        no_problems(page)


@test("a Chinese card can be wanted, and a want is priced by PriceCharting", phone=True)
def zh_wants(browser, kind):
    with browser.page(kind, seed={"settings": {"pcToken": "TESTKEY"}, "wants": [
            {"id": "w1", "productId": MILOTIC, "name": "Milotic", "number": "244", "setName": "CSV8C", "edition": "Normal", "qty": 1, "added": "2026-01-01T00:00:00Z"}]}) as page:
        page.pc_items[12353504] = item(12353504, "Milotic #244", 4500)
        page.evaluate("CardVault.refreshGradedPrices(true)")
        page.wait_for_function("CardVault.wantPrice(CardVault.state().wants[0]) === 45", timeout=8000)
        check(page.evaluate("CardVault.wantSource(CardVault.state().wants[0])") == "PriceCharting", "the want's source")
        page.evaluate("CardVault.setTab('wants')")
        page.wait_for_timeout(300)
        text = page.inner_text("#panel-wants")
        check("Milotic" in text and "$45.00" in text, "the want list shows the price: %r" % text[:300])
        no_problems(page)


# ---------------------------------------------------------------- without the list
@test("the website works as before when there is no Chinese card list", phone=True)
def zh_absent(browser, kind):
    with browser.page(kind, base=browser.no_zh_url) as page:
        info = page.evaluate("({zh: CardVault.state().catalog.products.filter(p => p.zh).length, all: CardVault.state().catalog.products.length, "
                             "groups: CardVault.state().catalog.groups.filter(g => g.zh).length})")
        check(info["zh"] == 0 and info["groups"] == 0 and info["all"] >= 30, "catalog: %s" % info)
        page.evaluate("CardVault.openAdd()")
        page.fill("#lookupNumber", "255")
        page.press("#lookupNumber", "Enter")
        page.wait_for_selector("#lookupOut .notice")
        check(page.locator("#lookupOut .result").count() == 0, "nothing to find")
        for tab in ("collection", "search", "sets", "wants", "market"):
            page.evaluate("t => CardVault.setTab(t)", tab)
            page.wait_for_timeout(100)
        no_problems(page)


@test("a saved Chinese card stays in the collection, unpriced, when the Chinese list is missing", phone=True)
def zh_absent_saved(browser, kind):
    with browser.page(kind, base=browser.no_zh_url, seed=seed_one()) as page:
        check(page.evaluate("CardVault.state().collection.length") == 1, "the card is still there")
        rid = page.evaluate("CardVault.state().collection[0].id")
        page.evaluate("id => CardVault.openDetails(id)", rid)
        page.wait_for_selector("#drawerBody")
        check("Carmine" in page.inner_text("#drawerBody"), "the details open")
        no_problems(page)
