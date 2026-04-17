import os
import json
import pandas as pd
from datetime import datetime

BASE_DIR = os.path.dirname(__file__)
RESTAURANTS_DIR = BASE_DIR


def normalize_category(raw):
    if not raw:
        return "Unknown"
    return str(raw).strip().title()


def normalize_allergens(raw):
    """
    Normalizes allergens to a clean list regardless of input format.
    Handles: string "dairy, gluten", list ["dairy","gluten"], empty, None
    """
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(a).strip() for a in raw if str(a).strip()]
    if isinstance(raw, str):
        parts = [a.strip() for a in raw.replace(";", ",").replace("/", ",").split(",")]
        return [p for p in parts if p]
    return []


def merge_allergens(existing, incoming):
    """
    Merges two allergen sources into one deduplicated list.
    Works regardless of whether inputs are strings or lists.
    """
    existing_list = normalize_allergens(existing)
    incoming_list = normalize_allergens(incoming)
    return list(dict.fromkeys(existing_list + incoming_list))


# ================================================================
# SELF-HEALING PASS
# Only fixes items where user_set is NOT true.
# Items saved by the R user have user_set=True and are never touched.
# ================================================================

def heal_existing_dataset(restaurant_id, data_dir=None):
    base         = data_dir if data_dir else RESTAURANTS_DIR
    dataset_file = os.path.join(base, restaurant_id, "menu_dataset.json")

    if not os.path.exists(dataset_file):
        print(f"[heal] No dataset found at {dataset_file}")
        return

    with open(dataset_file, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except Exception as e:
            print(f"[heal] JSON load error: {e}")
            return

    if not isinstance(data, dict):
        return

    changed    = False
    items      = data.get("items", [])
    categories = data.get("categories", [])

    for item in items:

        # Normalize category strings to Title Case
        old_cats = item.get("categories", [])
        new_cats = list(dict.fromkeys(normalize_category(c) for c in old_cats))
        if new_cats != old_cats:
            item["categories"] = new_cats
            changed = True

        # Normalize allergens to list format
        raw_allergies   = item.get("allergies") or item.get("allergens", "")
        clean_allergies = normalize_allergens(raw_allergies)
        if clean_allergies != item.get("allergies"):
            item["allergies"] = clean_allergies
            item["allergens"] = ", ".join(clean_allergies)
            changed = True

        # ONLY fix items the R user has NEVER manually saved
        if item.get("user_set") is True:
            continue

        # Item was auto-parsed — ensure it defaults active
        if item.get("item_status") == "inactive" or item.get("active") is False:
            item["item_status"]      = "active"
            item["active"]           = True
            item["customer_visible"] = True
            changed = True

    # Rebuild categories list from items
    cat_map = {
        c["name"].strip().lower(): c
        for c in categories
        if isinstance(c, dict) and c.get("name")
    }

    all_cat_names = set()
    for item in items:
        for c in item.get("categories", []):
            all_cat_names.add(normalize_category(c))

    for name in all_cat_names:
        key = name.lower()
        if key not in cat_map:
            cat_map[key] = {
                "name":       name,
                "location":   "Entire Restaurant",
                "timeStart":  "",
                "timeEnd":    "",
                "chatActive": False
            }
            changed = True
        else:
            if cat_map[key].get("name") != name:
                cat_map[key]["name"] = name
                changed = True

    if changed:
        data["items"]      = items
        data["categories"] = list(cat_map.values())
        with open(dataset_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"[heal] Fixed dataset for {restaurant_id}")
    else:
        print(f"[heal] No changes needed for {restaurant_id}")


# ================================================================
# BUILD DATASET
# Merges parsed items from any file into the existing dataset.
#
# MULTI-FILE MERGE RULES:
#   - Item already exists → fill in any empty fields from new file
#   - Allergens → ALWAYS combine from all sources (never overwrite)
#   - Price → fill in if currently empty
#   - Description → fill in if currently empty
#   - Sources → track every file that contributed to this item
#   - Flags → removed automatically when field is filled in
# ================================================================

def build_dataset(record, parsed_items=None, data_dir=None):

    restaurant_id = record.get("restaurant_id", "pie ai")
    filename      = record.get("name")
    category      = record.get("category")
    bucket        = record.get("bucket", "food")

    base = data_dir if data_dir else RESTAURANTS_DIR

    restaurant_path = os.path.join(base, restaurant_id)
    os.makedirs(restaurant_path, exist_ok=True)

    print("RESTAURANT ID:", restaurant_id)
    print("RESTAURANT PATH:", restaurant_path)

    file_path = os.path.join(base, restaurant_id, "files", category, filename)

    print(f"Processing dataset file: {filename}")
    print("FILE PATH:", file_path)

    if not os.path.exists(file_path):
        print("File not found")
        return False

    dataset_file = os.path.join(restaurant_path, "menu_dataset.json")

    existing_items      = []
    existing_categories = []

    if os.path.exists(dataset_file):
        with open(dataset_file, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                if isinstance(data, dict):
                    existing_items      = data.get("items", [])
                    existing_categories = data.get("categories", [])
            except Exception:
                pass

    # Build lookup dict keyed by lowercase name
    items = {
        item.get("name", "").strip().lower(): item
        for item in existing_items
        if item.get("name")
    }

    # Normalize existing items
    for item in items.values():
        old_cats = item.get("categories", [])
        item["categories"] = list(dict.fromkeys(normalize_category(c) for c in old_cats))
        item["allergies"]  = normalize_allergens(item.get("allergies") or item.get("allergens", ""))

        if item.get("user_set") is True:
            continue

        if item.get("item_status") == "inactive" or item.get("active") is False:
            item["item_status"]      = "active"
            item["active"]           = True
            item["customer_visible"] = True

    categories = {
        c["name"].strip().lower(): c
        for c in existing_categories
        if isinstance(c, dict) and c.get("name")
    }

    item_counter = len(items) + 1

    def ensure_category(raw_name):
        name     = normalize_category(raw_name)
        name_key = name.lower()
        if name_key not in categories:
            categories[name_key] = {
                "name":       name,
                "location":   "Entire Restaurant",
                "timeStart":  "",
                "timeEnd":    "",
                "chatActive": False
            }
        else:
            categories[name_key]["name"] = name
        return name

    if parsed_items:

        for parsed in parsed_items:

            name = parsed.get("name")
            if not name:
                continue
            name = str(name).strip()
            if not name:
                continue

            name_key     = name.lower()
            description  = parsed.get("description", "")
            price        = str(parsed.get("price", "") or "").strip()
            raw_category = parsed.get("category", category)
            cat_name     = ensure_category(raw_category)
            notes        = parsed.get("notes", "")

            # Normalize incoming allergens — handles string or list
            incoming_allergens = normalize_allergens(
                parsed.get("allergens") or parsed.get("allergies", "")
            )

            # ============================================
            # EXISTING ITEM — fill in any empty fields
            # ============================================
            if name_key in items:
                item = items[name_key]
                item.setdefault("sources",    [])
                item.setdefault("categories", [])
                item.setdefault("allergies",  [])
                item.setdefault("flags",      [])

                # Fill empty description
                if not item.get("description") and description:
                    item["description"] = description
                    print(f"[merge] '{name}' ← description from {filename}")

                # Fill empty price
                if not item.get("price") and price:
                    item["price"] = price
                    print(f"[merge] '{name}' ← price from {filename}")

                # ALWAYS merge allergens — combine from ALL sources
                # This fires regardless of whether item already has allergens
                # so uploading a separate allergy file always adds to existing items
                if incoming_allergens:
                    before = list(item["allergies"])
                    item["allergies"] = merge_allergens(item["allergies"], incoming_allergens)
                    item["allergens"] = ", ".join(item["allergies"])
                    if item["allergies"] != before:
                        print(f"[merge] '{name}' ← allergens filled from {filename}: {item['allergies']}")
                    else:
                        print(f"[merge] '{name}' — allergens already up to date")

                # Fill empty notes
                if notes and not item.get("special_notes"):
                    item["special_notes"] = notes

                # Add category if not already there — never add "Unknown" if item already has real categories
                existing_norm = [c.lower() for c in item["categories"]]
                real_cats = [c for c in item["categories"] if c.lower() != "unknown"]
                if cat_name.lower() not in existing_norm:
                    if cat_name.lower() != "unknown" or not real_cats:
                        item["categories"].append(cat_name)

                # Track source file
                if filename not in item["sources"]:
                    item["sources"].append(filename)

                # Remove flags that are now resolved
                if item.get("description") and "Missing Description" in item["flags"]:
                    item["flags"].remove("Missing Description")
                if item.get("price") and "Missing Price" in item["flags"]:
                    item["flags"].remove("Missing Price")

            # ============================================
            # NEW ITEM — create fresh
            # ============================================
            else:
                prefix  = bucket[0].upper()
                item_id = f"{prefix}{str(item_counter).zfill(3)}"

                flags = []
                if not price:
                    flags.append("Missing Price")
                if not description:
                    flags.append("Missing Description")

                item = {
                    "id":                   item_id,
                    "name":                 name,
                    "categories":           [cat_name],
                    "description":          description,
                    "price":                price,
                    "allergies":            incoming_allergens,
                    "allergens":            ", ".join(incoming_allergens),
                    "special_notes":        notes,
                    "item_status":          "active",
                    "active":               True,
                    "customer_visible":     True,
                    "user_set":             False,
                    "available_from":       None,
                    "available_until":      None,
                    "location_restriction": "Entire Restaurant",
                    "sources":              [filename],
                    "bucket":               bucket,
                    "flags":                flags
                }

                items[name_key] = item
                item_counter += 1

    else:
        # ============================================
        # STRUCTURED FALLBACK (Excel direct read)
        # ============================================
        if file_path.endswith((".xlsx", ".xls")):
            df = pd.read_excel(file_path)
            for _, row in df.iterrows():
                name = row.get("Item")
                if pd.isna(name):
                    continue
                name_key    = str(name).strip().lower()
                cat_name    = ensure_category(category)
                raw_allergy = row.get("Allergens") or row.get("Allergies") or ""
                allergens   = normalize_allergens(str(raw_allergy) if raw_allergy else "")

                item = {
                    "id":                   f"{bucket[0].upper()}{str(item_counter).zfill(3)}",
                    "name":                 str(name).strip(),
                    "categories":           [cat_name],
                    "description":          str(row.get("Description") or "").strip(),
                    "price":                str(row.get("Price") or "").strip(),
                    "allergies":            allergens,
                    "allergens":            ", ".join(allergens),
                    "special_notes":        "",
                    "item_status":          "active",
                    "active":               True,
                    "customer_visible":     True,
                    "user_set":             False,
                    "available_from":       None,
                    "available_until":      None,
                    "location_restriction": "Entire Restaurant",
                    "sources":              [filename],
                    "bucket":               bucket,
                    "flags":                []
                }
                items[name_key] = item
                item_counter += 1

    final_items      = list(items.values())
    final_categories = list(categories.values())

    print("TOTAL ITEMS:", len(final_items))
    print("TOTAL CATEGORIES:", len(final_categories))

    with open(dataset_file, "w", encoding="utf-8") as f:
        json.dump({
            "items":      final_items,
            "categories": final_categories
        }, f, indent=2)

    print(f"Dataset updated: {len(final_items)} items, {len(final_categories)} categories")
    return True