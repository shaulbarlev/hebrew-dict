#!/bin/bash
#
# Builds a Hebrew <-> English dictionary and installs it into the macOS
# Dictionary app (~/Library/Dictionaries).
#
#   bash install-hebrew-english-dictionary.sh
#
# What it does:
#   1. downloads Apple's Dictionary Development Kit (GitHub mirror of the copy
#      shipped in Additional Tools for Xcode 14.1 - universal binary, no Xcode
#      and no Apple ID needed)
#   2. downloads the Hebrew Wiktionary extract from kaikki.org
#   3. converts it to Apple Dictionary XML (make_appledict.py, next to this file)
#   4. builds the .dictionary bundle and installs it
#
# Nothing outside ~/Library/Caches/heb-eng-dict and ~/Library/Dictionaries is
# touched. To uninstall: rm -rf ~/Library/Dictionaries/HebrewEnglish.dictionary
#
set -euo pipefail

WORK="$HOME/Library/Caches/heb-eng-dict"
DDK="$WORK/ddk"
SRC="$WORK/src"
DEST="$HOME/Library/Dictionaries"
DICT_NAME="HebrewEnglish"
DDK_RAW="https://raw.githubusercontent.com/nanoskript/dictionary-development-kit/main/bin"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GEN="$HERE/make_appledict.py"

say() { printf '\033[1m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- preflight
say "Checking prerequisites"
[ -f "$GEN" ] || die "make_appledict.py not found next to this script (looked in $HERE)"
for t in curl perl sed tr; do
  command -v "$t" >/dev/null || die "'$t' not found"
done
for t in /usr/bin/xmllint /usr/bin/xsltproc /usr/bin/plutil; do
  [ -x "$t" ] || die "$t not found (it normally ships with macOS)"
done
if ! python3 -c 'import sys; sys.exit(0)' >/dev/null 2>&1; then
  die "python3 is not usable. Install the command line tools first:  xcode-select --install"
fi
echo "    python3: $(python3 -V 2>&1)"

mkdir -p "$DDK/bin" "$SRC" "$DEST"

# ------------------------------------------------------- dictionary dev kit
DDK_FILES=(
  build_dict.sh generate_dict_template.sh
  extract_property.xsl
  make_line.pl make_body.pl extract_index.pl extract_referred_id.pl
  extract_front_matter_id.pl replace_entryid_bodyid.pl remove_duplicate_key.pl
  pick_referred_entry_id.pl make_readonly.pl
  make_dict_package add_body_record normalize_key_text add_supplementary_key
  build_key_index build_reference_index
)
SYSTEM_DDK="${DICT_DEV_KIT:-/Applications/Utilities/Dictionary Development Kit}"
if [ -x "$SYSTEM_DDK/bin/build_dict.sh" ]; then
  say "Using the Dictionary Development Kit already installed"
  DDK="$SYSTEM_DDK"
  echo "    $DDK"
else
  say "Fetching Apple's Dictionary Development Kit"
  for f in "${DDK_FILES[@]}"; do
    if [ ! -s "$DDK/bin/$f" ]; then
      curl -fsSL --retry 3 "$DDK_RAW/$f" -o "$DDK/bin/$f" \
        || die "could not download $f from the DDK mirror"
    fi
  done
  chmod +x "$DDK"/bin/*
  xattr -dr com.apple.quarantine "$DDK/bin" 2>/dev/null || true
  echo "    ${#DDK_FILES[@]} files in $DDK/bin"
fi

# --------------------------------------------------------------- source data
JSONL="$SRC/hebrew.jsonl"
if [ ! -s "$JSONL" ]; then
  say "Locating the Hebrew Wiktionary extract on kaikki.org"
  URL="https://kaikki.org/dictionary/Hebrew/kaikki.org-dictionary-Hebrew.jsonl"
  if ! curl -fsSLI "$URL" >/dev/null 2>&1; then
    URL=$(curl -fsSL "https://kaikki.org/dictionary/Hebrew/index.html" 2>/dev/null \
          | grep -oE 'href="[^"]*\.jsonl"' | head -1 | sed 's/^href="//;s/"$//') || true
    case "$URL" in
      "")      die "could not find a .jsonl download link on kaikki.org/dictionary/Hebrew/" ;;
      http*)   ;;
      /*)      URL="https://kaikki.org$URL" ;;
      *)       URL="https://kaikki.org/dictionary/Hebrew/$URL" ;;
    esac
  fi
  say "Downloading $URL"
  curl -fL --retry 3 --progress-bar "$URL" -o "$JSONL.part" || die "download failed"
  mv "$JSONL.part" "$JSONL"
else
  say "Using cached extract ($(du -h "$JSONL" | cut -f1)) - delete $JSONL to refresh"
fi

# ----------------------------------------------------------------- generate
say "Converting to Apple Dictionary XML"
BUILD="$WORK/build"
rm -rf "$BUILD"; mkdir -p "$BUILD"
python3 "$GEN" "$JSONL" "$BUILD"

say "Validating XML"
/usr/bin/xmllint --noout "$BUILD/HebrewEnglish.xml" || die "generated XML is not well formed"

# -------------------------------------------------------------------- build
say "Building the dictionary bundle (this takes a minute)"
cd "$BUILD"
"$DDK/bin/build_dict.sh" -v 10.11 "$DICT_NAME" \
  HebrewEnglish.xml HebrewEnglish.css HebrewEnglishInfo.plist

BUNDLE="$BUILD/objects/$DICT_NAME.dictionary"
[ -d "$BUNDLE" ] || die "build produced no bundle"

# ------------------------------------------------------------------ install
say "Installing into $DEST"
rm -rf "$DEST/$DICT_NAME.dictionary"
cp -R "$BUNDLE" "$DEST/"
touch "$DEST"

cat <<EOF

Done. $(du -sh "$DEST/$DICT_NAME.dictionary" | cut -f1) installed at
  $DEST/$DICT_NAME.dictionary

Last steps, in the Dictionary app:
  1. quit Dictionary completely (Cmd-Q) and reopen it
  2. Dictionary > Settings, tick "Hebrew – English (Wiktionary)"
  3. drag it up the list if you want it to win over the English dictionary

Then Look Up (Ctrl-Cmd-D, or three-finger tap) works on Hebrew and English
words anywhere in macOS. Words carrying ב/ה/ו/כ/ל/מ/ש prefixes are indexed
too, so בבית finds בית.

To remove it:  rm -rf "$DEST/$DICT_NAME.dictionary"
EOF
