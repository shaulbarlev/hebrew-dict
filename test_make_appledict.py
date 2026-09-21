#!/usr/bin/env python3
"""Self-check for the index-key and gloss logic:  python3 test_make_appledict.py"""

from make_appledict import english_keys, hebrew_index_keys

# Plain word: literal + niqqud-stripped primary, prefixed forms as extras.
primary, extra = hebrew_index_keys("בַּיִת")
assert primary == ["בַּיִת", "בית"], primary
assert "בבית" in extra and "ובבית" in extra and "שבבית" in extra, extra

# Punctuated forms (root, abbreviation) keep ONLY their literal key - stripping
# the maqaf/gershayim would collide them with בית and outrank the real word.
assert hebrew_index_keys("ב־י־ת") == (["ב־י־ת"], [])
assert hebrew_index_keys("בי״ת") == (["בי״ת"], [])

# Too short for prefixing (a one-letter stem plus prefix is noise).
assert hebrew_index_keys("אב")[1] == []

assert english_keys("house") == ["house"]
assert english_keys("to count") == ["to count", "count"]
assert english_keys("book (a written work); volume") == ["book"]
assert english_keys("the") == []
assert english_keys("a unit of a poem, written or printed as a paragraph") == []

print("ok")
