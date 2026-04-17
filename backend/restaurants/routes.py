import os
import json
from flask import Blueprint, jsonify, session

restaurant_routes = Blueprint('restaurant_routes', __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESTAURANTS_DIR = os.path.join(BASE_DIR, "restaurants")

@restaurant_routes.route("/r-menu-dataset")
def r_menu_dataset():
    # Get restaurant_id from session (however your auth sets it)
    restaurant_id = session.get("restaurant_id")
    if not restaurant_id:
        return jsonify({"error": "No restaurant in session"}), 401

    dataset_file = os.path.join(RESTAURANTS_DIR, restaurant_id, "menu_dataset.json")

    if not os.path.exists(dataset_file):
        return jsonify({"categories": {}}), 200

    with open(dataset_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    items      = data.get("items", [])
    categories = data.get("categories", [])

    # Only categories with chatActive = True
    active_cat_names = {
        c["name"].strip().lower()
        for c in categories
        if c.get("chatActive") is True
    }

    # Build response: { "Appetizers": [...items], "Dinner": [...] }
    result = {}
    for item in items:
        if not item.get("active") or not item.get("customer_visible"):
            continue
        for cat in item.get("categories", []):
            if cat.strip().lower() in active_cat_names:
                result.setdefault(cat, [])
                result[cat].append({
                    "name":        item.get("name", ""),
                    "price":       item.get("price", ""),
                    "description": item.get("description", ""),
                    "allergies":   item.get("allergies", [])
                })

    return jsonify({"categories": result})