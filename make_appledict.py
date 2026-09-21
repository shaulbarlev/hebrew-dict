#!/usr/bin/env python3
"""
Build Apple Dictionary (.dictionary) source files for a Hebrew <-> English
dictionary from a kaikki.org / Wiktextract JSONL extract of Hebrew.

Stdlib only. Reads the JSONL path as argv[1], writes into argv[2] (a directory):
    HebrewEnglish.xml
    HebrewEnglish.css
    HebrewEnglishInfo.plist
"""

import html
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict

# --- Hebrew helpers ---------------------------------------------------------

# Niqqud, cantillation, meteg etc.  U+0591..U+05C7 minus the letters themselves.
NIQQUD_RE = re.compile(r"[֑-ֽֿ-ׇ]")
HEB_LETTER_RE = re.compile(r"[א-ת]")
PUNCT_RE = re.compile(r"[־׀׃׳״\"'’]")

# Inseparable prefixes ("otiyot ha-shimush") and the most common stacks.
PREFIXES = [
    "ב",  # be-
    "ה",  # ha-
    "ו",  # ve-
    "כ",  # ke-
    "ל",  # le-
    "מ",  # mi-
    "ש",  # she-
    "וב", "וה", "ול", "ומ", "וש",
    "כש", "מה", "שב", "של", "שה",
    "וכש", "לכש",
]


def strip_niqqud(s: str) -> str:
    return NIQQUD_RE.sub("", unicodedata.normalize("NFC", s))


def is_hebrew(s: str) -> bool:
    return bool(HEB_LETTER_RE.search(s))


def x(s: str) -> str:
    """XML-escape text."""
    return html.escape(s, quote=True)


# --- English gloss -> headword extraction -----------------------------------

PAREN_RE = re.compile(r"\([^)]*\)")
BRACKET_RE = re.compile(r"\[[^\]]*\]")
OK_EN_RE = re.compile(r"^[a-z][a-z'\- ]{0,28}$")

STOP_GLOSSES = {
    "", "of", "the", "a", "an", "to", "and", "or", "used", "see", "obsolete",
}


def english_keys(gloss: str):
    """Turn one English gloss into 0-2 lookup headwords."""
    g = BRACKET_RE.sub("", PAREN_RE.sub("", gloss)).strip()
    g = g.split(";")[0].split(",")[0].strip().strip(".").strip()
    g = re.sub(r"\s+", " ", g).lower()
    if not g or g in STOP_GLOSSES:
        return []
    if len(g.split()) > 3 or not OK_EN_RE.match(g):
        return []
    keys = [g]
    if g.startswith("to ") and len(g) > 3:
        keys.append(g[3:])
    return keys


# --- Parse -----------------------------------------------------------------

def load(path):
    """word -> list of {pos, glosses, roman}"""
    entries = defaultdict(list)
    n = 0
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except ValueError:
                continue
            word = o.get("word")
            if not word or not is_hebrew(word):
                continue
            pos = o.get("pos") or ""
            glosses = []
            for sense in o.get("senses", []):
                gl = sense.get("glosses") or sense.get("raw_glosses") or []
                for g in gl:
                    g = g.strip()
                    if g and g not in glosses:
                        glosses.append(g)
            if not glosses:
                continue
            roman = ""
            for f in o.get("forms", []) or []:
                tags = f.get("tags") or []
                if "romanization" in tags or "transliteration" in tags:
                    roman = f.get("form", "")
                    break
            entries[word].append({"pos": pos, "glosses": glosses, "roman": roman})
            n += 1
    return entries, n


# --- Emit -------------------------------------------------------------------

HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<d:dictionary xmlns="http://www.w3.org/1999/xhtml" '
    'xmlns:d="http://www.apple.com/DTDs/DictionaryService-1.0.rng">\n'
)
FOOTER = "</d:dictionary>\n"


def hebrew_index_keys(word):
    """Primary key first, then prefixed variants.

    Roots ("ב־י־ת") and abbreviations ("בי״ת") keep only their literal key:
    stripping the maqaf/gershayim would collide them with the plain word
    (בית) and let them outrank it in lookups.
    """
    if PUNCT_RE.search(word):
        return [word], []
    plain = strip_niqqud(word)
    plain = PUNCT_RE.sub("", plain).strip()
    primary = []
    for k in (word, plain):
        if k and k not in primary:
            primary.append(k)
    extra = []
    if len(plain) >= 3:
        for p in PREFIXES:
            extra.append(p + plain)
    return primary, extra


def write_xml(entries, out_path):
    eng_map = defaultdict(list)          # english headword -> [(heb, roman, gloss)]
    n_entries = 0

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(HEADER)

        # ---- Hebrew -> English
        for i, (word, groups) in enumerate(sorted(entries.items()), 1):
            eid = "h%d" % i
            title = strip_niqqud(word) or word
            primary, extra = hebrew_index_keys(word)

            parts = ['<d:entry id="%s" d:title="%s">' % (eid, x(title))]
            for k in primary:
                parts.append('<d:index d:value="%s" d:title="%s"/>' % (x(k), x(title)))
            # No d:priority here: the DDK treats priority>0 as "hidden from
            # search", so prefixed forms would never resolve at all.
            for k in extra:
                parts.append('<d:index d:value="%s" d:title="%s"/>' % (x(k), x(title)))

            roman = next((g["roman"] for g in groups if g["roman"]), "")
            parts.append('<div class="he">')
            parts.append('<h1 class="hw">%s</h1>' % x(word))
            if roman:
                parts.append('<span class="tr">%s</span>' % x(roman))
            for g in groups:
                if g["pos"]:
                    parts.append('<div class="pos">%s</div>' % x(g["pos"]))
                parts.append("<ol>")
                for gl in g["glosses"][:12]:
                    parts.append("<li>%s</li>" % x(gl))
                    for k in english_keys(gl):
                        if len(eng_map[k]) < 40:
                            eng_map[k].append((title, roman, gl))
                parts.append("</ol>")
            parts.append("</div></d:entry>\n")
            fh.write("".join(parts))
            n_entries += 1

        # ---- English -> Hebrew
        for j, (term, hits) in enumerate(sorted(eng_map.items()), 1):
            eid = "e%d" % j
            parts = ['<d:entry id="%s" d:title="%s">' % (eid, x(term))]
            parts.append('<d:index d:value="%s" d:title="%s"/>' % (x(term), x(term)))
            parts.append('<div class="en">')
            parts.append('<h1 class="hw-en">%s</h1>' % x(term))
            parts.append('<div class="pos">Hebrew</div><ul>')
            seen = set()
            for heb, roman, gl in hits:
                if heb in seen:
                    continue
                seen.add(heb)
                bit = '<li><span class="he-inline">%s</span>' % x(heb)
                if roman:
                    bit += ' <span class="tr">%s</span>' % x(roman)
                bit += ' <span class="note">%s</span></li>' % x(gl)
                parts.append(bit)
            parts.append("</ul></div></d:entry>\n")
            fh.write("".join(parts))
            n_entries += 1

        fh.write(FOOTER)

    return n_entries, len(eng_map)


CSS = """@charset "UTF-8";

d|entry { font-family: -apple-system, "SF Pro Text", sans-serif; line-height: 1.45; }

h1.hw {
  font-size: 1.55em;
  font-weight: 600;
  margin: 0 0 .15em 0;
  direction: rtl;
  unicode-bidi: isolate;
}
h1.hw-en { font-size: 1.4em; font-weight: 600; margin: 0 0 .15em 0; }

span.tr { color: #8a8a8e; font-style: italic; margin-inline-start: .35em; }

div.pos {
  font-variant: small-caps;
  letter-spacing: .04em;
  color: #8a8a8e;
  margin: .55em 0 .2em 0;
}

ol, ul { margin: .2em 0 .2em 1.25em; padding: 0; }
li { margin: .12em 0; }

span.he-inline {
  direction: rtl;
  unicode-bidi: isolate;
  font-size: 1.15em;
}
span.note { color: #8a8a8e; }

@media (prefers-color-scheme: dark) {
  span.tr, div.pos, span.note { color: #9b9ba0; }
}
"""

PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
\t<key>CFBundleDevelopmentRegion</key>
\t<string>English</string>
\t<key>CFBundleIdentifier</key>
\t<string>org.wiktionary.dictionary.hebrew-english</string>
\t<key>CFBundleDisplayName</key>
\t<string>Hebrew – English (Wiktionary)</string>
\t<key>CFBundleName</key>
\t<string>HebrewEnglish</string>
\t<key>CFBundleShortVersionString</key>
\t<string>1.0</string>
\t<key>DCSDictionaryCopyright</key>
\t<string>Wiktionary, CC BY-SA 3.0 / GFDL. Extracted via kaikki.org (Wiktextract).</string>
\t<key>DCSDictionaryManufacturerName</key>
\t<string>Wiktionary contributors</string>
\t<key>DCSDictionaryFrontMatterReferenceID</key>
\t<string>front_back_matter</string>
\t<key>DCSDictionaryPrefsHTML</key>
\t<string>HebrewEnglish_prefs.html</string>
\t<key>DCSDictionaryXSL</key>
\t<string>HebrewEnglish.xsl</string>
</dict>
</plist>
"""

# The optional keys above point at files we do not ship; drop them.
PLIST = "\n".join(
    l for l in PLIST.splitlines()
    if "FrontMatter" not in l and "PrefsHTML" not in l and "DictionaryXSL" not in l
    and "front_back_matter" not in l and "_prefs.html" not in l and "HebrewEnglish.xsl" not in l
) + "\n"


def main():
    if len(sys.argv) < 3:
        sys.exit("usage: make_appledict.py <kaikki.jsonl> <outdir>")
    src, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)

    entries, n_lines = load(src)
    if not entries:
        sys.exit("error: no Hebrew entries parsed from %s" % src)

    n_entries, n_eng = write_xml(entries, os.path.join(outdir, "HebrewEnglish.xml"))

    with open(os.path.join(outdir, "HebrewEnglish.css"), "w", encoding="utf-8") as fh:
        fh.write(CSS)
    with open(os.path.join(outdir, "HebrewEnglishInfo.plist"), "w", encoding="utf-8") as fh:
        fh.write(PLIST)

    print("  source lines parsed : %d" % n_lines)
    print("  Hebrew headwords    : %d" % len(entries))
    print("  English headwords   : %d" % n_eng)
    print("  total entries       : %d" % n_entries)


if __name__ == "__main__":
    main()
