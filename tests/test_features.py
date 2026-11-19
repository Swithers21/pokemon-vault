"""Checks of the newer features: prices that look inflated, and rapid scan (cards going straight into the collection)."""
from harness import test, check, no_problems
from test_core import owned


def settle(page, ms=500):
    page.wait_for_timeout(ms)


def read_card(page, text, until=None, wait=5000):
    """The pretend text reader 'sees' this text. It has to read it twice in a row before the card counts, so this waits
    until the page shows `until` (a JavaScript test), or just the given time when nothing should happen."""
    page.evaluate("t => { window.__ocrText = t; }", text)
    if until:
        page.wait_for_function(until, timeout=wait)
    else:
        page.wait_for_timeout(wait)


def collection(page):
    return page.evaluate("CardVault.state().collection.map(r => ({name: r.name, number: r.number, edition: r.edition, condition: r.condition, "
                         "qty: r.qty, location: r.location}))")


def open_rapid(page, camera=True):
    page.evaluate("CardVault.openScanner()")
    page.wait_for_selector("#scanRapid")
    if not page.is_checked("#scanRapid"):
        page.check("#scanRapid")
    if camera:
        page.wait_for_function("CardVault.scanState() && CardVault.scanState().stream", timeout=8000)
    else:
        page.wait_for_selector("#scanForm:not([hidden])", timeout=8000)


# ---------------------------------------------------------------- prices that look inflated
@test("which prices count as inflated", smoke=True)
def shaky_rule(browser, kind):
    with browser.page(kind) as page:
        flags = page.evaluate("""() => {
          const out = {};
          for (const p of CardVault.state().catalog.products) for (const [ed, sub] of Object.entries(p.prices)) out[p.name + '|' + ed] = !!CardVault.shakySub(sub);
          return out; }""")
        yes = sorted(k for k, v in flags.items() if v)
        check(yes == ["Mixed Sample|Holofoil", "Shaky Sample ex|Holofoil"], "flagged: %s" % yes)
        # (not flagged: small amounts, market below the lowest listing, no listing, no sales, a mild gap, ordinary cards)
        check(not flags["Cheap Sample|Normal"] and not flags["Backwards Sample|Holofoil"] and not flags["Mild Sample|Holofoil"], "edge cases")


@test("inflated prices are tagged, explained and can be counted at the lowest listing", phone=True)
def shaky_screens(browser, kind):
    with browser.page(kind) as page:
        recs = [owned(page, "Shaky Sample ex", "120/198", "Holofoil", 1), owned(page, "Mixed Sample", "126/198", "Holofoil", 2),
                owned(page, "Mixed Sample", "126/198", "Normal", 1), owned(page, "Charizard ex", "199/165", "Holofoil", 1)]
        page.evaluate("recs => { CardVault.state().collection.push(...recs); CardVault.save(); CardVault.render(); }", recs)
        # the total counts them at market, with a note
        total = 120 + 2 * 60 + 2 + 95
        check(page.inner_text("#totalValue").strip() == "$%s.00" % format(total, ","), "total %s" % page.inner_text("#totalValue"))
        note = page.inner_text("#valueSub")
        check("3 cards" in note and "may be inflated" in note, "note under the total: %r" % note)
        check(page.locator(".shaky-flag").count() == 2, "tags in the collection: %s" % page.locator(".shaky-flag").count())
        # the card page explains it
        rid = page.evaluate("CardVault.state().collection[0].id")
        page.evaluate("id => CardVault.openDetails(id)", rid)
        check("may be inflated" in page.inner_text("#drawerBody"), "details drawer has no explanation")
        page.evaluate("document.getElementById('drawerClose').click()")
        # switch them to the lowest listing from the note
        page.click("#valueSub [data-action=shaky-toggle]")
        low_total = 30 + 2 * 12 + 2 + 95
        check(page.inner_text("#totalValue").strip() == "$%s.00" % low_total, "total at lowest listing %s" % page.inner_text("#totalValue"))
        check(page.locator(".shaky-flag", has_text="lowest listing").count() == 2, "tags should say lowest listing")
        check(page.evaluate("CardVault.state().settings.shakyLow") is True, "setting not kept")
        # and back
        page.click("#valueSub [data-action=shaky-toggle]")
        check(page.inner_text("#totalValue").strip() == "$%s.00" % format(total, ","), "total back at market")
        no_problems(page)


@test("inflated-price setting is in Settings and survives a reload", phone=True)
def shaky_setting(browser, kind):
    with browser.page(kind) as page:
        page.evaluate("CardVault.openSettings()")
        page.check("#sShakyLow")
        page.evaluate("document.getElementById('drawerClose').click()")
        page.reload()
        page.wait_for_function("window.CardVault && CardVault.state().catalog")
        check(page.evaluate("CardVault.state().settings.shakyLow") is True, "not kept after reload")


@test("scan-to-check and card price page warn about an inflated price", phone=True)
def shaky_check(browser, kind):
    with browser.page(kind) as page:
        page.evaluate("CardVault.openScanner({check: true})")
        page.wait_for_selector("#scanForm", state="attached")
        page.evaluate("document.getElementById('scanForm').hidden = false")
        page.fill("#scanNumber", "120/198")
        page.click("#scanForm button[type=submit]")
        page.wait_for_selector("#lookupOut .check-card")
        check("may be inflated" in page.inner_text("#lookupOut .check-card"), "no warning in scan-to-check")
        page.fill("#scanNumber", "121/198")
        page.click("#scanForm button[type=submit]")
        page.wait_for_selector("#lookupOut .check-card")
        check("may be inflated" not in page.inner_text("#lookupOut .check-card"), "a cheap card was flagged")
        pid = page.evaluate("CardVault.state().catalog.products.find(p => p.name === 'Shaky Sample ex').id")
        page.evaluate("id => CardVault.openPriceCard(id)", pid)
        check("may be inflated" in page.inner_text("#drawerBody"), "no warning on the price page")
        no_problems(page)


# ---------------------------------------------------------------- rapid scan
@test("rapid scan: a card read by the camera is added and the camera stays on", phone=True, smoke=True)
def rapid_basic(browser, kind):
    with browser.page(kind) as page:
        open_rapid(page)
        read_card(page, "Illus. Test 013/198 SVI", until="CardVault.state().collection.length === 1")
        recs = collection(page)
        check(len(recs) == 1 and recs[0]["name"] == "Sprigatito" and recs[0]["qty"] == 1 and recs[0]["condition"] == "Near Mint", "collection: %s" % recs)
        check(page.evaluate("CardVault.scanState().stream.active"), "the camera was turned off")
        check("Just added: 1 card" in page.inner_text("#rapidTray"), "tray: %s" % page.inner_text("#rapidTray"))
        # holding the same card up for a while does not add it again
        page.wait_for_timeout(3500)
        check(collection(page)[0]["qty"] == 1, "the same card was added twice: %s" % collection(page))
        # the next card is read straight after
        read_card(page, "Illus. Test 133/198 SVI", until="CardVault.state().collection.length === 2", wait=9000)
        check(sorted(r["name"] for r in collection(page)) == ["Eevee", "Sprigatito"], "second card: %s" % collection(page))
        check(page.locator(".rapid-row").count() == 2, "tray rows")
        no_problems(page)


@test("rapid scan: Undo, one more copy and a different printing", phone=True)
def rapid_tray(browser, kind):
    with browser.page(kind, camera=False) as page:
        # one Eevee (Normal) is already in the binder: scanning adds one more to that line, and Undo takes only that one back
        have = owned(page, "Eevee", "133/198", "Normal", 3)
        page.evaluate("r => { CardVault.state().collection.push(r); CardVault.save(); }", have)
        open_rapid(page, camera=False)
        page.fill("#scanNumber", "133/198")
        page.click("#scanForm button[type=submit]")
        check(collection(page)[0]["qty"] == 4, "merged into the line you had: %s" % collection(page))
        page.click(".rapid-row .r-plus")
        check(collection(page)[0]["qty"] == 5 and "×2" in page.inner_text(".rapid-row .r-qty"), "+1: %s" % collection(page))
        page.select_option(".rapid-row .r-ed", "Reverse Holofoil")
        recs = {r["edition"]: r["qty"] for r in collection(page)}
        check(recs == {"Normal": 3, "Reverse Holofoil": 2}, "printing change moved only the new copies: %s" % recs)
        check(page.evaluate("CardVault.state().settings.rapidEd") == "Reverse Holofoil", "last printing not remembered")
        page.click(".rapid-row .r-undo")
        recs = collection(page)
        check(len(recs) == 1 and recs[0]["edition"] == "Normal" and recs[0]["qty"] == 3, "Undo should leave what you had: %s" % recs)
        check(page.locator(".rapid-row").count() == 0, "the tray line should be gone")
        no_problems(page)


@test("rapid scan: uses the printing, condition and place you chose last", phone=True)
def rapid_defaults(browser, kind):
    with browser.page(kind, camera=False, seed={"settings": {"rapidEd": "Reverse Holofoil", "rapidScan": True}}) as page:
        open_rapid(page, camera=False)
        page.select_option("#rapidCond", "Lightly Played")
        page.fill("#rapidLoc", "Binder 1")
        page.fill("#scanNumber", "133/198")
        page.click("#scanForm button[type=submit]")
        recs = collection(page)
        check(recs == [{"name": "Eevee", "number": "133/198", "edition": "Reverse Holofoil", "condition": "Lightly Played", "qty": 1, "location": "Binder 1"}], "added: %s" % recs)
        # a card that has no such printing gets its own first printing
        page.fill("#scanNumber", "013/198")
        page.click("#scanForm button[type=submit]")
        check({r["name"]: r["edition"] for r in collection(page)} == {"Eevee": "Reverse Holofoil", "Sprigatito": "Normal"}, "fallback printing: %s" % collection(page))
        # the choices are still there next time
        page.evaluate("document.getElementById('drawerClose').click()")
        page.evaluate("CardVault.openScanner()")
        check(page.input_value("#rapidCond") == "Lightly Played" and page.input_value("#rapidLoc") == "Binder 1" and page.is_checked("#scanRapid"), "choices not kept")


@test("rapid scan: several printings share the number, so you pick", phone=True)
def rapid_pick(browser, kind):
    with browser.page(kind) as page:
        open_rapid(page)
        read_card(page, "025/165", until="document.querySelectorAll('#lookupOut .result').length === 3")
        check(collection(page) == [], "nothing should be added before you pick: %s" % collection(page))
        check(page.locator("#lookupOut .result").count() == 3, "printings offered: %s" % page.locator("#lookupOut .result").count())
        page.locator("#lookupOut .result").first.click()
        recs = collection(page)
        check(len(recs) == 1 and recs[0]["number"] == "025/165", "picked card: %s" % recs)
        check(page.locator("#lookupOut .result").count() == 0, "the list of printings should close")
        # skipping a card adds nothing and goes back to looking
        page.evaluate("t => { window.__ocrText = ''; }", "")
        page.wait_for_timeout(1500)
        read_card(page, "063/198", until="document.querySelectorAll('#lookupOut .result').length === 2", wait=9000)
        check(page.locator("#lookupOut .result").count() == 2, "second pick list")
        page.click("#scanAgain")
        check(len(collection(page)) == 1 and page.locator("#lookupOut .result").count() == 0, "skip: %s" % collection(page))
        no_problems(page)


@test("rapid scan: a number TCGplayer doesn't have adds nothing", phone=True)
def rapid_unknown(browser, kind):
    with browser.page(kind) as page:
        open_rapid(page)
        read_card(page, "999/198", wait=5000)
        check(collection(page) == [], "added something for an unknown number: %s" % collection(page))
        check("no card with that number" in page.inner_text("#scanStatus"), "status: %s" % page.inner_text("#scanStatus"))


@test("rapid scan: typing a number works without a camera, and twice means two copies", phone=True)
def rapid_typed(browser, kind):
    with browser.page(kind, camera=False) as page:
        open_rapid(page, camera=False)
        for _ in range(2):
            page.fill("#scanNumber", "013/198")
            page.click("#scanForm button[type=submit]")
        check(collection(page)[0]["qty"] == 2, "typed twice: %s" % collection(page))
        check("×2" in page.inner_text(".rapid-row .r-qty") or page.locator(".rapid-row").count() == 2, "tray after typing twice")
        no_problems(page)


@test("rapid scan off: the normal scan still asks you to pick and adds nothing by itself", phone=True)
def rapid_off(browser, kind):
    with browser.page(kind) as page:
        page.evaluate("CardVault.openScanner()")
        page.wait_for_selector("#scanRapid")
        check(not page.is_checked("#scanRapid"), "rapid scan should start off")
        page.wait_for_function("CardVault.scanState() && CardVault.scanState().stream", timeout=8000)
        read_card(page, "013/198", until="document.querySelectorAll('#lookupOut .result').length === 1")
        check(collection(page) == [], "added without being asked: %s" % collection(page))
        check(page.locator("#lookupOut .result").count() == 1, "the printing should be offered")
        no_problems(page)


@test("rapid scan: switching it on and off while scanning", phone=True)
def rapid_toggle(browser, kind):
    with browser.page(kind) as page:
        page.evaluate("CardVault.openScanner()")
        page.wait_for_function("CardVault.scanState() && CardVault.scanState().stream", timeout=8000)
        page.check("#scanRapid")
        read_card(page, "013/198", until="CardVault.state().collection.length === 1")
        check(len(collection(page)) == 1, "rapid on adds")
        page.uncheck("#scanRapid")
        check(page.is_hidden("#rapidOpts"), "the options should fold away when off")
        check(page.locator(".rapid-row").count() == 1, "what was added can still be undone after switching off")
        check(page.evaluate("CardVault.state().settings.rapidScan") is False, "setting")
        no_problems(page)
