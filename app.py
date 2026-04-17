from flask import Flask, render_template, request, redirect, session
from flask_mail import Mail, Message
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

from backend.auth import authenticate_user
from backend.restaurants.restaurants import restaurants_bp

app = Flask(__name__)
app.secret_key = "CHANGE_THIS_SECRET_KEY"

# ============================================================
# MAIL CONFIG
# ============================================================

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')

mail = Mail(app)

# ============================================================
# REGISTER BLUEPRINTS
# ============================================================

app.register_blueprint(restaurants_bp)

# ============================================================
# PATHS / CONFIG
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESTAURANT_DATA_DIR = os.path.join(BASE_DIR, "backend", "restaurants")
RESTAURANT_STATIC_DIR = os.path.join(BASE_DIR, "static", "restaurants")

# ============================================================
# PUBLIC PAGES
# ============================================================

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/why')
def why_page():
    return render_template('why.html')

@app.route('/about')
def about_page():
    return render_template('about.html')

@app.route('/links')
def links_page():
    return render_template('links.html')

@app.route('/thankyou')
def thankyou_page():
    return render_template('thankyou.html')

@app.route('/error')
def error_page():
    return render_template('error.html')

@app.route('/contact')
def contact_page():
    return render_template('contact.html')

@app.route('/pricing')
def pricing_page():
    return render_template('pricing.html')

@app.route('/privacy')
def privacy_page():
    return render_template('privacy.html')

# ============================================================
# EARLY ACCESS — WAVE FORM
# ============================================================

@app.route('/join-wave', methods=['POST'])
def join_wave():
    try:
        data = request.get_json()
        email = data.get('email', '').strip()
        entry_type = data.get('type', 'supporter').capitalize()

        if not email or '@' not in email:
            return {'success': False, 'error': 'Invalid email'}, 400

        msg = Message(
            subject=f"New Pie AI Sign Up — {entry_type}",
            sender=os.environ.get('MAIL_USERNAME'),
            recipients=[os.environ.get('MAIL_USERNAME')],
            body=f"New sign up!\n\nType: {entry_type}\nEmail: {email}\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        mail.send(msg)
        print(f"✅ Email sent for: {email} ({entry_type})")

        return {'success': True}, 200

    except Exception as e:
        print(f"❌ Mail error: {e}")
        return {'success': False, 'error': str(e)}, 500

# ============================================================
# RESTAURANT SETUP
# ============================================================

@app.route('/restaurant-setup-1')
def restaurant_setup1():
    return render_template('r_setup_main.html')

@app.route('/restaurant-setup-2')
def restaurant_setup2():
    return render_template('r_setup_files.html')

@app.route('/restaurant-subscription')
def restaurant_subscription():
    return render_template('r_subscription.html')

# ============================================================
# LOGIN
# ============================================================

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = authenticate_user(username, password)

        if user:
            session['restaurant_id'] = user['restaurant_id']
            session['admin'] = user['admin']

            if user['admin']:
                return redirect('/loading-ceo')
            else:
                return redirect('/loading-restaurant')

        return render_template('r_login.html', error="Invalid username or password")

    return render_template('r_login.html')

# ============================================================
# LOADING
# ============================================================

@app.route('/loading-restaurant')
def loading_to_restaurant():
    if 'restaurant_id' not in session:
        return redirect('/login')
    return render_template('loading.html', next="/restaurant-home")

@app.route('/loading-ceo')
def loading_to_ceo():
    if session.get('admin') is not True:
        return redirect('/login')
    return render_template('loading.html', next="/ceo-office")

# ============================================================
# ERRORS
# ============================================================

@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html'), 404

@app.errorhandler(500)
def internal_error(e):
    return render_template('error.html'), 500

# ============================================================
# RUN
# ============================================================

if __name__ == '__main__':
    print("Pie AI Local Server Running — Login Active")
    app.run(debug=True)