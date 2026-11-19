"""Checks of what the website already did: opening, finding cards, adding them, totals, goals, the grading fee list."""
import json
import re
from datetime import date, timedelta

from harness import test, check, no_problems


def record(**kw):
    """A collection entry as the website stores it."""
    base = {"id": "r" + str(abs(hash(json.dumps(kw, sort_keys=True))) % 10**8), "productId": None, "name": "", "productName": "", "setName": "",
            "number": "", "rarity": "", "edition": "Normal", "condition": "Near Mint", "language": "English", "qty": 1, "added": "2026-01-01T00:00:00Z"}
    base.update(kw)
    base["productName"] = base["productName"] or base["name"]
    return base


def product_id(page, name, number=None):
    return page.evaluate("([n, num]) => { const p = CardVault.state().catalog.products.find(x => x.name === n && (!num || x.number === num)); return p && p.id; }", [name, number])


def owned(page, name, number, edition="Normal", qty=1, **extra):
    return record(productId=product_id(page, name, number), name=name, number=number, edition=edition, qty=qty, **extra)


@test("opens without problems, card list loaded", phone=True, smoke=True)
def opens(browser, kind):
    with browser.page(kind) as page:
        n = page.evaluate("CardVault.state().catalog.products.length")
        check(n >= 30, "the card list has %s products" % n)
        check(page.is_visible("#totalValue"), "the collection value is not shown")
        for tab in ("collection", "search", "insights", "sets", "wants", "decks", "trades", "market"):
            page.evaluate("t => CardVault.setTab(t)", tab)
            page.wait_for_timeout(120)
        no_problems(page)


@test("opens with no card list at all", phone=True)
def opens_without_data(browser, kind):
    # (the card list file is missing, as on a bad day for the daily update)
    with browser.page(kind, base=browser.no_data_url) as page:
        check(page.evaluate("CardVault.state().catalog") is None, "a card list appeared from nowhere")
        page.evaluate("CardVault.openAdd()")
        page.fill("#lookupNumber", "025/198")
        page.click("#lookupForm button[type=submit]")
        check("card list" in page.inner_text("#lookupOut").lower(), "no explanation when the card list is missing")
        no_problems(page)


@test("finding cards by number and by name", smoke=True)
def finding(browser, kind):
    with browser.page(kind) as page:
        n = lambda q: page.evaluate("q => CardVault.findByNumber(q).length", q)
        check(n("025/165") == 3, "025/165 should have 3 printings (two English, one Japanese), found %s" % n("025/165"))
        check(n("SVP085") == 1, "SVP085 not found")
        check(n("25") >= 3, "a bare number should find every card numbered 25")
        check(n("999/999") == 0, "an unknown number found something")
        names = page.evaluate("CardVault.searchByName('pikachu', 50).items.map(p => p.name)")
        check(len(names) >= 6 and not any("Elite Trainer" in x for x in names), "name search: %s" % names)
        check(page.evaluate("CardVault.searchByName('trainer box', 50).items.length") == 0, "sealed products must not show up as cards")


@test("reading a scanned number", smoke=True)
def reading(browser, kind):
    with browser.page(kind) as page:
        m = lambda t: page.evaluate("t => { const r = CardVault.matchScanned(t); return r && {number: r.number, n: r.products.length, sure: r.sure}; }", t)
        check(m("Illus. Test 013/198 SVI") == {"number": "013/198", "n": 1, "sure": True}, "clean read: %s" % m("013/198"))
        check(m("O13/198")["number"] == "013/198", "an O read for 0 should be fixed: %s" % m("O13/198"))
        check(m("0I3/I98")["number"] == "013/198", "I read for 1 should be fixed: %s" % m("0I3/I98"))
        check(m("SVP 085")["number"] == "SVP085", "promo code")
        unknown = m("999/198")
        check(unknown and unknown["sure"] is False, "a number TCGplayer doesn't have must not be 'sure': %s" % unknown)
        check(m("no number here") is None, "text with no number")


@test("adding a card by number, then it counts in the total", phone=True, smoke=True)
def add_by_number(browser, kind):
    with browser.page(kind) as page:
        page.evaluate("CardVault.openAdd()")
        page.fill("#lookupNumber", "133/198")
        page.click("#lookupForm button[type=submit]")
        page.click("#lookupOut .result")
        page.wait_for_selector("#pickedForm")
        page.select_option("#fEd", "Reverse Holofoil")
        page.fill("#fQty", "3")
        page.click("#pickedForm button[type=submit]")
        recs = page.evaluate("CardVault.state().collection")
        check(len(recs) == 1 and recs[0]["name"] == "Eevee" and recs[0]["qty"] == 3 and recs[0]["edition"] == "Reverse Holofoil", "added: %s" % recs)
        check(page.inner_text("#totalValue").strip() == "$1.50", "total is %s, expected $1.50" % page.inner_text("#totalValue"))
        # adding the same again merges into one line
        page.evaluate("CardVault.openAdd()")
        page.fill("#lookupNumber", "133/198")
        page.click("#lookupForm button[type=submit]")
        page.click("#lookupOut .result")
        page.select_option("#fEd", "Reverse Holofoil")
        page.click("#pickedForm button[type=submit]")
        recs = page.evaluate("CardVault.state().collection")
        check(len(recs) == 1 and recs[0]["qty"] == 4, "merged: %s" % recs)
        no_problems(page)


@test("collection value, condition adjustment and the printing used", phone=True)
def value(browser, kind):
    with browser.page(kind) as page:
        seed = [owned(page, "Charizard ex", "199/165", "Holofoil", 2),
                owned(page, "Charizard ex", "006/165", "Holofoil", 1, condition="Lightly Played")]
        page.evaluate("recs => { CardVault.state().collection.push(...recs); CardVault.save(); CardVault.render(); }", seed)
        # 2 x 95.00 + 8.50 at 85% for Lightly Played
        expected = 2 * 95.00 + round(8.50 * 0.85, 2)
        got = page.inner_text("#totalValue").replace("$", "").replace(",", "")
        check(abs(float(got) - expected) < 0.011, "total %s, expected %.2f" % (got, expected))
        no_problems(page)


@test("Pokemon goals: whose prints count", smoke=False)
def pokemon_goals(browser, kind):
    with browser.page(kind) as page:
        prints = page.evaluate("CardVault.monPrints('Pikachu', '').map(p => p.name + '|' + p.number)")
        names = [x.split("|")[0] for x in prints]
        check("Pikachu ex" in names and "Detective Pikachu" in names and "Pikachu with Grey Felt Hat" in names, "Pikachu prints: %s" % prints)
        check(not any("Raichu" in x or "Energy" in x for x in names), "Raichu and Energy are not Pikachu: %s" % prints)
        jp = page.evaluate("CardVault.monPrints('Pikachu', 'jp').length")
        en = page.evaluate("CardVault.monPrints('Pikachu', 'en').length")
        check(jp == 1 and en == len(prints) - 1, "language filter: jp %s en %s of %s" % (jp, en, len(prints)))
        check(page.evaluate("CardVault.monPrints('Mew', '').map(p => p.name)") == ["Mew ex"], "Mew finds Mew ex only, not Mewtwo")
        base = lambda n: page.evaluate("n => { const p = CardVault.state().catalog.products.find(x => x.name === n); return CardVault.monBase(p); }", n)
        check(base("Detective Pikachu") == "Pikachu" and base("Pikachu ex") == "Pikachu" and base("Charizard ex") == "Charizard", "monBase")
        cands = page.evaluate("CardVault.monCandidates('pika').map(c => c.name)")
        check(cands and cands[0] == "Pikachu", "candidates for 'pika': %s" % cands)


@test("goals show up when you scan to check a card", phone=True)
def goal_notes(browser, kind):
    goals = [{"id": "mpikachu", "mon": "Pikachu", "name": "Pikachu", "lang": "", "added": "2026-01-01T00:00:00Z"},
             {"id": "g9002", "groupId": 9002, "name": "SV01: Scarlet & Violet Base Set", "mode": "number", "added": "2026-01-01T00:00:00Z"}]
    with browser.page(kind, seed={"goals": goals}) as page:
        page.evaluate("CardVault.openScanner({check: true})")
        page.evaluate("document.getElementById('scanForm').hidden = false")
        page.fill("#scanNumber", "063/198")
        page.click("#scanForm button[type=submit]")
        page.wait_for_selector("#lookupOut .check-card")
        text = page.inner_text("#lookupOut")
        check("Counts toward your" in text and "Pikachu" in text, "goal note missing from the check: %s" % text[:300])
        no_problems(page)


@test("'since you last looked' appears when prices moved", phone=True)
def since_last_looked(browser, kind):
    seen = (date.today() - timedelta(days=8)).isoformat()
    probe = {"settings": {"lookSeen": seen, "tab": "collection"}}
    with browser.page(kind, seed=probe) as page:
        page.evaluate("recs => { CardVault.state().collection.push(...recs); CardVault.save(); }", [owned(page, "Charizard ex", "199/165", "Holofoil", 1)])
        page.reload()
        page.wait_for_function("window.CardVault && CardVault.state().catalog")
        page.wait_for_selector("#lookBanner:not([hidden])", timeout=5000)
        check("Since you last looked" in page.inner_text("#lookBanner"), "banner text")
        no_problems(page)


@test("grading fee list is complete and sensible", smoke=True)
def fee_table(browser, kind):
    with browser.page(kind) as page:
        table = page.evaluate("CardVault.GRADING_FEE_TABLE")
        check(sorted(table) == ["BGS", "CGC", "PSA", "SGC", "TAG"], "companies: %s" % sorted(table))
        for co, t in table.items():
            check(re.match(r"^\d{4}-\d\d-\d\d$", t["checked"]), "%s checked date %r" % (co, t["checked"]))
            check(t["source"].startswith("https://"), "%s source" % co)
            check(sum(1 for l in t["levels"] if l.get("usual")) == 1, "%s needs exactly one 'usual' level" % co)
            for l in t["levels"]:
                check(l["fee"] is None or l["fee"] > 0, "%s %s fee %r" % (co, l["name"], l["fee"]))
            usual = [l for l in t["levels"] if l.get("usual")][0]
            check(usual["fee"] is not None and not usual.get("paused"), "%s usual level is not open with a fee" % co)
        check(page.evaluate("CardVault.gradingUsual('PSA').fee") > 0, "gradingUsual")
        # the fee list is shown in Insights > grading, and in Settings it can be edited
        page.evaluate("CardVault.setTab('insights')")
        no_problems(page)


@test("Card search tab finds a card and shows its price card", phone=True)
def card_search(browser, kind):
    with browser.page(kind) as page:
        page.evaluate("CardVault.setTab('search')")
        page.fill("#csQ", "charizard")
        page.wait_for_selector("#csOut .cs-card", timeout=5000)
        check(page.locator("#csOut .cs-card").count() == 2, "charizard should be two cards (Charizard, Charizard ex), got %s" % page.locator("#csOut .cs-card").count())
        page.fill("#csQ", "shaky sample")
        page.wait_for_selector("#csOut .cs-card [data-cs-open]", timeout=5000)
        page.locator("#csOut [data-cs-open]").first.click()
        page.wait_for_selector("#drawerBody .price-table", timeout=5000)
        check("TCGplayer price" in page.inner_text("#drawerBody"), "price card did not open")
        no_problems(page)


@test("backup file round trip keeps cards", smoke=False)
def backup_round_trip(browser, kind):
    with browser.page(kind) as page:
        page.evaluate("recs => { CardVault.state().collection.push(...recs); CardVault.save(); }", [owned(page, "Pikachu", "173/165", "Holofoil", 2, location="Binder 1")])
        payload = page.evaluate("CardVault.backupPayload()")
        check(payload["collection"][0]["qty"] == 2 and payload["collection"][0]["location"] == "Binder 1", "payload: %s" % payload["collection"])
        check(json.loads(json.dumps(payload))["kind"] == "backup", "payload kind")
