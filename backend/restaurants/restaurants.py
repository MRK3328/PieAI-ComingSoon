# ============================================================
# 🟢 Pie AI – AI SYSTEM (CORE)
# ============================================================
 
from fileinput import filename
import profile
import profile
from flask import current_app
import os
import json
import anthropic
from flask import Blueprint, render_template, redirect, session, request, jsonify
from flask import render_template, request, redirect, session, current_app
from .processors import process_uploaded_file, dispatch_unprocessed_files
 
 
# ============================================================
# CLAUDE CLIENT
# ============================================================
 
claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
print("🟢 Pie AI – Claude (Anthropic) client initialized")
 
# ============================================================
# BLUEPRINT
# ============================================================
 
restaurants_bp = Blueprint("restaurants", __name__)
 
# ============================================================
# RESTAURANT DATA PATHS
# ============================================================
 
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RESTAURANT_DATA_DIR = os.path.join(BASE_DIR, "backend", "restaurants")
 

# ============================================================
# 🟢 Pie AI – AI SYSTEM (CORE)
# ============================================================

def load_allowed_file_text(rid, allowed_files):
    combined_text = []
    for f in allowed_files:
        path = f["path"]
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as file:
                combined_text.append(file.read())
        except Exception:
            continue
    return "\n\n".join(combined_text)


def ask_pie_ai(user_message, context_text, off_script_level=2):
    if off_script_level == 1:
        personality = (
            "You are Pie AI, a helpful restaurant assistant. "
            "Answer strictly using the menu data provided. "
            "Always include item names and prices. "
            "Be clear, direct, and factual. No creativity. "
            "For allergy questions, always recommend confirming with staff."
        )
    elif off_script_level == 3:
        personality = (
            "You are Pie AI — talk like a knowledgeable friend at the table, not a robot reading a menu. "
            "Lead with the vibe and description of items. Only mention prices if the customer asks. "
            "Keep it natural and warm — short sentences, conversational, like texting. "
            "Make the food sound appealing without being over the top. "
            "For allergy questions, be reassuring but always suggest confirming with the server."
        )
    else:
        personality = (
            "You are Pie AI, a helpful and friendly restaurant assistant. "
            "Rephrase naturally — don't just read a list. "
            "Include prices when relevant but keep the tone conversational. "
            "For allergy questions, always recommend confirming with staff for safety."
        )
    message = claude_client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        system=personality,
        messages=[
            {
                "role": "user",
                "content": f"RESTAURANT MENU DATA:\n{context_text}\n\nCUSTOMER QUESTION:\n{user_message}"
            }
        ]
    )
    return message.content[0].text.strip()


def load_active_file_text(allowed_files):
    context_parts = []
    for f in allowed_files:
        path = f["path"]
        try:
            if path.lower().endswith(".txt"):
                with open(path, "r", encoding="utf-8", errors="ignore") as file:
                    context_parts.append(file.read())
            elif path.lower().endswith(".csv"):
                import csv
                with open(path, newline="", encoding="utf-8", errors="ignore") as file:
                    reader = csv.reader(file)
                    for row in reader:
                        context_parts.append(" | ".join(row))
            elif path.lower().endswith(".xlsx"):
                import pandas as pd
                df = pd.read_excel(path)
                context_parts.append(df.to_string(index=False))
            elif path.lower().endswith(".docx"):
                from docx import Document
                doc = Document(path)
                for para in doc.paragraphs:
                    if para.text.strip():
                        context_parts.append(para.text)
        except Exception as e:
            print(f"⚠️ File skipped: {path} → {e}")
    return "\n\n".join(context_parts)

# ============================================================
# RESTAURANT PROFILE HELPERS
# ============================================================

def get_restaurant_profile(rid):
    profile_path = os.path.join(RESTAURANT_DATA_DIR, rid, "profile.json")
    if not os.path.exists(profile_path):
        return {}
    with open(profile_path, "r") as f:
        return json.load(f)

def save_restaurant_profile(rid, data):
    folder = os.path.join(RESTAURANT_DATA_DIR, rid)
    os.makedirs(folder, exist_ok=True)
    profile_path = os.path.join(folder, "profile.json")
    with open(profile_path, "w") as f:
        json.dump(data, f, indent=4)

# ============================================================
# CUSTOMER – RESTAURANT DISCOVERY
# ============================================================

def get_all_restaurants():
    restaurants = []
    if not os.path.exists(RESTAURANT_DATA_DIR):
        return restaurants
    for rid in os.listdir(RESTAURANT_DATA_DIR):
        restaurant_folder = os.path.join(RESTAURANT_DATA_DIR, rid)
        profile_path      = os.path.join(restaurant_folder, "profile.json")
        if not os.path.isdir(restaurant_folder):
            continue
        if not os.path.exists(profile_path):
            continue
        with open(profile_path, "r") as f:
            profile = json.load(f)
        restaurants.append({
            "id":      rid,
            "name":    profile.get("name", rid),
            "tagline": profile.get("tagline", ""),
            "icon":    profile.get("icon", "/static/images/placeholder.png"),
            "count":   profile.get("item_count", None)
        })
    return restaurants

# ============================================================
# CUSTOMER – RESTAURANT LIST
# ============================================================

@restaurants_bp.route("/restaurant-list")
def customer_restaurant_list():
    restaurants = get_all_restaurants()
    return render_template("c_restaurant_list.html", restaurants=restaurants)

# ============================================================
# outside R Account – R CUSTOMER CHAT  |  GET
# ============================================================

@restaurants_bp.route("/restaurant/<rid>/chat")
def customer_restaurant_chat(rid):
    profile = get_restaurant_profile(rid)
    if not profile:
        return "Restaurant not found", 404
    return render_template("r_customer_chat.html", restaurant_id=rid, profile=profile)

# ============================================================
# outside R Account – R CUSTOMER CHAT  |  POST
# Reads from menu_dataset.json — filtered by:
#   • categories where chatActive = True  (R user controls)
#   • items where active = True           (R user controls)
# ============================================================

@restaurants_bp.route("/r/<rid>/customer/chat", methods=["POST"])
def customer_restaurant_chat_post(rid):
    try:
        data         = request.get_json()
        user_message = data.get("message", "").strip()

        if not user_message:
            return jsonify({"reply": "Please enter a message."})

        dataset_path = os.path.join(RESTAURANT_DATA_DIR, rid, "menu_dataset.json")

        if not os.path.exists(dataset_path):
            return jsonify({"reply": "This restaurant hasn't set up their menu yet."})

        with open(dataset_path, "r", encoding="utf-8") as f:
            dataset = json.load(f)

        all_items      = dataset.get("items", [])
        all_categories = dataset.get("categories", [])

        # Only categories the R user has activated for customer chat
        active_cat_names = set(
            c["name"].lower()
            for c in all_categories
            if isinstance(c, dict) and c.get("chatActive") is True
        )

        if not active_cat_names:
            return jsonify({
                "reply": "The menu isn't available for chat yet. Please ask your server for assistance."
            })

        # Only items that are active AND in a chatActive category
        active_items = [
            item for item in all_items
            if item.get("active") is True
            and any(
                cat.lower() in active_cat_names
                for cat in item.get("categories", [])
            )
        ]

        if not active_items:
            return jsonify({
                "reply": "No menu items are currently available. Please check back soon or ask your server."
            })

        # Build clean readable context grouped by category
        context_lines = ["MENU ITEMS AVAILABLE:\n"]

        grouped = {}
        for item in active_items:
            cat = next(
                (c for c in item.get("categories", []) if c.lower() in active_cat_names),
                "General"
            )
            grouped.setdefault(cat, []).append(item)

        for cat_name, items in grouped.items():
            context_lines.append(f"\n--- {cat_name.upper()} ---")
            for item in items:
                line = f"  • {item.get('name', 'Unknown')}"
                if item.get("price"):
                    line += f" — ${item['price']}"
                if item.get("description"):
                    line += f"\n    {item['description']}"
                allergies = item.get("allergies") or []
                allergens = item.get("allergens", "")
                if allergies:
                    line += f"\n    Allergens: {', '.join(allergies)}"
                elif allergens:
                    line += f"\n    Allergens: {allergens}"
                note = item.get("special_notes") or item.get("notes", "")
                if note:
                    line += f"\n    Note: {note}"
                context_lines.append(line)

        context_text     = "\n".join(context_lines)
        ai_profile_path  = os.path.join(RESTAURANT_DATA_DIR, rid, "ai_profile.json")
        off_script_level = 2
        if os.path.exists(ai_profile_path):
            with open(ai_profile_path, "r") as f:
                off_script_level = json.load(f).get("off_script_level", 2)
        ai_reply = ask_pie_ai(user_message, context_text, off_script_level)
        return jsonify({"reply": ai_reply})

    except Exception as e:
        print("Customer chat ERROR:", e)
        return jsonify({"reply": "I encountered an error. Please try again."})
    
# ============================================================
# CUSTOMER – MENU SIDEBAR DATA (public, no session needed)
# Feeds the left panel of r_customer_chat.html
# Only returns categories where chatActive = True
# ============================================================

@restaurants_bp.route("/restaurant/<rid>/menu-data")
def customer_menu_data(rid):
    dataset_path = os.path.join(RESTAURANT_DATA_DIR, rid, "menu_dataset.json")

    if not os.path.exists(dataset_path):
        return jsonify({"categories": {}})

    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    items      = data.get("items", [])
    categories = data.get("categories", [])

    active_cat_names = {
        c["name"].strip().lower()
        for c in categories
        if isinstance(c, dict) and c.get("chatActive") is True
    }

    result = {}
    for item in items:
        if not item.get("active") or not item.get("customer_visible"):
            continue
        for cat in item.get("categories", []):
            if cat.strip().lower() in active_cat_names:
                result.setdefault(cat, [])
                result[cat].append({
                    "name":      item.get("name", ""),
                    "price":     item.get("price", ""),
                    "allergies": item.get("allergies", [])
                })

    return jsonify({"categories": result})

# =============================================================
# Pie AI – Manager Chat  |  Top Nav
# =============================================================

@restaurants_bp.route("/manager-chat")
def r_manager_chat():
    if "restaurant_id" not in session:
        return redirect("/login")
    rid     = session["restaurant_id"]
    profile = get_restaurant_profile(rid)
    return render_template("r_manager_chat.html", profile=profile, manager_mode=True)

# ============================================================
# Activity Dashboard  |  Top Nav
# ============================================================

@restaurants_bp.route("/activity-dashboard")
def r_activity_dashboard():
    if "restaurant_id" not in session:
        return redirect("/login")
    rid     = session["restaurant_id"]
    profile = get_restaurant_profile(rid)
    return render_template("r_activity_dashboard.html", profile=profile, manager_mode=True)

# ============================================================
# AI PROFILE – GET
# ============================================================

@restaurants_bp.route("/r-ai-profile")
def r_ai_profile():
    if "restaurant_id" not in session:
        return jsonify({"off_script_level": 2})
    rid          = session["restaurant_id"]
    profile_path = os.path.join(RESTAURANT_DATA_DIR, rid, "ai_profile.json")
    if not os.path.exists(profile_path):
        return jsonify({"off_script_level": 2})
    with open(profile_path, "r") as f:
        return jsonify(json.load(f))

# ============================================================
# AI PROFILE – SAVE
# ============================================================

@restaurants_bp.route("/r-save-ai-profile", methods=["POST"])
def r_save_ai_profile():
    if "restaurant_id" not in session:
        return jsonify({"success": False})
    rid          = session["restaurant_id"]
    data         = request.json
    profile_path = os.path.join(RESTAURANT_DATA_DIR, rid, "ai_profile.json")
    existing     = {}
    if os.path.exists(profile_path):
        with open(profile_path, "r") as f:
            existing = json.load(f)
    existing.update(data)
    with open(profile_path, "w") as f:
        json.dump(existing, f, indent=2)
    return jsonify({"success": True})

# ============================================================
# Control Panel  |  Top Nav
# ============================================================

@restaurants_bp.route("/control-panel")
def r_control_panel():
    if "restaurant_id" not in session:
        return redirect("/login")
    rid     = session["restaurant_id"]
    profile = get_restaurant_profile(rid)
    return render_template("r_control_panel.html", profile=profile)

# ============================================================
# Control Panel – MENU DATASET  1
# ============================================================

@restaurants_bp.route("/r-items")
def r_items():
    if "restaurant_id" not in session:
        return jsonify({"items": []})
    rid          = session["restaurant_id"]
    dataset_path = os.path.join(RESTAURANT_DATA_DIR, rid, "menu_dataset.json")
    if not os.path.exists(dataset_path):
        return jsonify({"items": []})
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return jsonify({"items": data.get("items", [])})

# ============================================================
# Control Panel – MENU DATASET  2
# ============================================================

@restaurants_bp.route("/r-menu-dataset")
def r_menu_dataset():
    from .dataset_builder import heal_existing_dataset
    rid          = session.get("restaurant_id", "pie_ai")
    dataset_path = os.path.join(RESTAURANT_DATA_DIR, rid, "menu_dataset.json")
    if not os.path.exists(dataset_path):
        return jsonify({"items": [], "categories": []})
    heal_existing_dataset(rid, data_dir=RESTAURANT_DATA_DIR)
    with open(dataset_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if isinstance(raw, dict):
        items      = raw.get("items", [])
        categories = raw.get("categories", [])
    else:
        items      = raw
        categories = []
    return jsonify({"items": items, "categories": categories})

# ============================================================
# SAVE ITEM
# ============================================================

@restaurants_bp.route("/r-save-item", methods=["POST"])
def r_save_item():
    if "restaurant_id" not in session:
        return jsonify({"success": False})
    rid          = session["restaurant_id"]
    dataset_path = os.path.join(RESTAURANT_DATA_DIR, rid, "menu_dataset.json")
    if not os.path.exists(dataset_path):
        return jsonify({"success": False})
    data = request.json
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)
    if isinstance(dataset, dict):
        items = dataset.get("items", [])
    else:
        items = dataset
    updated = False
    for i in range(len(items)):
        if items[i].get("id") == data.get("id"):
            items[i] = data
            updated  = True
            break
    if not updated:
        items.append(data)
    if isinstance(dataset, dict):
        dataset["items"] = items
    else:
        dataset = items
    with open(dataset_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2)
    return jsonify({"success": True})

# ============================================================
# DELETE ITEM
# ============================================================

@restaurants_bp.route("/r-delete-item", methods=["POST"])
def r_delete_item():
    if "restaurant_id" not in session:
        return jsonify({"success": False})
    rid          = session["restaurant_id"]
    dataset_path = os.path.join(RESTAURANT_DATA_DIR, rid, "menu_dataset.json")
    if not os.path.exists(dataset_path):
        return jsonify({"success": False})
    item_id = request.json.get("id")
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)
    if isinstance(dataset, dict):
        items = dataset.get("items", [])
    else:
        items = dataset
    items = [i for i in items if i.get("id") != item_id]
    if isinstance(dataset, dict):
        dataset["items"] = items
    else:
        dataset = items
    with open(dataset_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2)
    return jsonify({"success": True})

# ============================================================
# DELETE CATEGORY
# ============================================================

@restaurants_bp.route("/r-delete-category", methods=["POST"])
def r_delete_category():
    if "restaurant_id" not in session:
        return jsonify({"success": False})
    rid      = session["restaurant_id"]
    cat_name = request.json.get("name", "").strip()
    if not cat_name:
        return jsonify({"success": False})
    dataset_path = os.path.join(RESTAURANT_DATA_DIR, rid, "menu_dataset.json")
    if not os.path.exists(dataset_path):
        return jsonify({"success": False})
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)
    if not isinstance(dataset, dict):
        return jsonify({"success": False})
    items      = dataset.get("items", [])
    categories = dataset.get("categories", [])
    categories = [c for c in categories if c.get("name", "").lower() != cat_name.lower()]
    for item in items:
        item["categories"] = [
            c for c in item.get("categories", [])
            if c.lower() != cat_name.lower()
        ]
    dataset["items"]      = items
    dataset["categories"] = categories
    with open(dataset_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2)
    return jsonify({"success": True})
# ============================================================
# SAVE CATEGORIES
# Called whenever R user changes chatActive, location, or time
# on a category — persists those changes to menu_dataset.json
# ============================================================

@restaurants_bp.route("/r-save-categories", methods=["POST"])
def r_save_categories():
    if "restaurant_id" not in session:
        return jsonify({"success": False})

    rid  = session["restaurant_id"]
    data = request.json

    incoming_categories = data.get("categories", [])

    if not incoming_categories:
        return jsonify({"success": False})

    dataset_path = os.path.join(RESTAURANT_DATA_DIR, rid, "menu_dataset.json")

    if not os.path.exists(dataset_path):
        return jsonify({"success": False})

    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    if not isinstance(dataset, dict):
        return jsonify({"success": False})

    # Merge incoming category settings into saved data.
    # Key by lowercase name so existing R user settings
    # (location, time, chatActive) are updated, not replaced.
    existing = {
        c["name"].strip().lower(): c
        for c in dataset.get("categories", [])
        if isinstance(c, dict) and c.get("name")
    }

    for cat in incoming_categories:
        name = cat.get("name", "").strip()
        if not name:
            continue
        key = name.lower()
        if key in existing:
            # Update fields the R user can change
            existing[key]["chatActive"] = cat.get("chatActive", False)
            existing[key]["location"]   = cat.get("location", "Entire Restaurant")
            existing[key]["timeStart"]  = cat.get("timeStart", "")
            existing[key]["timeEnd"]    = cat.get("timeEnd", "")
        else:
            # New category — add it
            existing[key] = {
                "name":       name,
                "location":   cat.get("location", "Entire Restaurant"),
                "timeStart":  cat.get("timeStart", ""),
                "timeEnd":    cat.get("timeEnd", ""),
                "chatActive": cat.get("chatActive", False)
            }

    dataset["categories"] = list(existing.values())

    with open(dataset_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2)

    return jsonify({"success": True})

# ============================================================
# R FILES – Top Nav  1
# ============================================================

@restaurants_bp.route("/r-files")
def r_files():
    if "restaurant_id" not in session:
        return redirect("/login")
    rid          = session["restaurant_id"]
    profile_path = os.path.join(RESTAURANT_DATA_DIR, rid, "profile.json")
    profile      = {}
    if os.path.exists(profile_path):
        with open(profile_path, "r") as f:
            profile = json.load(f)
    base_dir        = os.path.join(RESTAURANT_DATA_DIR, rid, "files")
    files_json_path = os.path.join(base_dir, "files.json")
    files           = []
    saved_meta      = {}
    if os.path.exists(files_json_path):
        with open(files_json_path, "r") as f:
            for item in json.load(f).get("files", []):
                saved_meta[item["name"]] = item
    if os.path.exists(base_dir):
        for category in ["menu", "other"]:
            category_dir = os.path.join(base_dir, category)
            if not os.path.exists(category_dir):
                continue
            for filename in os.listdir(category_dir):
                meta = saved_meta.get(filename, {})
                files.append({
                    "name":     filename,
                    "category": category,
                    "active":   bool(meta.get("active", True))
                })
    return render_template("r_files.html", files=files, profile=profile)

# ============================================================
# R FILES – TOGGLE  2
# ============================================================

@restaurants_bp.route("/r-files/toggle", methods=["POST"])
def r_files_toggle():
    if "restaurant_id" not in session:
        return redirect("/login")
    rid       = session["restaurant_id"]
    filename  = request.form.get("filename")
    category  = request.form.get("category")
    json_path = os.path.join(RESTAURANT_DATA_DIR, rid, "files", "files.json")
    data      = {"files": []}
    if os.path.exists(json_path):
        with open(json_path, "r") as f:
            data = json.load(f)
    for f in data["files"]:
        if f["name"] == filename and f["category"] == category:
            f["active"] = not f.get("active", True)
            break
    else:
        data["files"].append({"name": filename, "category": category, "active": False})
    with open(json_path, "w") as f:
        json.dump(data, f, indent=2)
    return redirect("/r-files")

# ============================================================
# FILE INDEX HELPERS (AI MEMORY PERMISSIONS)  3
# ============================================================

def get_files_index(rid):
    path = os.path.join(RESTAURANT_DATA_DIR, rid, "files.json")
    if not os.path.exists(path):
        return {"files": []}
    with open(path, "r") as f:
        return json.load(f)

def save_files_index(rid, data):
    folder = os.path.join(RESTAURANT_DATA_DIR, rid)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "files.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

# ============================================================
# R FILES – DELETE  4
# ============================================================

@restaurants_bp.route("/r-files/delete", methods=["POST"])
def r_files_delete():
    if "restaurant_id" not in session:
        return redirect("/login")
    rid       = session["restaurant_id"]
    filename  = request.form.get("filename")
    category  = request.form.get("category")
    base_dir  = os.path.join(RESTAURANT_DATA_DIR, rid, "files")
    file_path = os.path.join(base_dir, category, filename)
    json_path = os.path.join(base_dir, "files.json")
    if os.path.exists(file_path):
        os.remove(file_path)
    if os.path.exists(json_path):
        with open(json_path, "r") as f:
            data = json.load(f)
        data["files"] = [
            f for f in data["files"]
            if not (f["name"] == filename and f["category"] == category)
        ]
        with open(json_path, "w") as f:
            json.dump(data, f, indent=2)
    return redirect("/r-files")

# ============================================================
# R FILES – UPLOAD  5
# ============================================================

@restaurants_bp.route("/r-files/upload", methods=["POST"])
def r_files_upload():
    if "restaurant_id" not in session:
        return redirect("/login")
    rid            = session["restaurant_id"]
    uploaded_files = request.files.getlist("files")
    base_dir       = os.path.join(RESTAURANT_DATA_DIR, rid, "files")
    menu_dir       = os.path.join(base_dir, "menu")
    other_dir      = os.path.join(base_dir, "other")
    os.makedirs(menu_dir,  exist_ok=True)
    os.makedirs(other_dir, exist_ok=True)
    json_path = os.path.join(base_dir, "files.json")
    if os.path.exists(json_path):
        with open(json_path, "r") as f:
            data = json.load(f)
    else:
        data = {"files": []}
    for file in uploaded_files:
        if not file or not file.filename:
            continue
        safe_name = file.filename.replace(" ", "_")
        category  = "menu"
        save_path = os.path.join(menu_dir, safe_name)
        file.save(save_path)
        data["files"].append({
            "restaurant_id": rid,
            "name":          safe_name,
            "category":      category,
            "processed":     False
        })
        process_uploaded_file(restaurant_id=rid, filename=safe_name, category=category)
    dispatch_unprocessed_files()
    with open(json_path, "w") as f:
        json.dump(data, f, indent=2)
    return redirect("/r-files")

# ============================================================
# 🟢 Pie AI – File Text Extraction (Phase 1)  6
# Supports: .xlsx, .xls, .csv
# ============================================================

import csv

try:
    import openpyxl
except ImportError:
    openpyxl = None


def extract_text_from_file(file_path):
    text_chunks = []
    if file_path.endswith((".xlsx", ".xls")):
        if not openpyxl:
            return ""
        try:
            wb = openpyxl.load_workbook(file_path, data_only=True)
            for sheet in wb.worksheets:
                text_chunks.append(f"\n--- Sheet: {sheet.title} ---")
                for row in sheet.iter_rows(values_only=True):
                    row_text = " | ".join(
                        str(cell).strip() for cell in row if cell is not None
                    )
                    if row_text:
                        text_chunks.append(row_text)
        except Exception:
            return ""
    elif file_path.endswith(".csv"):
        try:
            with open(file_path, newline="", encoding="utf-8", errors="ignore") as f:
                reader = csv.reader(f)
                for row in reader:
                    row_text = " | ".join(cell.strip() for cell in row if cell)
                    if row_text:
                        text_chunks.append(row_text)
        except Exception:
            return ""
    return "\n".join(text_chunks)


def build_ai_context(allowed_files):
    context_parts = []
    for f in allowed_files:
        extracted = extract_text_from_file(f["path"])
        if extracted:
            context_parts.append(f"\n### FILE: {f['name']} ({f['category']})\n{extracted}")
    return "\n".join(context_parts)

# ============================================================
# RESTAURANT HOME  |  Bottom Nav
# ============================================================

@restaurants_bp.route("/restaurant-home")
def restaurant_home():
    if "restaurant_id" not in session:
        return redirect("/login")
    rid     = session["restaurant_id"]
    profile = get_restaurant_profile(rid)
    return render_template(
        "r_home.html", profile=profile,
        restaurant_id=rid, stats={}, updates=[]
    )

# ============================================================
# My PROFILE  |  Bottom Nav
# ============================================================

@restaurants_bp.route("/my-profile", methods=["GET", "POST"])
def r_profile():
    if "restaurant_id" not in session:
        return redirect("/login")

    rid     = session["restaurant_id"]
    profile = get_restaurant_profile(rid)

    restaurant_dir        = os.path.join(RESTAURANT_DATA_DIR, rid)
    assets_dir            = os.path.join(restaurant_dir, "assets")
    os.makedirs(assets_dir, exist_ok=True)

    restaurant_static_dir = os.path.join(
        current_app.root_path, "static", "restaurants", rid, "assets"
    )
    os.makedirs(restaurant_static_dir, exist_ok=True)

    if request.method == "POST":

        # ── HELPER ───────────────────────────────────────────
        # Only overwrite a field if the form sent a non-empty value.
        # If the field came in blank, keep whatever is already saved.
        def keep(form_key, profile_key=None):
            pk  = profile_key or form_key
            val = request.form.get(form_key, "").strip()
            return val if val else profile.get(pk, "")
        # ─────────────────────────────────────────────────────

        profile["name"]             = keep("name")
        profile["theme"]            = keep("theme")
        profile["accent"]           = keep("accent")
        profile["accent_color"]     = profile["accent"]   # keep both keys in sync
        profile["background_mode"]  = keep("background_mode")
        profile["background_color"] = keep("background_color")
        profile["header_preset"]    = keep("header_preset")

        # Files — only update if a new file was actually uploaded
        header_file = request.files.get("header_image")
        if header_file and header_file.filename:
            header_name = f"header_{header_file.filename.replace(' ', '_')}"
            header_file.save(os.path.join(restaurant_static_dir, header_name))
            profile["header_image"] = f"/static/restaurants/{rid}/assets/{header_name}"

        profile_file = request.files.get("profile_image")
        if profile_file and profile_file.filename:
            profile_name = f"profile_{profile_file.filename.replace(' ', '_')}"
            profile_file.save(os.path.join(restaurant_static_dir, profile_name))
            profile["profile_image"] = f"/static/restaurants/{rid}/assets/{profile_name}"

        save_restaurant_profile(rid, profile)
        return redirect("/my-profile")

    return render_template("r_profile.html", profile=profile, restaurant_id=rid)

# ============================================================
# SETTINGS  |  Bottom Nav
# ============================================================

@restaurants_bp.route("/r-settings")
def r_settings():
    if "restaurant_id" not in session:
        return redirect("/login")
    rid     = session["restaurant_id"]
    profile = get_restaurant_profile(rid)
    return render_template(
        "r_settings.html", profile=profile,
        restaurant_id=rid, manager_mode=True
    )