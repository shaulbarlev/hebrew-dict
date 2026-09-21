# Brief for Claude Code: install a Hebrew–English dictionary into Dictionary.app

**Goal:** a working Hebrew ⇄ English dictionary inside the macOS Dictionary app, so
Look Up (⌃⌘D / three-finger tap) resolves Hebrew words system-wide.

**Why you and not Cowork:** macOS only grants the cloud session *click* access to
Terminal — it cannot type commands. You have a real shell, so you can finish this.

Two files sit next to this brief in `~/Dump/hebrew-dict/`:

- `install-hebrew-english-dictionary.sh` — the whole pipeline
- `make_appledict.py` — kaikki JSONL → Apple Dictionary XML (stdlib only)

---

## The one command

```bash
cd ~/Dump/hebrew-dict && bash install-hebrew-english-dictionary.sh
```

Run it, watch for errors, fix what breaks, then verify. Everything below is
context so you can debug without re-deriving it.

---

## What's already been verified (don't re-research)

- **No Xcode, no Apple ID, no Rosetta.** Apple's Dictionary Development Kit is
  mirrored at `github.com/nanoskript/dictionary-development-kit` (the copy from
  Additional Tools for Xcode 14.1). Its Mach-O binaries are **universal** —
  checked the fat header: cputype `16777223` (x86_64) + `16777228` (arm64).
- **`make` is not needed.** The script calls `bin/build_dict.sh` directly. The
  only other tools it needs — `xmllint`, `xsltproc`, `plutil`, `perl` — ship
  with macOS. `python3` is the one real dependency; if it's the CLT stub, run
  `xcode-select --install` first.
- **18 DDK files** are fetched individually over `raw.githubusercontent.com`
  (no `git clone`, so no CLT requirement) into `~/Library/Caches/heb-eng-dict/ddk/bin`
  and `chmod +x`'d. curl downloads carry no quarantine xattr, so Gatekeeper
  stays quiet.
- **Source data:** the Hebrew Wiktextract extract from
  `kaikki.org/dictionary/Hebrew/`. The script tries the canonical
  `kaikki.org-dictionary-Hebrew.jsonl` and falls back to scraping the first
  `.jsonl` href off the index page. It's cached, so re-runs don't re-download.
- **Build invocation:** `build_dict.sh -v 10.11 HebrewEnglish <xml> <css> <plist>`.
  `-v 10.11` puts the payload under `Contents/Resources` (correct for modern
  macOS) and turns on trie + body compression.
- **Install path:** `~/Library/Dictionaries/HebrewEnglish.dictionary`.
  Uninstall is `rm -rf` on that one path.

## What `make_appledict.py` produces

- **Hebrew → English:** one entry per headword, senses grouped by part of
  speech, romanization when Wiktionary has it.
- **English → Hebrew:** built by inverting the short glosses (≤3 words, after
  stripping parentheticals), capped at 40 Hebrew words per English term.
- **Prefix indexing — the important bit.** Every lemma is also indexed under
  its ב/ה/ו/כ/ל/מ/ש forms and the common stacks (וב, וה, ול, ומ, וש, כש, מה,
  שב, של, שה, לכש, וכש), plus a niqqud-stripped key. Those extra keys carry
  `d:priority="2"` so they rank below exact matches. This is what makes
  `בבית` resolve to `בַּיִת` — the prebuilt bundles floating around the web
  don't do it, and it's the main reason they feel broken.
- RTL CSS with `unicode-bidi: isolate` on Hebrew runs, light and dark mode.

The generator was tested against synthetic kaikki-shaped records and its XML
passes `xmllint`. The build and install steps have **not** been run on this
machine — that's your job.

---

## If it breaks

| Symptom | Likely cause / fix |
|---|---|
| `could not find a .jsonl download link` | kaikki reorganised. Open `https://kaikki.org/dictionary/Hebrew/`, find the real JSONL URL, `curl` it to `~/Library/Caches/heb-eng-dict/src/hebrew.jsonl`, re-run. |
| `python3 is not usable` | `xcode-select --install`, then re-run. |
| `xmllint` fails on the generated XML | A gloss contains something the escaper missed. Find the offending line number and fix `x()` in `make_appledict.py`. |
| `build_dict.sh` dies in "Extracting index data" | Usually a malformed `d:index`. Check for empty `d:value`. |
| Build succeeds, dictionary doesn't appear | Quit Dictionary.app fully (⌘Q, not just the window), reopen, check Settings. Also `killall -HUP Dictionary` and re-check. |
| Entries appear but Hebrew renders LTR | `DefaultStyle.css` didn't get copied — check `Contents/Resources/DefaultStyle.css` inside the bundle. |
| Build is very slow | Expected: the prefix keys multiply the index ~19×. A few minutes is normal. |

## Verification before you report back

1. `ls -la ~/Library/Dictionaries/HebrewEnglish.dictionary` and `du -sh` it.
2. Confirm `Contents/Resources/` holds `Body.data`, `KeyText.index`,
   `EntryID.index`, `DefaultStyle.css`.
3. Quit and reopen Dictionary.app, enable **Hebrew – English (Wiktionary)** in
   Settings, drag it up the list.
4. Look up, and report what each returns:
   - `בית` — should hit the entry directly
   - `בבית` — should hit the **same** entry via the prefix index
   - `ספר`
   - `house` — should list Hebrew equivalents
5. Report the headword counts the script printed (Hebrew headwords, English
   headwords, total entries).

If anything in the pipeline needed changing, say what you changed and why — the
scripts are drafts, not gospel.

---

## Build results (2026-09-21, run on this Mac)

Installed and working: 21 MB at `~/Library/Dictionaries/HebrewEnglish.dictionary`.
18,007 source lines → 14,272 Hebrew headwords, 14,362 English, 28,634 entries.

Two fixes were needed in `make_appledict.py`:

1. **`d:priority="2"` hid every prefixed key.** The DDK treats priority > 0 as
   "not returned by lookup", not "ranked lower" — so `בבית` resolved to nothing
   at all. Dropped the attribute; prefixed forms are plain indexes now.
2. **Punctuated headwords collided with real words.** `PUNCT_RE` strips maqaf
   and gershayim, so the root `ב־י־ת` and the letter name `בי״ת` both reduced to
   the key `בית` and outranked the actual noun — `בבית` returned "Beth, the
   second letter". Those forms now keep only their literal key.

Verified via `DCSCopyTextDefinition` against the installed bundle: `בית`,
`בבית`, `ובבית`, `שבבית` all hit בַּיִת; `ספר` and `מהספר` hit סֵפֶר; `house`
and `book` list the Hebrew equivalents. `test_make_appledict.py` covers the
key-generation logic.

The dictionary was also added to `DCSActiveDictionaries` in
`com.apple.DictionaryServices`, so Look Up works without visiting Settings.
Apple's own `he.oup` / `he-en.oup` were already active and rank above it.
