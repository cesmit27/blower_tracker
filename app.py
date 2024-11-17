# app.py
from flask import Flask, render_template, redirect, url_for, request, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import func
from config import Config
from models import db, User, Sighting
from datetime import datetime, timedelta
import time

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config.from_object(Config)
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Initialize Flask-Migrate and SQLAlchemy with the app
db.init_app(app)
migrate = Migrate(app, db)  # Initialize Flask-Migrate with app and db

@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']  # Get the logged-in user's ID
    user = User.query.get(user_id)  # Get the user from the database using the ID

    last_sighting = Sighting.query.filter_by(user_id=user_id).order_by(Sighting.datetime.desc()).first()
    home_gif = "mad-angry.gif"
    days_since = "No sightings yet"
    
    if last_sighting:
        # Get the current time in the user's local timezone (simplified to system local time)
        now = datetime.fromtimestamp(time.time())  # Current time (system local time)
        sighting_time_local = last_sighting.datetime  # Assuming datetime is stored in local time

        # Calculate the time difference from the most recent sighting
        diff = now - sighting_time_local  # The difference between now and the sighting time
        # Calculate days, hours, and minutes
        if diff.days == 0 and diff.seconds < 3600:  # Less than 1 hour (in seconds)
            minutes = diff.seconds // 60
            days_since = f"{minutes} minute{'' if minutes == 1 else 's'}"
            home_gif = "mad-angry.gif"
        elif diff.days == 0 and diff.seconds < 86400:  # Less than 24 hours, but more than 1 hour
            hours = diff.seconds // 3600
            minutes = (diff.seconds % 3600) // 60
            days_since = f"{hours} hour{'s' if hours > 1 else ''} and {minutes} minute{'s' if minutes > 1 else ''} "
            home_gif = "button.gif"
        elif diff.days == 1:
            days_since = "1 day "
            home_gif = "diep.gif"
        else:  # More than 1 day ago
            days_since = f"{diff.days} days "
            home_gif = "thin_ice.gif"
    else:
        days_since = "No sightings yet"

    top_sightings = db.session.query(Sighting.user_id, func.count(Sighting.id).label('total_sightings'))\
        .group_by(Sighting.user_id).order_by(func.count(Sighting.id).desc()).limit(10).all()

    top_users = [{'user': User.query.get(user_id), 'total_sightings': total_sightings} for user_id, total_sightings in top_sightings]

    try:
        about_file_path = os.path.join(app.root_path, 'static', 'about.txt')  # Absolute path to static/about.txt
        with open(about_file_path, 'r') as file:
            about = file.read()
    except FileNotFoundError:
        about = "About content not available."

    return render_template('home.html', days_since=days_since, top_users=top_users, user=user, about=about, home_gif=home_gif)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id  # Store user_id in session
            return redirect(url_for('home'))
        flash("Invalid username or password")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

         # Check if the username contains spaces
        if ' ' in username:
            flash("Username cannot contain spaces. Please choose a different one.")
            return redirect(url_for('register'))

        # Check if the username already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash("Username already exists. Please choose a different one.")
            return redirect(url_for('register'))
        
        user_timezone = request.form.get('timezone', 'UTC')

        # Hash the password and create the new user
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password, timezone=user_timezone)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash("Account created successfully! Please log in.")
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.pop('user_id', None)  # Clear user_id from session
    return redirect(url_for('login'))  # Redirect to the login page

@app.route('/leaderboard')
def leaderboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']  # Get the logged-in user's ID
    user = User.query.get(user_id)  # Get the user from the database using the ID

    top_sightings = db.session.query(Sighting.user_id, func.count(Sighting.id).label('total_sightings'))\
        .group_by(Sighting.user_id).order_by(func.count(Sighting.id).desc()).limit(3).all()
    top_users = [{'user': User.query.get(user_id), 'total_sightings': total_sightings} for user_id, total_sightings in top_sightings]
    return render_template('leaderboard.html', top_users=top_users)

@app.route('/<username>')
def user_stats(username):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']  # Get the logged-in user's ID
    user = User.query.get(user_id)  # Get the user from the database using the ID
    user = User.query.filter_by(username=username).first_or_404()  # Fetch the user by username
    sightings = Sighting.query.filter_by(user_id=user.id).all()
    return render_template('user_stats.html', user=user, sightings=sightings)

@app.route('/log', methods=['GET', 'POST'])
def log_sighting():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])  # Get the logged-in user
    
    if request.method == 'POST':
        # Get the current time in system local time (simplified for local use)
        now = datetime.fromtimestamp(time.time())  # Define now in system local time

        # Create the sighting object with the local time
        sighting = Sighting(
            user_id=session['user_id'],  # Use the logged-in user's ID
            blower_user=request.form.get('blower_user'),
            blower_type=request.form.get('blower_type'),
            num_blowers=request.form.get('num_blowers'),
            location=request.form.get('location'),
            weather=request.form.get('weather'),
            noise_level=request.form.get('noise_level', type=int),
            anger_level=request.form.get('anger_level'),
            duration=request.form.get('duration'),
            datetime=now,  # Store local time
            comment=request.form.get('comment')
        )
        
        db.session.add(sighting)
        db.session.commit()
        return redirect(url_for('home'))

    return render_template('log_sighting.html', user_id=session['user_id'])

@app.route('/test_flash') #Debugging flash messages
def test_flash():
    flash("This is a test flash message.")
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
