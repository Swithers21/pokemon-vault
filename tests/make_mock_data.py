"""A small made-up card list in the same format as the real daily one (tcgplayer-data.js), for the automatic checks.

It has a few English sets, a Japanese set, promos, sealed products and cards chosen to try the tricky cases:
the same card number in several sets, Pokemon that share part of a name, prices that look inflated, and so on.
Prices are invented. Run:  python tests/make_mock_data.py OUT_DIR
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

DATA_FORMAT = 5

GROUPS = [  # id, name, abbreviation, published, 1 for a Japanese set
    [9001, "SV: Scarlet & Violet 151", "MEW", "2023-09-22T00:00:00", 0],
    [9002, "SV01: Scarlet & Violet Base Set", "SVI", "2023-03-31T00:00:00", 0],
    [9003, "Base Set", "BS", "1999-01-09T00:00:00", 0],
    [9004, "SV2a: Pokemon Card 151", "SV2a", "2023-06-16T00:00:00", 1],
    [9005, "SVP Black Star Promos", "SVP", "2023-03-31T00:00:00", 0],
]
RARITIES = ["", "Common", "Uncommon", "Rare", "Holo Rare", "Double Rare", "Illustration Rare", "Special Illustration Rare", "Promo"]
SUBTYPES = ["Normal", "Holofoil", "Reverse Holofoil", "1st Edition", "1st Edition Holofoil", "Unlimited", "Unlimited Holofoil"]
CARD_TYPES = ["Lightning", "Fire", "Psychic", "Grass", "Water", "Trainer", "Energy", "Colorless"]
STAGES = ["Basic", "Stage 1", "Stage 2", "Basic ex"]

R = {n: i for i, n in enumerate(RARITIES)}
S = {n: i for i, n in enumerate(SUBTYPES)}
T = {n: i for i, n in enumerate(CARD_TYPES)}
G = {n: i for i, n in enumerate(STAGES)}

# (group index, name, number, rarity, card type, stage, [(printing, market, low, price a day ago, a week ago, a month ago)])
CARDS = [
    (0, "Bulbasaur", "001/165", "Common", "Grass", "Basic", [("Normal", 0.25, 0.10, 0.25, 0.25, 0.30), ("Reverse Holofoil", 0.40, 0.20, 0.40, 0.40, 0.40)]),
    (0, "Charizard ex", "006/165", "Double Rare", "Fire", "Basic ex", [("Holofoil", 8.50, 7.00, 8.50, 8.00, 7.50)]),
    (0, "Pikachu", "025/165", "Common", "Lightning", "Basic", [("Normal", 0.40, 0.20, 0.40, 0.40, 0.40), ("Reverse Holofoil", 0.50, 0.30, 0.50, 0.50, 0.50)]),
    (0, "Pikachu (Master Ball Pattern)", "025/165", "Common", "Lightning", "Basic", [("Reverse Holofoil", 12.00, 8.00, 12.00, 11.00, 9.00)]),
    (0, "Raichu", "026/165", "Rare", "Lightning", "Stage 1", [("Holofoil", 1.20, 0.90, 1.20, 1.20, 1.10)]),
    (0, "Mewtwo ex", "150/165", "Double Rare", "Psychic", "Basic ex", [("Holofoil", 6.00, 5.00, 6.00, 6.50, 7.00)]),
    (0, "Mew ex", "151/165", "Double Rare", "Psychic", "Basic ex", [("Holofoil", 4.00, 3.50, 4.00, 4.00, 4.20)]),
    (0, "Pikachu", "173/165", "Illustration Rare", "Lightning", "Basic", [("Holofoil", 14.00, 12.50, 14.00, 13.00, 12.00)]),
    (0, "Charizard ex", "199/165", "Special Illustration Rare", "Fire", "Basic ex", [("Holofoil", 95.00, 70.00, 90.00, 80.00, 70.00)]),
    (0, "Professor's Research", "190/165", "Uncommon", "Trainer", None, [("Normal", 0.20, 0.10, 0.20, 0.20, 0.20)]),
    (0, "Basic Lightning Energy", "257/165", "Common", "Energy", None, [("Normal", 0.05, 0.02, 0.05, 0.05, 0.05)]),
    (1, "Sprigatito", "013/198", "Common", "Grass", "Basic", [("Normal", 0.10, 0.05, 0.10, 0.10, 0.10)]),
    (1, "Pikachu", "063/198", "Common", "Lightning", "Basic", [("Normal", 0.30, 0.15, 0.30, 0.30, 0.30), ("Reverse Holofoil", 0.45, 0.30, 0.45, 0.45, 0.45)]),
    (1, "Pikachu ex", "063/198", "Double Rare", "Lightning", "Basic ex", [("Holofoil", 2.00, 1.50, 2.00, 2.00, 2.00)]),
    (1, "Detective Pikachu", "188/198", "Rare", "Lightning", "Basic", [("Holofoil", 3.00, 2.40, 3.00, 3.00, 3.00)]),
    (1, "Eevee", "133/198", "Common", "Colorless", "Basic", [("Normal", 0.30, 0.15, 0.30, 0.30, 0.30), ("Reverse Holofoil", 0.50, 0.30, 0.50, 0.50, 0.50)]),
    (1, "Mewtwo", "100/198", "Rare", "Psychic", "Basic", [("Holofoil", 1.50, 1.00, 1.50, 1.50, 1.50)]),
    # prices that look off: market far above the lowest listing, small amounts, market below the lowest, no listing, no market
    (1, "Shaky Sample ex", "120/198", "Double Rare", "Fire", "Basic ex", [("Holofoil", 120.00, 30.00, 118.00, 110.00, 100.00)]),
    (1, "Cheap Sample", "121/198", "Common", "Water", "Basic", [("Normal", 1.00, 0.20, 1.00, 1.00, 1.00)]),
    (1, "Mild Sample", "122/198", "Rare", "Water", "Basic", [("Holofoil", 10.00, 6.00, 10.00, 10.00, 10.00)]),
    (1, "Backwards Sample", "123/198", "Rare", "Water", "Basic", [("Holofoil", 5.00, 8.00, 5.00, 5.00, 5.00)]),
    (1, "No Listing Sample", "124/198", "Rare", "Water", "Basic", [("Holofoil", 3.00, None, 3.00, 3.00, 3.00)]),
    (1, "No Sales Sample", "125/198", "Rare", "Water", "Basic", [("Holofoil", None, 4.00, None, None, None)]),
    (1, "Mixed Sample", "126/198", "Rare", "Water", "Basic", [("Normal", 2.00, 1.50, 2.00, 2.00, 2.00), ("Holofoil", 60.00, 12.00, 55.00, 50.00, 40.00)]),
    (2, "Charizard", "004/102", "Holo Rare", "Fire", "Stage 2", [("1st Edition Holofoil", 400.00, 320.00, 400.00, 390.00, 380.00), ("Unlimited Holofoil", 150.00, 120.00, 150.00, 148.00, 140.00)]),
    (2, "Pikachu", "058/102", "Common", "Lightning", "Basic", [("1st Edition", 40.00, 30.00, 40.00, 40.00, 38.00), ("Unlimited", 4.00, 3.00, 4.00, 4.00, 4.00)]),
    (3, "Pikachu", "025/165", "Common", None, None, [("Normal", 0.35, 0.20, 0.35, 0.35, 0.35)]),
    (3, "Charizard ex", "006/165", "Double Rare", None, None, [("Holofoil", 5.00, 4.00, 5.00, 5.00, 5.00)]),
    (4, "Pikachu with Grey Felt Hat", "SVP085", "Promo", "Lightning", "Basic", [("Holofoil", 55.00, 30.00, 54.00, 52.00, 50.00)]),
]

# (group index, name, price market, low)
SEALED = [
    (0, "Scarlet & Violet 151 Elite Trainer Box", 60.00, 50.00),
    (0, "Scarlet & Violet 151 Booster Bundle", 25.00, 22.00),
]


def build(now=None):
    now = now or datetime.now(timezone.utc).replace(microsecond=0)
    today = now.date()
    products = []
    next_id = 5000

    def row(group, name, number, rarity, ctype, stage, prices, sealed=False):
        nonlocal next_id
        next_id += 1
        flat = []
        for printing, market, low, d1, d7, d30 in prices:
            flat.extend([S[printing], market, low, d1, d7, d30])
        extra = [1 if sealed else 0, 0, T[ctype] if ctype else -1, G[stage] if stage else -1]
        defaults = [0, 0, -1, -1]
        while extra and extra[-1] == defaults[len(extra) - 1]:
            extra.pop()
        out = [next_id, group, name, number, R[rarity or ""], flat]
        out.extend(extra)
        products.append(out)

    for group, name, number, rarity, ctype, stage, prices in CARDS:
        row(group, name, number, rarity, ctype, stage, prices)
    for group, name, market, low in SEALED:
        row(group, name, "", None, None, None, [("Normal", market, low, market, market, market)], sealed=True)
    return {
        "format": DATA_FORMAT,
        "source": "TCGCSV (TCGplayer) - made-up test data",
        "generated": now.isoformat(),
        "builtAt": now.isoformat(),
        "history": {"d1": (today - timedelta(days=1)).isoformat(), "d7": (today - timedelta(days=7)).isoformat(),
                    "d30": (today - timedelta(days=30)).isoformat()},
        "groups": GROUPS, "rarities": RARITIES, "subtypes": SUBTYPES, "cardTypes": CARD_TYPES, "stages": STAGES,
        "products": products,
    }


def write(out_dir, now=None):
    data = build(now)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "tcgplayer-data.js"), "w", encoding="ascii") as f:
        f.write("window.TCG_DATA = ")
        json.dump(data, f, ensure_ascii=True, separators=(",", ":"))
        f.write(";\n")
    with open(os.path.join(out_dir, "tcgplayer-data-version.js"), "w", encoding="ascii") as f:
        f.write("window.TCG_DATA_VERSION = ")
        json.dump({"generated": data["generated"], "builtAt": data["builtAt"]}, f, ensure_ascii=True, separators=(",", ":"))
        f.write(";\n")
    return data


if __name__ == "__main__":
    write(sys.argv[1] if len(sys.argv) > 1 else ".")
