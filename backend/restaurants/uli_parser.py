"""
ULI — Universal Layout Intelligence
MRK | Pie AI

Spatial pattern recognition for menu parsing.
Reads menus the way a human eye does:
  1. Find price anchors
  2. Map spatial relationships around anchors
  3. Detect typography signals (caps, bold, indent)
  4. Lock in repeating patterns

This runs BEFORE Claude Vision.
Claude Vision is the fallback for files ULI can't confidently read.
"""

import re
import os
import json
from dataclasses import dataclass, field
from typing import List, Optional


# ================================================================
# DATA STRUCTURES
# ================================================================

@dataclass
class MenuLine:
    """A single line of text from a menu with its properties."""
    raw:        str
    text:       str   = ""      # cleaned text
    price:      str   = ""      # extracted price if found
    is_caps:    bool  = False   # ALL CAPS
    is_indented:bool  = False   # starts with whitespace
    indent_lvl: int   = 0       # how many spaces/tabs indented
    has_dots:   bool  = False   # has dot leader (......)
    has_dash:   bool  = False   # has dash leader (-----)
    is_short:   bool  = False   # under 30 chars (likely header or name)
    is_long:    bool  = False   # over 80 chars (likely description)


@dataclass
class ParsedItem:
    """A fully parsed menu item."""
    name:        str
    category:    str  = "Unknown"
    price:       str  = ""
    description: str  = ""
    allergens:   str  = ""
    notes:       str  = ""
    confidence:  float = 0.0    # 0.0 - 1.0 how confident ULI is


@dataclass
class PatternSignature:
    """
    Locked-in pattern for a menu section.
    Once ULI sees Name→dots→price repeat 2+ times,
    it locks this pattern and applies it to the rest of the section.
    """
    has_dot_leader:  bool = False
    has_dash_leader: bool = False
    price_on_right:  bool = True
    description_below: bool = True
    confirmed:       bool = False
    seen_count:      int  = 0


# ================================================================
# PRICE ANCHOR
# The most reliable signal on any menu
# ================================================================

PRICE_PATTERN = re.compile(
    r"""
    (?:
        \$\s*\d{1,3}(?:[.,]\d{2})?   # $12.99 or $12
        |
        \d{1,3}\.\d{2}               # 12.99
        |
        \d{1,2}\s*$                  # bare number at end of line: "15"
    )
    """,
    re.VERBOSE
)

def extract_price(text):
    """
    Find and extract price from a line.
    Returns (clean_name, price_str) or (text, "")
    """
    # Try dollar sign first
    match = re.search(r'\$\s*(\d{1,3}(?:[.,]\d{2})?)', text)
    if match:
        price    = match.group(1).replace(",", ".")
        clean    = text[:match.start()].strip(" .-·")
        return clean, price

    # Try decimal number
    match = re.search(r'(\d{1,3}\.\d{2})', text)
    if match:
        price = match.group(1)
        clean = text[:match.start()].strip(" .-·")
        return clean, price

    # Try bare integer at end of line (e.g. "Chicken Burrito  15")
    match = re.search(r'\s+(\d{1,2})\s*$', text)
    if match:
        price = match.group(1)
        clean = text[:match.start()].strip()
        return clean, price

    return text.strip(), ""


# ================================================================
# LINE ANALYZER
# Classifies each line before pattern detection
# ================================================================

DOT_LEADER  = re.compile(r'\.{3,}')
DASH_LEADER = re.compile(r'-{3,}')

def analyze_line(raw_line) -> MenuLine:
    """
    Takes a raw text line and extracts all its properties.
    """
    line = MenuLine(raw=raw_line)

    # Indent detection
    stripped = raw_line.lstrip()
    indent   = len(raw_line) - len(stripped)
    line.indent_lvl  = indent
    line.is_indented = indent >= 2

    # Clean separators before analysis
    text = stripped
    line.has_dots = bool(DOT_LEADER.search(text))
    line.has_dash = bool(DASH_LEADER.search(text))

    # Remove dot/dash leaders for clean text
    text = DOT_LEADER.sub(' ', text)
    text = DASH_LEADER.sub(' ', text)
    text = text.strip()

    # Price extraction
    clean_text, price = extract_price(text)
    line.text  = clean_text.strip()
    line.price = price

    # Typography signals
    line.is_caps  = bool(line.text) and line.text == line.text.upper() and any(c.isalpha() for c in line.text)
    line.is_short = len(line.text) < 35
    line.is_long  = len(line.text) > 80

    return line


# ================================================================
# CATEGORY DETECTOR
# Combines spatial + typography signals
# ================================================================

KNOWN_CATEGORIES = {
    "appetizer", "appetizers", "starter", "starters",
    "entree", "entrees", "main", "mains", "dinner", "dinners",
    "lunch", "breakfast", "brunch",
    "soup", "soups", "salad", "salads",
    "sandwich", "sandwiches", "sammie", "sammies",
    "burger", "burgers",
    "wrap", "wraps",
    "pizza", "pasta",
    "taco", "tacos", "burrito", "burritos",
    "enchilada", "enchiladas", "fajita", "fajitas",
    "chimichanga", "chimichangas",
    "side", "sides", "extra", "extras",
    "dessert", "desserts", "sweet", "sweets",
    "drink", "drinks", "beverage", "beverages",
    "beer", "wine", "cocktail", "cocktails", "spirits",
    "snack", "snacks",
    "kids", "children",
    "special", "specials", "feature", "features",
    "seafood", "steak", "grill", "bbq",
}

def is_category(line: MenuLine) -> bool:
    """
    A line is a category header if:
    - It has no price AND
    - It is ALL CAPS or matches a known keyword AND
    - It is short
    """
    if line.price:
        return False

    if not line.text or len(line.text) < 2:
        return False

    lower = line.text.lower().strip()

    # Known category keyword match
    for kw in KNOWN_CATEGORIES:
        if lower == kw or lower.startswith(kw + " ") or lower.endswith(" " + kw):
            return True

    # ALL CAPS + short + no digits = strong category signal
    if line.is_caps and line.is_short and not any(c.isdigit() for c in line.text):
        return True

    return False


def is_description(line: MenuLine, prev_had_price: bool) -> bool:
    """
    A line is a description if:
    - It has no price AND
    - It is indented OR long OR follows a priced item
    - It is not a category
    """
    if line.price:
        return False
    if is_category(line):
        return False
    if line.is_indented and not line.is_caps:
        return True
    if prev_had_price and not line.is_caps and len(line.text) > 10:
        return True
    if line.is_long:
        return True
    return False


# ================================================================
# PATTERN LOCK
# After seeing Name→price 2+ times, lock in the pattern
# ================================================================

def update_pattern(sig: PatternSignature, line: MenuLine):
    """Update the pattern signature based on what we see."""
    if line.has_dots:
        sig.has_dot_leader = True
    if line.has_dash:
        sig.has_dash_leader = True
    if line.price:
        sig.seen_count += 1
    if sig.seen_count >= 2:
        sig.confirmed = True


# ================================================================
# MAIN ULI PARSER
# ================================================================

def uli_parse(lines: List[str]) -> List[dict]:
    """
    Main ULI spatial parser.
    Takes raw text lines, returns structured menu items.

    Flow:
    1. Analyze all lines
    2. Detect categories, items, descriptions using spatial rules
    3. Lock pattern after 2 confirmations
    4. Build structured items
    """

    analyzed     = [analyze_line(l) for l in lines if l.strip()]
    items        = []
    current_cat  = "Unknown"
    pattern      = PatternSignature()
    pending_item = None   # item we're building
    prev_had_price = False

    for i, line in enumerate(analyzed):

        # ---- Skip empty ----
        if not line.text:
            # Empty line often signals end of description
            if pending_item:
                items.append(pending_item)
                pending_item   = None
                prev_had_price = False
            continue

        # ---- Category header ----
        if is_category(line):
            if pending_item:
                items.append(pending_item)
                pending_item = None
            current_cat    = line.text.strip().title()
            prev_had_price = False
            continue

        # ---- Line with a price = item name ----
        if line.price:
            # Save any pending item first
            if pending_item:
                items.append(pending_item)

            update_pattern(pattern, line)

            pending_item = {
                "name":        line.text,
                "category":    current_cat,
                "price":       line.price,
                "description": "",
                "allergens":   "",
                "notes":       "",
                "confidence":  0.9 if pattern.confirmed else 0.7
            }
            prev_had_price = True
            continue

        # ---- Description line ----
        if is_description(line, prev_had_price):
            if pending_item:
                if pending_item["description"]:
                    pending_item["description"] += " " + line.text
                else:
                    pending_item["description"] = line.text
            prev_had_price = False
            continue

        # ---- Modifier / add-on (indented, no price) ----
        if line.is_indented and pending_item:
            if pending_item["notes"]:
                pending_item["notes"] += " " + line.text
            else:
                pending_item["notes"] = line.text
            continue

        # ---- Unpriced item (name only, price on next line sometimes) ----
        if not line.price and not is_category(line) and line.is_short:
            # Could be an item with price coming later — hold it
            if pending_item:
                items.append(pending_item)
            pending_item = {
                "name":        line.text,
                "category":    current_cat,
                "price":       "",
                "description": "",
                "allergens":   "",
                "notes":       "",
                "confidence":  0.5   # lower confidence — no price anchor yet
            }
            prev_had_price = False

    # Save last item
    if pending_item:
        items.append(pending_item)

    # Filter out low quality results
    clean = []
    for item in items:
        name = item.get("name", "").strip()
        if not name or len(name) < 2:
            continue
        if name.replace(" ", "").isdigit():
            continue
        clean.append(item)

    return clean


# ================================================================
# CONFIDENCE REPORTER
# Tells the system how well ULI understood the menu
# ================================================================

def uli_confidence_report(items: List[dict]) -> dict:
    """
    Returns a summary of how confident ULI is about the parse.
    Used to decide whether to fall back to Claude Vision.
    """
    if not items:
        return {"score": 0.0, "verdict": "empty", "fallback": True}

    with_price = [i for i in items if i.get("price")]
    with_desc  = [i for i in items if i.get("description")]
    avg_conf   = sum(i.get("confidence", 0) for i in items) / len(items)

    score = (
        (len(with_price) / len(items)) * 0.5 +   # 50% weight: items have prices
        (len(with_desc)  / len(items)) * 0.2 +   # 20% weight: items have descriptions
        avg_conf                       * 0.3      # 30% weight: average confidence
    )

    verdict  = "high" if score > 0.7 else "medium" if score > 0.4 else "low"
    fallback = score < 0.5   # tell caller to use Claude Vision instead

    return {
        "score":        round(score, 2),
        "verdict":      verdict,
        "fallback":     fallback,
        "total_items":  len(items),
        "with_price":   len(with_price),
        "with_desc":    len(with_desc),
    }


# ================================================================
# PUBLIC ENTRY POINT
# Called by processors.py
# ================================================================

def uli_parse_file(lines: List[str]) -> tuple:
    """
    Returns (items, report) where:
    - items  = list of parsed menu items
    - report = confidence report dict
    If report["fallback"] is True, caller should use Claude Vision.
    """
    # Garbage check first — binary PDF text goes straight to Vision
    if is_garbage_text(lines):
        print("[ULI] Garbage text detected — skipping to Claude Vision")
        return [], {"score": 0.0, "verdict": "garbage", "fallback": True,
                    "total_items": 0, "with_price": 0, "with_desc": 0}

    items  = uli_parse(lines)
    report = uli_confidence_report(items)

    print(f"[ULI] Parsed {report['total_items']} items | "
          f"Score: {report['score']} | "
          f"Verdict: {report['verdict']} | "
          f"Fallback: {report['fallback']}")

    return items, report


# ================================================================
# GARBAGE DETECTION — added to block PDF binary text
# ================================================================

def is_garbage_text(lines) -> bool:
    """
    Detects binary/PDF garbage before ULI wastes time parsing it.
    Returns True if text looks like PDF binary, not a real menu.
    """
    if not lines:
        return False

    full_text = " ".join(lines)

    # PDF binary markers
    for marker in ["%PDF", "endobj", "endstream", "xref", "startxref", "%%EOF"]:
        if marker in full_text:
            print(f"[ULI] Garbage: PDF binary marker '{marker}' found → Vision fallback")
            return True

    total_chars = len(full_text)
    if total_chars == 0:
        return False

    non_printable   = sum(1 for c in full_text if ord(c) < 32 and c not in '\n\r\t')
    unicode_escapes = full_text.count("\\u00")

    if non_printable / total_chars > 0.20:
        print(f"[ULI] Garbage: {non_printable/total_chars:.0%} non-printable chars → Vision fallback")
        return True

    if unicode_escapes / max(total_chars / 4, 1) > 0.15:
        print(f"[ULI] Garbage: high unicode escape ratio → Vision fallback")
        return True

    return False