from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# =========================================================
# EMAIL CONFIGURATION
# =========================================================
from flask_mail import Mail, Message

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'nexus33business@gmail.com'
app.config['MAIL_PASSWORD'] = 'oogp ksxk sjhn uizr'  # your Google app password
app.config['MAIL_DEFAULT_SENDER'] = ('Pie AI Registration', 'nexus33business@gmail.com')

mail = Mail(app)

# =========================================================
# MAIN ROUTES
# =========================================================

@app.route('/')
def home():
    """Landing page"""
    return render_template('index.html')

@app.route('/why')
def why_page():
    """Why Pie AI section"""
    return render_template('why.html')

@app.route('/about')
def about_page():
    """About page"""
    return render_template('about.html')

@app.route('/links')
def links_page():
    """Link hub page"""
    return render_template('links.html')

@app.route('/thankyou')
def thankyou_page():
    """Thank you confirmation page"""
    return render_template('thankyou.html')

@app.route('/error')
def error_page():
    """Error page"""
    return render_template('error.html')

@app.route('/contact')
def contact_page():
    """Contact page"""
    return render_template('contact.html')

@app.route('/loading')
def loading_page():
    """Loading animation / transition page"""
    return render_template('loading.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')


# =========================================================
# FORM SUBMISSION + REDIRECT FLOW
# =========================================================
@app.route('/preregister', methods=['GET', 'POST'])
def preregister_page():
    if request.method == 'POST':
        role = request.form.get('role')
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        message = request.form.get('message')

        msg = Message(
            f"New Pie AI {role} Registration",
            recipients=['CEO@Nexus33LLC.com']
        )
        msg.body = f"""
        New {role} Registration:

        Name / Restaurant: {name}
        Email: {email}
        Phone: {phone}
        Message: {message}
        """

        try:
            mail.send(msg)
            # Step 1: Go to loading page first instead of thank you
            return redirect(url_for('loading_page'))
        except Exception as e:
            return f"Error sending email: {e}"

    return render_template('preregister.html')


# =========================================================
# ERROR HANDLERS
# =========================================================

@app.errorhandler(404)
def page_not_found(e):
    """Custom 404 error redirect"""
    return render_template('error.html'), 404

@app.errorhandler(500)
def internal_error(e):
    """Custom 500 error redirect"""
    return render_template('error.html'), 500

# =========================================================
# LAUNCH
# =========================================================

if __name__ == '__main__':
    app.run(debug=True)
