from flask import Flask, render_template, request, redirect, url_for
import gspread
from datetime import datetime

app = Flask(__name__)

# ===========================================
# GOOGLE SHEETS CONNECTION
# ===========================================
import os, json
from google.oauth2.service_account import Credentials
import gspread

credentials_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
credentials_dict = json.loads(credentials_json)

gc = gspread.authorize(Credentials.from_service_account_info(credentials_dict))
sheet = gc.open_by_key("1h4AMu9vc6ZyRrc6tN54pYe36J3Cjnh0CRLstjP3rqpw").sheet1

# ===========================================
# ROUTES
# ===========================================
@app.route('/')
def home():
    return render_template('index.html')

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

@app.route('/loading')
def loading_page():
    return render_template('loading.html')

# ===========================================
# FORM SUBMISSION → GOOGLE SHEETS
# ===========================================
@app.route('/preregister', methods=['GET', 'POST'])
def preregister_page():
    if request.method == 'POST':
        role = request.form.get('role')
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        message = request.form.get('message')

        try:
            sheet.append_row([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                role,
                name,
                email,
                message,
                phone
            ])

            return redirect(url_for('loading_page'))

        except Exception as e:
            return f"Error writing to Google Sheet: {e}"

    return render_template('preregister.html')

# ===========================================
# ERROR PAGES
# ===========================================
@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html'), 404

@app.errorhandler(500)
def internal_error(e):
    return render_template('error.html'), 500

# ===========================================
# RUN
# ===========================================
if __name__ == '__main__':
    app.run(debug=True)
