"""Checks of the Chinese card list updater (update_zh_cards.py) against pretend PriceCharting pages, so nothing here needs
the internet.   python tests/test_zh_update.py
"""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import update_zh_cards as zh  # noqa: E402


def row(pid, console, slug, title, image="abcdef123456", price="$1.00"):
    # the shape of PriceCharting's set page rows (kept from a real page, prices and all, which the updater must ignore)
    return ('<tr id="product-%d" data-product="%d"> <td class="image"> <div> <a href="https://www.pricecharting.com/game/%s/%s" title="%d">'
            ' <img class="photo" loading="lazy" src="https://storage.googleapis.com/images.pricecharting.com/%s/60.jpg" /> </a> </div> </td>'
            ' <td class="title" title="%d"> <a href="/game/%s/%s">%s</a> </td> <td class="price numeric used_price"> <span class="js-price">%s</span> </td>'
            ' <td class="add_to container"><a href="/publish-offer?product=%d">add</a></td> </tr>') % (
                pid, pid, console, slug, pid, image, pid, console, slug, title, price, pid)


def page(title, rows, cursor=None):
    form = ""
    if cursor is not None:
        form = ('<form method="POST" action="" class="next_page js-next-page"> <input type="hidden" name="sort" value="" />'
                ' <input type="hidden" name="when" value="none" /> <input type="hidden" name="cursor" value="%d" />'
                ' <input type="submit" value="more results &raquo;" /> </form>') % cursor
    return "<html><head><title>%s</title></head><body><table id=\"games_table\"><tbody>%s</tbody>%s</table></body></html>" % (title, "".join(rows), form)


class Titles(unittest.TestCase):
    def test_split(self):
        self.assertEqual(zh.split_title("Carmine #255"), ("Carmine", "255"))
        self.assertEqual(zh.split_title("Pikachu [Reverse Holo] #25"), ("Pikachu (Reverse Holo)", "25"))
        self.assertEqual(zh.split_title("Charizard ex [Gold] [Foil] #10a"), ("Charizard ex (Gold, Foil)", "10a"))
        self.assertEqual(zh.split_title("Booster Box"), ("Booster Box", ""))
        self.assertEqual(zh.split_title("Farfetch&#39;d #7"), ("Farfetch'd", "7"))

    def test_set_name(self):
        self.assertEqual(zh.set_name("Pokemon Chinese CSV8C Card Prices | Holo, Rare, &amp; Graded Cards", "pokemon-chinese-csv8c"), "CSV8C")
        self.assertEqual(zh.set_name("Pokemon Chinese Gem Pack 3 Card Prices | x", "pokemon-chinese-gem-pack-3"), "Gem Pack 3")
        self.assertEqual(zh.set_name("", "pokemon-chinese-gem-pack-3"), "GEM PACK 3")


class Rows(unittest.TestCase):
    def test_parse(self):
        html = page("t", [row(1, "pokemon-chinese-csv8c", "carmine-255", "Carmine #255", "inbukwejsstzqsxh", "$130.00"),
                          row(2, "pokemon-chinese-csv8c", "booster-box", "Booster Box", "")])
        rows = zh.parse_rows(html)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], {"id": 1, "console": "pokemon-chinese-csv8c", "slug": "carmine-255", "name": "Carmine", "number": "255", "image": "inbukwejsstzqsxh"})
        self.assertEqual(rows[1]["number"], "")
        self.assertNotIn("130", json.dumps(rows))   # no price anywhere in what is kept

    def test_next_form(self):
        self.assertEqual(zh.next_page_fields(page("t", [], cursor=150)), [("sort", ""), ("when", "none"), ("cursor", "150")])
        self.assertIsNone(zh.next_page_fields(page("t", [])))


class Whole(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.real = zh.fetch
        zh.PAUSE = 0
        c = "pokemon-chinese-csv8c"
        first = [row(i, c, "card-%d" % i, "Card %d #%d" % (i, i)) for i in range(1, 4)]
        second = [row(i, c, "card-%d" % i, "Card %d #%d" % (i, i)) for i in range(4, 6)]

        def fake(url, data=None, tries=3):
            self.calls.append((url, data))
            if url.endswith("/category/pokemon-cards"):
                return '<a href="/console/pokemon-chinese-csv8c">x</a><a href="/console/pokemon-japanese-foo">y</a><a href="/console/pokemon-chinese-gem-pack">z</a>'
            if url.endswith("/console/pokemon-chinese-gem-pack"):
                return page("Pokemon Chinese Gem Pack Card Prices | x", [row(9, "pokemon-chinese-gem-pack", "pikachu-1", "Pikachu #1")])
            if url.endswith("/console/" + c):
                if data is None:
                    return page("Pokemon Chinese CSV8C Card Prices | x", first, cursor=3)
                self.assertIn(b"cursor=3", data)
                return page("Pokemon Chinese CSV8C Card Prices | x", second)
            if "/game/" in url:
                return "<html><body>Details Release Date: March 13, 2026 Publisher: x</body></html>"
            raise AssertionError(url)
        zh.fetch = fake

    def tearDown(self):
        zh.fetch = self.real

    def test_build(self):
        data = zh.build()
        self.assertEqual([g[:2] for g in data["groups"]], [["pokemon-chinese-csv8c", "CSV8C"], ["pokemon-chinese-gem-pack", "Gem Pack"]])
        self.assertEqual(data["groups"][0][2], "2026-03-13")
        ids = [g[3] for g in data["groups"]]   # every set has its own id, made from its page name (so it is the same if the saved list is lost)
        self.assertEqual(len(set(ids)), 2)
        self.assertTrue(all(zh.GROUP_ID_START <= i < zh.GROUP_ID_START + zh.GROUP_ID_SPAN for i in ids), ids)
        self.assertEqual([g[3] for g in zh.build(None)["groups"]], ids)
        self.assertEqual(zh.new_group_id("pokemon-chinese-csv8c", set()), ids[0])
        self.assertEqual(zh.new_group_id("pokemon-chinese-csv8c", {ids[0]}), ids[0] + 1)   # (a clash takes the next free number)
        self.assertEqual(len(data["cards"]), 6)   # 3 + 2 on the second page + 1 in the other set; the Japanese set isn't read
        self.assertEqual(data["cards"][0][:6], [1, 0, "Card 1", "1", "abcdef123456", "card-1"])
        self.assertFalse(any("japanese" in u for u, _ in self.calls))

    def test_write_and_keep_old(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "zh-cards.js")
            zh.OUT_FILE = path
            self.assertEqual(zh.main(["--force"]), 0)
            old = zh.read_old(path)
            self.assertEqual(len(old["cards"]), 6)
            # a later update keeps each set's id, and a set that turns up later gets one of its own
            before_ids = {g[0]: g[3] for g in old["groups"]}
            c = "pokemon-chinese-csv8c"
            real = zh.fetch

            def more(url, data=None, tries=3):
                if url.endswith("/category/pokemon-cards"):
                    return '<a href="/console/pokemon-chinese-brand-new">q</a><a href="/console/pokemon-chinese-gem-pack">z</a><a href="/console/%s">x</a>' % c
                if url.endswith("/console/pokemon-chinese-brand-new"):
                    return page("Pokemon Chinese Brand New Card Prices | x", [row(77, "pokemon-chinese-brand-new", "new-1", "New #1")])
                return real(url, data, tries)
            zh.fetch = more
            again = zh.build(old)
            self.assertEqual({g[0]: g[3] for g in again["groups"] if g[0] in before_ids}, before_ids)
            fresh = [g[3] for g in again["groups"] if g[0] == "pokemon-chinese-brand-new"]
            self.assertEqual(len(fresh), 1)
            self.assertNotIn(fresh[0], before_ids.values())
            zh.fetch = real
            # fresh enough: nothing is read again
            before = len(self.calls)
            self.assertEqual(zh.main([]), 0)
            self.assertEqual(len(self.calls), before)
            # a page that suddenly has a third of the cards isn't trusted: the old file stays
            zh.fetch = lambda url, data=None, tries=3: (
                '<a href="/console/pokemon-chinese-gem-pack">z</a>' if url.endswith("/category/pokemon-cards")
                else page("Pokemon Chinese Gem Pack Card Prices | x", [row(9, "pokemon-chinese-gem-pack", "pikachu-1", "Pikachu #1")]) if "/console/" in url
                else "Release Date: May 1, 2026")
            self.assertEqual(zh.main(["--force"]), 1)
            self.assertEqual(len(zh.read_old(path)["cards"]), 6)
            # PriceCharting down: the old file stays, and the run says so
            def down(url, data=None, tries=3):
                raise RuntimeError("down")
            zh.fetch = down
            self.assertEqual(zh.main(["--force"]), 1)
            self.assertEqual(len(zh.read_old(path)["cards"]), 6)
            # the file is plain data the website can read
            with open(path, encoding="utf-8") as f:
                text = f.read()
            self.assertTrue(text.startswith("window.ZH_DATA = {"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
