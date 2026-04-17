import json
import os
from rapidfuzz import fuzz


# Automatically build correct path to staging file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FOOD_STAGING = os.path.join(BASE_DIR, "pie_ai", "food_staging.json")


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_name(name):
    """
    Clean item names so fuzzy matching works better
    """
    if not name:
        return ""

    name = name.lower()

    # remove punctuation
    name = name.replace("(", "")
    name = name.replace(")", "")

    # remove size variants
    name = name.replace("double", "")
    name = name.replace("single", "")
    name = name.replace("dc", "")
    name = name.replace("sn", "")

    return name.strip()


def match_items(item_a, item_b):

    name_a = normalize_name(item_a)
    name_b = normalize_name(item_b)

    score = fuzz.ratio(name_a, name_b)

    return score


def load_food_items():

    data = load_json(FOOD_STAGING)

    items = data.get("items", [])

    print("Loaded items:", len(items))

    return items


def test_matching():

    items = load_food_items()

    seen = set()

    for i in items:
        for j in items:

            name_a = i.get("item")
            name_b = j.get("item")

            if not name_a or not name_b:
                continue

            if name_a == name_b:
                continue

            score = match_items(name_a, name_b)

            if score > 85:

                pair = tuple(sorted([name_a, name_b]))

                if pair in seen:
                    continue

                seen.add(pair)

                print("MATCH FOUND")
                print(name_a, "<->", name_b)
                print("Score:", score)
                print()


if __name__ == "__main__":
    test_matching()