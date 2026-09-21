# hebrew-dict

Build a Hebrew ⇄ English dictionary for the macOS **Dictionary.app**, from
Wiktionary data, with one command. No Xcode, no Apple ID, no Rosetta.

```bash
git clone https://github.com/shaulbarlev/hebrew-dict
cd hebrew-dict
bash install-hebrew-english-dictionary.sh
```

The script builds the bundle, installs it into `~/Library/Dictionaries`, and
enables it, so Look Up (⌃⌘D, or three-finger tap) works on Hebrew text right
away. You don't need to restart anything or open Settings.

Apple's own Hebrew dictionaries, if you have them, still win on words they
cover. To change that, drag Hebrew – English (Wiktionary) up the list in
Dictionary > Settings.

---

## Why this exists

macOS bundles bilingual dictionaries for a couple of dozen languages. Hebrew
isn't one of them, and it never has been. The Dictionary app is otherwise the
right place for this: it backs the system-wide Look Up gesture, so a dictionary
installed here works in Safari, Mail, Preview, Notes, and any other app that
uses standard text views — not just inside one dedicated app.

Third-party `.dictionary` bundles have existed for years, but the usual routes
have rotted:

- **DictUnifier**, the tool everyone's blog post points at, is long unmaintained
  and doesn't build on Apple Silicon.
- The **prebuilt Hebrew bundles** circulating since ~2013 are small, index only
  bare surface forms, and are hosted on links that keep dying.
- **PyGlossary** works well and is actively maintained, but its AppleDict writer
  still hands off to Apple's build kit, which the docs tell you to get by
  downloading a 3 GB *Additional Tools for Xcode* DMG behind an Apple ID login.

So this repo does the whole thing from scratch in two files, and fixes the one
defect that made the old bundles frustrating to actually use (see
[Hebrew prefixes](#hebrew-prefixes-the-part-that-matters)).

## How it works

```
kaikki.org Hebrew JSONL  ──►  make_appledict.py  ──►  HebrewEnglish.xml
                                                       HebrewEnglish.css
                                                       HebrewEnglishInfo.plist
                                                              │
   Apple Dictionary Development Kit (GitHub mirror)  ──►  build_dict.sh
                                                              │
                                                              ▼
                                       ~/Library/Dictionaries/HebrewEnglish.dictionary
```

Everything lands in `~/Library/Caches/heb-eng-dict/` (the downloaded data, the
build kit, the intermediate build) and `~/Library/Dictionaries/` (the result).
Nothing else on the system is touched.

### The build kit

A `.dictionary` bundle is not a text format. It's a compressed body blob
(`Body.data`) plus two custom binary trie indexes (`KeyText.index`,
`EntryID.index`). Apple's **Dictionary Development Kit** is the only practical
way to produce them; the format has been
[reverse-engineered for reading](https://josephg.com/blog/reverse-engineering-apple-dictionaries/),
but nobody has a maintained writer.

Apple distributes the kit inside the *Additional Tools for Xcode* disk image,
which needs a developer account. This repo fetches it instead from
[`nanoskript/dictionary-development-kit`](https://github.com/nanoskript/dictionary-development-kit),
a mirror of the copy shipped with Additional Tools for Xcode 14.1 — 18 files,
pulled individually over `raw.githubusercontent.com`.

Two things make this painless, and both were checked rather than assumed:

- **The binaries are universal.** Reading the fat Mach-O header of
  `make_dict_package` gives two architectures, cputype `16777223` (x86_64) and
  `16777228` (arm64). The older
  [Xcode 9 mirror](https://github.com/SebastianSzturo/Dictionary-Development-Kit)
  predates Apple Silicon and would need Rosetta; the 14.1 one doesn't.
- **`make` is not required.** The kit ships a sample Makefile, but reading
  `build_dict.sh` shows the Makefile only sets four variables and calls it. This
  repo calls `build_dict.sh` directly, which drops the Xcode Command Line Tools
  requirement. What's left — `xmllint`, `xsltproc`, `plutil`, `perl` — is all in
  the macOS base system. `python3` is the one genuine dependency.

Fetching with `curl` rather than a browser also means the binaries arrive
without the `com.apple.quarantine` xattr, so Gatekeeper never gets involved.

### The data

[kaikki.org](https://kaikki.org) publishes per-language JSONL extracts of
Wiktionary produced by [Wiktextract](https://github.com/tatuylonen/wiktextract).
The Hebrew extract gives, per entry: the headword (usually pointed), part of
speech, sense glosses, and often a romanization among its forms.

The installer resolves the download URL at runtime — it tries the canonical
filename and falls back to scraping the first `.jsonl` link off
`kaikki.org/dictionary/Hebrew/` — so a reorganisation upstream doesn't break it.
The extract is cached; re-runs don't re-download.

The September 2026 extract has 18,007 lines, which come out as 14,272 Hebrew
headwords, 14,362 English headwords, 28,634 entries, and about 21 MB installed.

Notably **not** usable here, each checked: FreeDict has no Hebrew pair, WikDict
covers 26 languages and Hebrew isn't among them, and the Wiktionary-derived
StarDict collections don't ship one either.

## Design decisions

### Hebrew prefixes, the part that matters

Hebrew glues its function words onto the front of the next word. *In the house*
is `בבית` — one token, and not the dictionary form `בית`. Dictionary.app matches
whatever text you selected against index keys, verbatim. So a dictionary that
only indexes lemmas misses most words as they actually occur in running text.
That's the flaw in every prebuilt Hebrew bundle I looked at, and the reason
their own README's warn you to select just the stem by hand.

The generator indexes each lemma under:

- the pointed form as Wiktionary has it,
- the **niqqud-stripped** form (running text is unpointed; dictionary entries
  aren't),
- and each of the inseparable prefixes **ב ה ו כ ל מ ש** plus the common stacks
  **וב וה ול ומ וש כש מה שב של שה לכש וכש**.

Cost is roughly 19× the index keys — the build takes a few minutes and the
bundle grows — which is a good trade for a dictionary that works on unedited
text.

Two bugs here only surfaced when querying the finished bundle.

The first: `d:priority="2"` hides a key rather than ranking it lower. Marking
the prefixed keys with it looks like the right design, since they should sit
below exact matches, but the build kit reads priority > 0 as "leave out of
lookup" and no prefixed form resolved at all. They are plain `d:index` entries
now.

The second was punctuation. Stripping maqaf and gershayim to build a lookup key
turns the root `ב־י־ת` and the letter name `בי״ת` both into `בית`, where they
outranked the actual noun, so `בבית` came back as "Beth, the second letter of
the Hebrew alphabet". Punctuated headwords now keep only their literal key.

This is morphologically naive: it strips prefixes off lemmas, it doesn't
conjugate or decline. Inflected verb forms mostly still miss. A real fix would
need an analyser like [HSpell](http://hspell.ivrix.org.il/), which is the
obvious next step for anyone who wants to take this further.

### English → Hebrew

The extract is Hebrew-headword-only, so the reverse direction is derived by
inverting glosses: a gloss is used as an English headword when it survives
stripping parentheticals and bracketed notes and is at most three words of plain
lowercase text. Verb glosses are indexed both with and without the leading
`to `. Each English term lists up to 40 Hebrew words, each with its romanization
and the gloss it came from, so you can see *why* a word was matched.

This is coarser than a purpose-built English→Hebrew dictionary — it inherits
Wiktionary's gloss phrasing, and rare senses can crowd common ones. It is,
however, free, and it covers the direction people actually need when writing.

### Presentation

RTL is handled with `direction: rtl; unicode-bidi: isolate` on Hebrew runs, so
mixed Hebrew/English lines don't scramble. Romanizations are set in italic grey,
parts of speech in small caps, and the stylesheet carries a
`prefers-color-scheme: dark` block.

## Repo layout

| File | What it is |
|---|---|
| `install-hebrew-english-dictionary.sh` | The pipeline: preflight, fetch kit, fetch data, generate, build, install. |
| `make_appledict.py` | JSONL → AppleDict XML + CSS + Info.plist. Standard library only. |
| `test_make_appledict.py` | Self-check for the index-key and gloss logic. `python3 test_make_appledict.py`. |
| `BRIEF-hebrew-dictionary.md` | Handoff brief written for a coding agent, kept because it doubles as a debugging runbook. |

## Requirements

macOS, `python3` (`xcode-select --install` if it's the stub), and a network
connection. Roughly 1 GB free while building.

## Troubleshooting

**`could not find a .jsonl download link`** — kaikki reorganised. Grab the real
URL from `https://kaikki.org/dictionary/Hebrew/`, save it to
`~/Library/Caches/heb-eng-dict/src/hebrew.jsonl`, re-run.

**Built fine but nothing shows up** — quit Dictionary.app completely (⌘Q, not
just closing the window) and reopen. The app reads `~/Library/Dictionaries` at
launch.

**Hebrew renders left-to-right** — `DefaultStyle.css` didn't make it into the
bundle; check `Contents/Resources/` inside `HebrewEnglish.dictionary`.

**The build seems stuck** — index building is the slow phase, and the prefix
keys make it slower. Give it a few minutes.

## Uninstall

```bash
rm -rf ~/Library/Dictionaries/HebrewEnglish.dictionary
rm -rf ~/Library/Caches/heb-eng-dict
```

## Licensing

The scripts in this repo are MIT (see `LICENSE`).

The **dictionary they generate is not**: it is derived from Wiktionary and
carries Wiktionary's terms — dual-licensed **CC BY-SA 3.0** and **GFDL**. If you
redistribute a built bundle rather than the build script, you're redistributing
Wiktionary content and those terms apply, attribution included. The generated
`Info.plist` states this.

The Dictionary Development Kit is © 1997–2022 Apple Inc. This repo doesn't
vendor it; the installer downloads it at build time from a third-party mirror.
If you'd rather get it from Apple directly, it's in the *Additional Tools for
Xcode* disk image on the developer downloads site, and the installer will use a
copy already present at
`/Applications/Utilities/Dictionary Development Kit` if you point it there.

## Sources

- [Dictionary Development Kit mirror (Xcode 14.1)](https://github.com/nanoskript/dictionary-development-kit) — the build kit this uses
- [Dictionary Development Kit mirror (Xcode 9)](https://github.com/SebastianSzturo/Dictionary-Development-Kit) — older, x86_64 only
- [Apple, *Dictionary Services Programming Guide*](https://developer.apple.com/library/archive/documentation/UserExperience/Conceptual/DictionaryServicesProgGuide/Introduction/Introduction.html) — the XML schema, `d:index`, `d:priority`
- [kaikki.org](https://kaikki.org) — machine-readable Wiktionary extracts
- [Wiktextract](https://github.com/tatuylonen/wiktextract) — the extractor behind them
- [PyGlossary AppleDict notes](https://github.com/ilius/pyglossary/blob/master/doc/apple.md) — the conventional conversion route
- [Reverse-engineering Apple Dictionary](https://josephg.com/blog/reverse-engineering-apple-dictionaries/) — how the binary format is laid out
- [Adding a Hebrew dictionary to OS X (2013)](https://blog.jle.vi/post/72464439746/get-the-look-up-dictionary-feature-in-os-x-to) — the prebuilt bundles this replaces
- [HSpell](http://hspell.ivrix.org.il/) — Hebrew morphological analyser, for anyone improving the prefix handling
