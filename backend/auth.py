# Authentication logic for Pie AI
# This file should NOT define routes or render templates

def authenticate_user(username, password):
    username = username.lower().strip()

    # Demo restaurant
    if username == "pie ai" and password == "ILPie$0314":
        return {
            "restaurant_id": "pie ai",
            "admin": False
        }

    return None
