#!/bin/bash
#
# Installs the prebuilt Hebrew <-> English dictionary into the macOS Dictionary
# app. Downloads a ~6 MB bundle from this repo's latest GitHub release, so
# there is no build step: no python, no Dictionary Development Kit, and no
# 300 MB Wiktionary download.
#
#   bash install-prebuilt.sh
#
# To build it yourself from current Wiktionary data instead, use
# install-hebrew-english-dictionary.sh.
#
# Nothing outside ~/Library/Dictionaries is touched. To uninstall:
#   rm -rf ~/Library/Dictionaries/HebrewEnglish.dictionary
#
set -euo pipefail

DEST="$HOME/Library/Dictionaries"
DICT_NAME="HebrewEnglish"
BUNDLE_ID="org.wiktionary.dictionary.hebrew-english"
TARBALL="$DICT_NAME.dictionary.tar.gz"
URL="https://github.com/shaulbarlev/hebrew-dict/releases/latest/download/$TARBALL"

say() { printf '\033[1m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(uname -s)" = "Darwin" ] || die "this only works on macOS"
command -v curl >/dev/null || die "'curl' not found"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

say "Downloading the prebuilt dictionary"
curl -fL --retry 3 --progress-bar "$URL" -o "$TMP/$TARBALL" \
  || die "download failed. Check https://github.com/shaulbarlev/hebrew-dict/releases"

say "Unpacking"
tar -xzf "$TMP/$TARBALL" -C "$TMP" || die "the archive did not unpack"
[ -d "$TMP/$DICT_NAME.dictionary/Contents/Resources" ] \
  || die "the archive does not contain a $DICT_NAME.dictionary bundle"

say "Installing into $DEST"
mkdir -p "$DEST"
rm -rf "$DEST/$DICT_NAME.dictionary"
cp -R "$TMP/$DICT_NAME.dictionary" "$DEST/"
touch "$DEST"

# Saves a trip to Dictionary > Settings. Dictionary.app rewrites these prefs on
# quit, so it has to be closed first; -array-add appends without clobbering the
# dictionaries already enabled.
say "Enabling it for system-wide Look Up"
osascript -e 'tell application "Dictionary" to quit' >/dev/null 2>&1 || true
if defaults read com.apple.DictionaryServices DCSActiveDictionaries 2>/dev/null \
   | grep -q "$BUNDLE_ID"; then
  echo "    already enabled"
else
  defaults write com.apple.DictionaryServices DCSActiveDictionaries -array-add "$BUNDLE_ID"
  echo "    added to DCSActiveDictionaries"
fi
killall -HUP cfprefsd >/dev/null 2>&1 || true

cat <<EOF

Done. $(du -sh "$DEST/$DICT_NAME.dictionary" | cut -f1) installed and enabled at
  $DEST/$DICT_NAME.dictionary

Look Up (Ctrl-Cmd-D, or three-finger tap) now works on Hebrew and English words
anywhere in macOS. Words carrying the prefixes ב/ה/ו/כ/ל/מ/ש are indexed too,
so בבית finds בית.

The entries come from Wiktionary and carry its terms, CC BY-SA 3.0 / GFDL.

To remove it:  rm -rf "$DEST/$DICT_NAME.dictionary"
EOF
