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
import pandas as pd
from collections import defaultdict

app = Flask(__name__)
app.secret_key = "It's a secret lol"
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
    all_sightings_recent = Sighting.query.all()
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
        home_gif = "celebration.gif"

    top_sightings = db.session.query(Sighting.user_id, func.count(Sighting.id).label('total_sightings'))\
        .group_by(Sighting.user_id).order_by(func.count(Sighting.id).desc()).limit(10).all()

    about = """<p>Leaf blowers can be really annoying. Whether they are so noisy that you can't focus at work or parking on the side of your house's street making it hard to get past, I'm sure we all have a gripe with them.</p>
        <br>
        <p>Personally, I have had a problem with them since I was at college. The building I lived in at school was shaped like a "U", and I was on the inside of that "U".
        The blowers would show up bright and early and the noise would echo off the walls of the building, and of course that is just a completly impossible situation to sleep in.
        Eventually, I kept getting fed up with this so I started messaging one of my friends to let him know about this situation, and it turned into a bit of an inside joke where whenever one of us saw a leaf blower, we would text that gif you can see on this page to each other.</p>
        <br>
        <p>I made this site as a silly way to track whenever you see a leaf blower, and keep tabs on when other users see a leaf blower. It provided a way for me to learn some HTML and I'm planning to use the data collected from the logs in a machine learning project (probably just linear regression lol) but it should help me get more familiar with Python too.</p>
        <br>
        <p>Thanks for checking out this website! Here is a link to the github page so you can see the code: <a href="https://github.com/cesmit27/blower_tracker" target="_blank">https://github.com/cesmit27/blower_tracker</a></p>"""


    top_users = [{'user': User.query.get(user_id), 'total_sightings': total_sightings} for user_id, total_sightings in top_sightings]

    return render_template('home.html', days_since=days_since, top_users=top_users, user=user, about=about, home_gif=home_gif, sightings=all_sightings_recent)


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

    # Fetch the top 10 users with the most sightings
    top_sightings = db.session.query(Sighting.user_id, func.count(Sighting.id).label('total_sightings'))\
        .group_by(Sighting.user_id).order_by(func.count(Sighting.id).desc()).limit(10).all()

   # For each user, fetch their sightings, sorted by datetime in descending order (most recent first)
    top_users = []
    anger_levels = defaultdict(list)  # Store anger levels for each user
    noise_levels = defaultdict(list)

    # Store users with sufficient sightings (10 or more)
    users_with_sufficient_sightings = []

    for user_id, total_sightings in top_sightings:
        sightings = Sighting.query.filter_by(user_id=user_id).order_by(Sighting.datetime.desc()).all()  # Fetch sightings for each user
        top_users.append({'user': User.query.get(user_id), 'total_sightings': total_sightings, 'sightings': sightings})

        # Collect anger and noise levels for all users, regardless of sightings count
        for sighting in sightings:
            anger_levels[user_id].append(sighting.anger_level)

        for sighting in sightings:
            noise_levels[user_id].append(sighting.noise_level)

        # Track users who have 10 or more sightings
        if len(sightings) >= 10:
            users_with_sufficient_sightings.append(user_id)

    # Calculate average anger levels for users with 10 or more sightings
    user_avg_anger = {
        user_id: sum(anger_levels[user_id]) / len(anger_levels[user_id])
        for user_id in anger_levels if user_id in users_with_sufficient_sightings
    }

    # Get the angriest user
    if user_avg_anger:
        angriest_user_id = max(user_avg_anger, key=user_avg_anger.get)
        angriest_user = User.query.get(angriest_user_id)
        angriest_user_avg_anger = round(user_avg_anger[angriest_user_id], 2)
    else:
        angriest_user = None
        angriest_user_avg_anger = None

    # Get the most chill user (least angry)
    if user_avg_anger:
        most_chill_user_id = min(user_avg_anger, key=user_avg_anger.get)
        most_chill_user = User.query.get(most_chill_user_id)
        most_chill_user_avg_anger = round(user_avg_anger[most_chill_user_id], 2)
    else:
        most_chill_user = None
        most_chill_user_avg_anger = None

    # Calculate average noise levels for users with 10 or more sightings
    user_avg_noise = {
        user_id: sum(noise_levels[user_id]) / len(noise_levels[user_id])
        for user_id in noise_levels if user_id in users_with_sufficient_sightings
    }

    # Get the noisiest user
    if user_avg_noise:
        noise_user_id = max(user_avg_noise, key=user_avg_noise.get)
        noise_user = User.query.get(noise_user_id)
        noise_user_avg_noise = round(user_avg_noise[noise_user_id], 2)
    else:
        noise_user = None
        noise_user_avg_noise = None

    # Render the template with top users, angriest user, noisiest user, and most chill user
    return render_template('leaderboard.html',
                           top_users=top_users,
                           angriest_user=angriest_user,
                           angriest_user_avg_anger=angriest_user_avg_anger,
                           noise_user=noise_user,
                           noise_user_avg_noise=noise_user_avg_noise,
                           most_chill_user=most_chill_user,
                           most_chill_user_avg_anger=most_chill_user_avg_anger)

@app.route('/<username>')
def user_logs(username):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']  # Get the logged-in user's ID
    user = User.query.get(user_id)  # Get the user from the database using the ID
    user = User.query.filter_by(username=username).first_or_404()  # Fetch the user by username

    # Fetch sightings for this user
    sightings = Sighting.query.filter_by(user_id=user.id).all()

    # Create a DataFrame from sightings
    sightings_df = pd.DataFrame([{
        'id': sighting.id,
        'datetime': sighting.datetime,
        'comment': sighting.comment,
        'anger_level': sighting.anger_level,
        'weather': sighting.weather,
        'location': sighting.location,
        'blower_user': sighting.blower_user,
        'blower_type': sighting.blower_type,
        'num_blowers': sighting.num_blowers,
        'noise_level': sighting.noise_level,
        'duration': sighting.duration
    } for sighting in sightings])

    # Convert the 'datetime' column to string first
    sightings_df['datetime'] = sightings_df['datetime'].astype(str)

    # Strip fractional seconds
    sightings_df['datetime'] = sightings_df['datetime'].apply(
        lambda x: x.split('.')[0] if '.' in x else x
    )

    # Convert back to datetime type after removing fractional seconds
    sightings_df['datetime'] = pd.to_datetime(sightings_df['datetime'], errors='coerce')

    # Extract just the date for date-specific analyses
    sightings_df['date'] = sightings_df['datetime'].dt.date

    # Drop rows with invalid datetime values (NaT)
    sightings_df = sightings_df.dropna(subset=['date'])

    # Stats Calculations
    # 1. Total Number of Blowers
    sightings_df['num_blowers'] = pd.to_numeric(sightings_df['num_blowers'])
    total_blowers = sightings_df['num_blowers'].sum()

    # 2. Time Spent Listening
    # Calculate total time in minutes
    noise_time = sightings_df['duration'].sum()

    # Constants for time conversion
    MINUTES_IN_HOUR = 60
    HOURS_IN_DAY = 24
    DAYS_IN_MONTH = 30.436875
    DAYS_IN_YEAR = 365.25

    # Convert total minutes to years, months, days, hours, and minutes
    years, remaining_minutes = divmod(noise_time, MINUTES_IN_HOUR * HOURS_IN_DAY * DAYS_IN_YEAR)
    months, remaining_minutes = divmod(remaining_minutes, MINUTES_IN_HOUR * HOURS_IN_DAY * DAYS_IN_MONTH)
    days, remaining_minutes = divmod(remaining_minutes, MINUTES_IN_HOUR * HOURS_IN_DAY)
    hours, minutes = divmod(remaining_minutes, MINUTES_IN_HOUR)

    # Build the formatted time string
    time_parts = []
    if years > 0:
        time_parts.append(f"{years:.0f} year{'s' if years != 1 else ''}")
    if months > 0:
        time_parts.append(f"{months:.0f} month{'s' if months != 1 else ''}")
    if days > 0:
        time_parts.append(f"{days:.0f} day{'s' if days != 1 else ''}")
    if hours > 0:
        time_parts.append(f"{hours:.0f} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        time_parts.append(f"{minutes:.0f} minute{'s' if minutes != 1 else ''}")

    # Combine the parts into a single string
    formatted_time = ', '.join(time_parts) if time_parts else "0 minutes"

    # 3. Avg Anger Level
    sightings_df['anger_level'] = pd.to_numeric(sightings_df['anger_level'])
    avg_angry = sightings_df['anger_level'].mean().round(2)

    # 4. Avg Noise Level
    sightings_df['noise_level'] = pd.to_numeric(sightings_df['noise_level'])
    avg_noise = sightings_df['noise_level'].mean().round(2)

    # 5. Most Common Weather Type
    weather_counts = sightings_df['weather'].value_counts().reset_index()
    weather_counts.columns = ['weather', 'count']

    # Get the row with the most common weather
    most_common_weather = weather_counts.loc[weather_counts['count'].idxmax()]

    # Extract the most common weather type and its count
    most_common_weather_type = most_common_weather['weather']
    most_common_weather_count = most_common_weather['count']

    # Create the string with the most common weather and its count
    weather_string = f"<b>Most Common Weather Type:</b> {most_common_weather_type}<br><b>Number of Times Seen:</b> {most_common_weather_count}"

    # 6. Longest Streak of Sightings
    sightings_df['streak_id'] = (sightings_df['date'] != sightings_df['date'].shift(1) + pd.Timedelta(1, 'D')).cumsum()
    streaks = sightings_df.groupby('streak_id').agg(streak_length=('date', 'count')).reset_index()
    longest_streak = streaks['streak_length'].max()

    # 7. Longest Drought (periods without sightings)
    full_dates = pd.date_range(sightings_df['date'].min(), sightings_df['date'].max(), freq='D')
    full_dates_df = pd.DataFrame(full_dates, columns=['date'])
    sightings_df['date'] = pd.to_datetime(sightings_df['date'], errors='coerce')

    missing_dates = pd.merge(full_dates_df, sightings_df[['date']], on='date', how='left', indicator=True)
    missing_dates = missing_dates[missing_dates['_merge'] == 'left_only']
    missing_dates['drought_id'] = (missing_dates['date'] != missing_dates['date'].shift(1) + pd.Timedelta(1, 'D')).cumsum()
    drought_streaks = missing_dates.groupby('drought_id').size().reset_index(name='drought_length')
    longest_drought = drought_streaks['drought_length'].max() if not drought_streaks.empty else 0

    # Return the stats page with combined data
    return render_template(
        'user_logs.html',
        user=user,
        user_id=session['user_id'],
        sightings=sightings,
        total_blowers=total_blowers,
        formatted_time=formatted_time,
        avg_angry=avg_angry,
        avg_noise=avg_noise,
        most_common_weather=most_common_weather,
        weather_string=weather_string,
        longest_streak=longest_streak,
        longest_drought=longest_drought
    )

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
