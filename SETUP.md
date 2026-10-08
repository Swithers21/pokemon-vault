# Pokémon Vault website: setup

Pokémon Vault as a website you can add to your iPhone's home screen, with your collection synced through
Google Drive and TCGplayer prices (English and Japanese cards) updated every evening by GitHub.

This is a separate app from any other "vault" you may have. It has its own repository, its own saved data and its own
Google Drive file, so the two never touch each other.

In this guide, `YOUR-USERNAME` is your GitHub username. The website's address will be
`https://YOUR-USERNAME.github.io/pokemon-vault/`.

## What lives where

- **This repository** (public): the website's code and this guide. Your collection is never in it.
- **Your devices**: your collection, saved in each browser (and in the home-screen app on your iPhone).
- **Your Google Drive**: `Pokemon Vault/Pokemon Vault backup.json`, which every device syncs with. Pokémon Vault can
  only see files it created itself in your Drive.
- **GitHub Actions**: every evening it downloads the day's TCGplayer prices (through TCGCSV) for English and Japanese
  Pokémon cards and publishes the website with them. It checks again overnight in case TCGCSV was late. An open
  Pokémon Vault picks up new prices by itself (within half an hour, or as soon as you switch back to it): nothing to
  reload or tap. It also looks at each grading company's public price page (`fee_watch.py`) so Pokémon Vault can warn
  you when a company's fees may have changed (see "Grading fees" below).

## 1. GitHub: the website

1. Sign in at [github.com](https://github.com) (or create a free account).
2. Click **+** (top right) > **New repository**. Name: `pokemon-vault`. Choose **Public** (free GitHub Pages
   websites need a public repository). Don't add a README. Click **Create repository**.
3. In the new repository: **Settings** > **Pages** > **Build and deployment** > **Source**: **GitHub Actions**.
4. Upload the files from the `pokemon-vault` folder: on the repository's main page, click
   **uploading an existing file**, drag in everything from the folder (including the `icons` folder), and click
   **Commit changes**.
5. Windows often hides the `.github` folder, so make the price-update file by hand: **Add file** >
   **Create new file**, name it `.github/workflows/daily-prices.yml`, paste in the contents of that file from
   the folder, and click **Commit changes**.
6. Open the **Actions** tab. "Daily Pokemon prices" starts by itself; the first run takes several minutes
   (it downloads every set's card list once; Pokémon has a few hundred English and Japanese sets). When it shows a
   green check, the website is live at `https://YOUR-USERNAME.github.io/pokemon-vault/`.

All GitHub Pages websites of one account share the address `YOUR-USERNAME.github.io`, so a page on one of them could
read another one's Google sign-in. Keep the GitHub account for your own sites only. (If you also run another vault
from the same account, that's fine: they're yours, and they save their data under different names.)

## 2. Google Cloud: signing in to Google Drive

**Already set up Google sign-in for another vault?** Skip to "Reuse an existing Google client" below.

1. Go to [console.cloud.google.com](https://console.cloud.google.com) and sign in with the Google account
   whose Drive you want to use.
2. Project picker (top left) > **New project**. Name: `Pokemon Vault`. **Create**, then select it.
3. **APIs & Services** > **Library**, search for **Google Drive API**, open it and click **Enable**.
4. **Google Auth Platform** (search for it at the top if you don't see it) > **Get started**:
   - App name: `Pokemon Vault`, user support email: yours. **Next**.
   - Audience: **External**. **Next**.
   - Contact information: your email. **Next**, agree, **Create**.
5. **Audience** > **Test users** > **Add users**: your Gmail address. **Save**. (Leave the app in
   "Testing": only the test users you add can sign in.)
6. **Data Access** > **Add or remove scopes**: tick
   `.../auth/drive.file` ("See, edit, create, and delete only the specific Google Drive files you use with
   this app"). **Update**, then **Save**.
7. **Clients** > **Create client**:
   - Application type: **Web application**. Name: `Pokemon Vault website`.
   - Authorized JavaScript origins: `https://YOUR-USERNAME.github.io`
   - Authorized redirect URIs: `https://YOUR-USERNAME.github.io/pokemon-vault/oauth.html`
   - **Create**. Copy the **Client ID** (it ends in `.apps.googleusercontent.com`). The client secret isn't
     used; don't share it.
8. On GitHub, open `config.js` in the repository, click the pencil (**Edit**), paste the Client ID between the
   quotes after `googleClientId:`, and click **Commit changes**. The website updates within a couple of
   minutes.

### Reuse an existing Google client

`config.js` already holds the Client ID of the Google client made for the Yu-Gi-Oh! Card Vault, so you only have to
tell Google about the new address:

1. [console.cloud.google.com](https://console.cloud.google.com) > pick the project you made for that vault >
   **Google Auth Platform** > **Clients** > open the client.
2. Under **Authorized redirect URIs**, **Add URI**: `https://YOUR-USERNAME.github.io/pokemon-vault/oauth.html`.
   (The **Authorized JavaScript origins** entry `https://YOUR-USERNAME.github.io` is already there.) **Save**.
3. Google can take a few minutes to start accepting it.

If you'd rather keep the two apps' sign-ins apart, make a new client as above instead and paste its ID into `config.js`.

When you sign in, Google shows **"Google hasn't verified this app"**. That's expected for your own
personal app: click **Continue**.

## 3. Start your collection

1. In Chrome or Edge, open `https://YOUR-USERNAME.github.io/pokemon-vault/`.
2. **Settings** > **Sync with Google Drive**, sign in, and allow access. Pokémon Vault saves your collection to
   your Google Drive.
3. Add cards: **Add card** and type the number printed at the bottom of the card (`025/198`, `SWSH123`, `TG05/TG30`),
   or import the CSV you exported from TCGplayer (**Import CSV**).
4. Optional: install it as an app. In Chrome: the install icon at the right of the address bar (or menu >
   **Cast, save and share** > **Install page as app**).

## 4. iPhone

1. Open `https://YOUR-USERNAME.github.io/pokemon-vault/` in **Safari**.
2. Tap **Share** > **Add to Home Screen** > **Add**.
3. Open Pokémon Vault from the home screen, then **Settings** > **Sync with Google Drive**, sign in, and choose
   **OK** when it offers to load your collection.
4. If you see "Still waiting for Google sign-in", tap **Sign in here**.

## Good to know

- **English and Japanese**: both come from TCGplayer (its "Pokemon" and "Pokemon Japan" lists). Each card is marked
  Japanese where it is, the Market and the Sets lists have an All / English / Japanese switch, and a card's language is
  filled in for you when you pick it. Korean and other languages aren't included.
- **Card numbers**: type the number from the card, like `025/198`, with or without the zeros. Promos and galleries work
  too (`SWSH123`, `SVP045`, `TG05/TG30`). If several sets share a number, Pokémon Vault lists them and you pick one.
- **Printings**: the finish TCGplayer prices separately: Normal, Holofoil, Reverse Holofoil, 1st Edition, Unlimited and
  so on. Pick yours when you add a card.
- **Google's sign-in lasts an hour, and Pokémon Vault renews it by itself.** When the hour has run out, Pokémon
  Vault goes to Google and straight back (it looks like a quick reload) the next time you open it or switch back
  to it, or when it has sat untouched for a few minutes. It never does this while you're in the middle of
  something (a card's details open, a search showing, a deck list not yet saved). This works as long as you're
  still signed in to Google in that browser or home-screen app. If Google wants you to sign in yourself (say you
  signed out of Google), Pokémon Vault shows "Sign in to Google Drive again": tap **Resume** (usually no typing).
  Until then, changes are kept on the device and sync afterwards. To turn the automatic part off:
  **Settings** > **Backup** > untick "Renew the Google Drive sign-in by itself".
- **No internet** (at a card shop, say): Pokémon Vault opens and works; changes sync when you're back online.
- **Syncing**: each device checks Google Drive every 15 seconds while Pokémon Vault is open, and before every
  save. If the same card is changed on two devices, the later change wins.
- **Camera scanning** works on the iPhone (Add card > Scan with camera; allow the camera). It reads the number at the
  bottom of the card, like `086/198`, and finds the card from it.
- **Scan to check**: Card search > **Scan to check** (or "Just checking a price?" in the normal scanner). Hold a card up
  and it shows what that card is worth, every printing's price, how it moved lately, and whether you already have it.
  Nothing is added unless you tap **Add**; **Want** puts it on your want list, and **Details** opens its price page.
  If the camera can't read the number, type it in or use a photo.
- **Add several cards**: Add card > Add several cards at once. One card per line: `086/198 x2`, `3 025/198`, or a name
  and number such as `Charizard 4/102`.
- **Sealed products**: Add card > **Add a sealed product** (booster boxes and packs, Elite Trainer Boxes, tins,
  collections). They're priced with TCGplayer's market price like cards, and listed under **Sealed products** in the
  Show menu.
- **PSA 10 value**: the switch under your collection's value shows what one gem-mint copy of each card would be worth,
  and cards you've had graded at their grade. Without more, it's a rough estimate from the raw price (Settings > Graded
  values). For real graded prices from eBay sales, add a PriceCharting key in Settings (it needs PriceCharting's
  Legendary plan). The key is saved with your Pokémon Vault data in your Google Drive.
- **Dated backups**: every day, the first save also keeps a dated copy in **Pokemon Vault > Backups** in your Google
  Drive (the last 30 days). Settings lists them; Restore puts one back on every device.
- **Card search** tab: what any card is worth. Type a name (or part of one), a card number or a set; more words narrow it
  (`charizard base`). Each card lists every printing with TCGplayer's market price, lowest listing and 30-day change,
  most valuable first. **Details** opens a card's price page: every printing, its price over time, a PSA 10 value, and
  buttons to add it or want it. Switch to **Sets** to find a set by name or code and see every card in it: card number,
  rarity, each printing's price, which you have, how many of its cards you have and what the rest would cost, its
  booster box price, with a filter by rarity and "Ones I don't have". It only uses data Pokémon Vault already has, so it
  works offline once the prices are loaded.
- **Market** tab: every set on TCGplayer with its 25 most valuable cards, and every sealed product (booster packs and
  boxes, bundles, Elite Trainer Boxes, tins, decks, collections…) with the cheapest TCGplayer listing next to the market
  price. Filter by language and by era (Scarlet & Violet, Sword & Shield, Sun & Moon…, Classic, Promos) and sort by
  biggest discount. Each product has one-tap searches at eBay, Amazon, Walmart and Target, sorted cheapest first. **Want**
  puts a card or sealed product on your want list.
- **Biggest movers** (Market tab, third button): the cards and sealed products whose TCGplayer price rose and fell the
  most, English and Japanese. Compare with the last update, 7 days or 30 days ago (those fill in as the daily updates
  stack up), rank by % or by dollars, leave out cheap ones (the default skips anything never worth $5) and show only the
  ones you have. Tap a card for its price page. Your own collection's gains and drops are in **Insights**.
- **Goals** (Sets tab): two kinds, both shown on the Sets tab and as slim rows on the Collection tab.
  - **Set goals**: pick a set to finish ("Add a set goal", or "Set as goal" on a set's page) and it shows how many
    cards you have, what the rest cost, and whether to count each card number once or every rarity.
  - **Pokémon goals**: "Add a Pokémon goal", then type a name (say Pikachu). It tracks every print of that Pokémon in
    every set, English and Japanese (ex, V and VMAX cards and tag teams included; Trainers, Energy and sealed products
    never are), with a progress bar, what the missing prints cost, and **See the prints** to browse the ones you're
    missing or have, newest set first. A switch picks English only, Japanese only or both. The picker suggests the
    Pokémon you collect most.
  - **Add all missing cards to my want list** is a button you press: nothing goes on the want list by itself, it skips
    cards already on it, and Undo takes them back off. Goals sync between your devices like the want list. On the
    Collection tab, tap a slim row to open its details and the Add all button, and tap "Goals" to fold the strip away.
- **Getting-started guide**: an empty collection shows a short guide (import a CSV, add by number, scan a card, sync to
  Google Drive, add it to your phone's home screen). It goes away on its own once you add a card, or tap **Hide this
  guide** (it can be shown again from the empty collection).
- **Want list** sections: cards, booster boxes, booster packs, and other sealed products (decks, tins, collections), each
  with its count and total, and a switch at the top to show just one. Add from the Market or Card search, or with **Add
  sealed** on the want list. **I got it** adds the item to your collection and takes it off the list.
- **Deck check**: paste a deck list (Pokémon TCG Live's **Export** text works as it is) to see which cards you already
  have, what the rest would cost at the cheapest TCGplayer prices, and whether the list follows the deck rules (60
  cards, no more than four copies of a card by name except Basic Energy, one ACE SPEC, one Radiant Pokémon). It doesn't
  check Standard or Expanded legality: TCGplayer's card list doesn't say which sets have rotated. It can put the cards
  you own for a deck into a location named after it ("Deck: Charizard ex").
- **Decks I can build** (in the Deck check tab): groups the Pokémon you own by type (Fire, Water, Psychic…), with the
  Trainers and Energy you already have, and shows the types you have enough Pokémon of for a deck idea. "Build a starter
  list" turns one into a 60-card list you can check and save. Types come from TCGplayer's card list.
- **Missing photos**: when TCGplayer has no photo of a printing (new sets, promos), Pokémon Vault shows the closest one it
  has, tagged "Similar photo" (the same card from another set). Anything left is drawn as a card or a box.
- **Trades & sales** tab: the trade checker adds up both sides of a trade at TCGplayer prices (cards from your collection
  against any TCGplayer printing, plus cash) and, when you complete it, moves the cards in and out. The sales log is next to it.
- **Insights** tab: price history, where your value is (by set, rarity, location), cards worth grading, and Tidy up
  (duplicates to merge, cards with no printing, price, location or TCGplayer link).
- **Get it graded** (in a card's details): links to start a submission at PSA, Beckett, CGC, SGC and TAG, the card's
  details to paste into their form, and tracking while it's away ("I sent it", then "It's back" with the grade).
- **Grading fees** (Settings): each company's price list (PSA, Beckett, CGC, SGC, TAG) is built in, as read on their
  sites on Oct 8, 2026 (`GRADING_FEE_TABLE` in `index.html`: level, fee, declared-value cap, business days, paused).
  Pick the service level you use and its fee fills in; until then each company's usual level is assumed (PSA Standard
  $59.99, Beckett Express $79.95, CGC Economy $20, SGC Standard $50, TAG Priority $149). A fee you type wins. Add
  shipping per card. Worth grading lets you pick the company to estimate with, each card's details show every
  company's cost and gain at a 10, and "I sent it" fills in that company's cost. Your choices sync to your other devices.
  **Fee watch**: every day the update also looks at each company's price page (`fee_watch.py`; it keeps only a
  fingerprint of the dollar amounts and turnaround times on the page) and publishes `fee-watch.json` with the website.
  If a page's prices change and stay changed on a later day, Settings, Worth grading and a card's grading section say
  "PSA's fees may have changed since Oct 8" with a link to their price list. Pokémon Vault never copies prices from those
  pages: it just tells you when to look. Pages it can't read are skipped. When the built-in list is updated (a newer
  checked date), the warning clears.
- **Price over time** (in a card's details): a chart of its TCGplayer market price. The daily update keeps every
  evening's prices (120 days, then monthly) and publishes them with the website, so the charts fill in day by day.
- **Share…** (select cards, or Show: Extras > Share trade binder, or the Want list tab) makes a link to a page with those
  cards, their photos and TCGplayer prices. The cards are in the link itself; nothing else of yours is shared.
- **Moving cards** between binders, boxes and decks: open a card and tap **Move** (next to where it's kept), or tick
  several cards and tap **Move…** in the bar at the bottom. Choose where they're going and how many of each.
- **Opened as a file** (without the website): double-click `index.html`, and run `python update_tcgplayer_data.py` in the
  folder (it needs Python 3) to download the prices next to it. Your collection is then saved in that browser only; the
  website is the better way to use it.

## If prices stop updating

1. On GitHub, open the repository's **Actions** tab and click **Daily Pokemon prices**.
2. If a run failed, open it to see why (TCGCSV being down for a day fixes itself). **Run workflow** runs it
   again by hand.
3. GitHub pauses scheduled workflows in repositories without new commits for 60 days. The workflow writes a
   one-line note twice a month to prevent that, but if GitHub shows "This scheduled workflow is disabled",
   click **Enable workflow**.
4. The fee watch is optional: if a grading company's page is down or can't be read, that company is skipped for the
   day and the website is published as usual.
5. Price comparisons (since the last update, 7 days, 30 days) are kept between runs in GitHub's cache. If the
   updates stopped for more than a week, they start over and fill in again day by day.

## Turning it off

- **Settings** > **Turn off** (under Backup and sync) stops syncing on that device; the file stays in your
  Google Drive.
- To remove Pokémon Vault's access to your Google account completely:
  [myaccount.google.com/connections](https://myaccount.google.com/connections) > the app's name > remove access.
  (If it shares a Google client with another vault, that removes both.)
