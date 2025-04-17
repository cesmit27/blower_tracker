import os
import sqlite3
import datetime
import pytz
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from atproto import Client, models
import logging
import tempfile
from datetime import timedelta
from PIL import Image
from dotenv import load_dotenv

# ------------------------------
# Configuration & Logging Setup
# ------------------------------
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

logging.basicConfig(level=logging.INFO)
db_path = "/home/BlowerTracker/blower_tracker/leaf_blower.db"

# ------------------------------
# Login to Bluesky Account
# ------------------------------
email = os.getenv('BLUESKY_EMAIL')
password = os.getenv('BLUESKY_PASSWORD')
client = Client()
client.login(email, password)

# ------------------------------
# Time Zone and Date Calculations
# ------------------------------
utc = pytz.utc
eastern = pytz.timezone('America/New_York')

# Get current time in UTC and convert to Eastern Time
now_utc = datetime.datetime.now(utc)
now_et = now_utc.astimezone(eastern)

# Define "today" and "yesterday" in Eastern Time (for the daily report, as myself and all users are eastern time)
today_start_et = now_et.replace(hour=0, minute=0, second=0, microsecond=0)
yesterday_start_et = today_start_et - timedelta(days=1)

# Convert boundaries to UTC for querying (The db in question is UTC)
today_start_utc = today_start_et.astimezone(utc)
yesterday_start_utc = yesterday_start_et.astimezone(utc)

# ------------------------------
# Fetch Yesterday's Data for Daily Stats
# ------------------------------
try:
    with sqlite3.connect(db_path) as conn:
        daily_query = """
            SELECT sightings.*, users.username
            FROM sightings
            LEFT JOIN users ON sightings.user_id = users.id
            WHERE sightings.datetime >= ? AND sightings.datetime < ?
        """
        daily_data = pd.read_sql_query(daily_query, conn, params=(yesterday_start_utc, today_start_utc))
except sqlite3.Error as e:
    logging.error(f"Database connection error: {e}")
    exit(1)

# ------------------------------
# Functions
# ------------------------------
def format_dict(d): # This is for counting up the blower types in the stats text
    return ", ".join(f"{k}: {v}" for k, v in d.items())

def generate_stats_text(df, period):
    """
    Generate the daily stats text. If no sightings occurred yesterday,
    the text explicitly states that.
    """
    #Windows vs Mac/Linux formatting
    if os.name == 'nt':
        yesterday_date = yesterday_start_et.strftime("%B %#d, %Y")
    else:
        yesterday_date = yesterday_start_et.strftime("%B %-d, %Y")

    if df.empty:
        return f"📈 Blower Report for {yesterday_date} 📉\nThere were no blower sightings yesterday!"

    total_sightings = len(df)

    if total_sightings == 1:
        # Use actual values for a single sighting
        noise_level = int(df['noise_level'].iloc[0])
        anger_level = int(df['anger_level'].iloc[0])
        duration = int(df['duration'].iloc[0])
    else:
        # Use averages for multiple sightings
        noise_level = pd.to_numeric(df['noise_level'], errors='coerce').mean()
        anger_level = pd.to_numeric(df['anger_level'], errors='coerce').mean()
        duration = pd.to_numeric(df['duration'], errors='coerce').mean()

    blower_types = format_dict(df['blower_type'].value_counts().to_dict())
    num_blowers = df['num_blowers'].sum()
    usernames = ", ".join(df['username'].unique())

    stats_text = (
        f"📈 Blower Report for {yesterday_date} 📉\n"
        f"Total Sightings: {total_sightings} (Reported by {usernames})\n"
        f"Number of Individual Blowers: {num_blowers}\n"
        f"Blower Types: [{blower_types}]\n"
    )

    if total_sightings == 1:
        stats_text += (
            f"Noise Level: {noise_level}/10\n"
            f"Anger Level: {anger_level}/10\n"
            f"Duration: {duration} mins\n"
        )
    else:
        stats_text += (
            f"Avg Noise Level: {int(noise_level)}/10\n"
            f"Avg Anger Level: {int(anger_level)}/10\n"
            f"Avg Duration: {int(duration)} mins\n"
        )
    return stats_text

def generate_line_chart(client, db_path, title, total_sightings):
    """
    Generate a line chart showing the number of sightings per day over the previous week.
    This chart is generated even if there were no sightings yesterday.
    """
    # Calculate the previous week's boundaries in Eastern Time cause thats where the users are
    first_day_current_week_et = now_et.replace(hour=0, minute=0, second=0, microsecond=0)
    last_day_previous_week_et = first_day_current_week_et - timedelta(days=1)
    first_day_previous_week_et = last_day_previous_week_et - timedelta(days=6)
    # Ensure the last day covers the whole day
    last_day_previous_week_et = last_day_previous_week_et.replace(hour=23, minute=59, second=59, microsecond=999999)

    # Convert these to UTC for querying, since the db server is on UTC
    first_day_previous_week_utc = first_day_previous_week_et.astimezone(utc)
    last_day_previous_week_utc = last_day_previous_week_et.astimezone(utc)

    # Query
    try:
        with sqlite3.connect(db_path) as conn:
            weekly_query = """
                SELECT *
                FROM sightings
                WHERE datetime >= ? AND datetime <= ?
            """
            weekly_df = pd.read_sql_query(weekly_query, conn, params=(first_day_previous_week_utc, last_day_previous_week_utc)) # The params fill the "?" in the SQL query. Now I know!!!
    except sqlite3.Error as e:
        logging.error(f"Database connection error during weekly query: {e}")
        return None

    # Process the datetime information
    if not weekly_df.empty and 'datetime' in weekly_df.columns:
        # Convert to datetime
        weekly_df['datetime'] = pd.to_datetime(weekly_df['datetime']).dt.floor('s') #Floor removes those nasty fractional seconds

        # Convert to Eastern Time (That's where all the users are). This fixed an issue with some days having their sightings attributed to the next day.
        weekly_df['datetime'] = weekly_df['datetime'].dt.tz_localize(utc).dt.tz_convert(eastern)

        weekly_df['date'] = weekly_df['datetime'].dt.date

        # Group by date to count the number of sightings per day
        daily_counts = weekly_df.groupby('date').size().reset_index(name='count')
        print(daily_counts)#print statement was for debugging
    else:
        daily_counts = pd.DataFrame(columns=['date', 'count'])


    # Create a complete date range for the previous week (7 days)
    date_range = pd.date_range(start=first_day_previous_week_et.date(), end=last_day_previous_week_et.date(), freq='D')
    daily_counts = daily_counts.set_index('date').reindex(date_range.date, fill_value=0).reset_index()
    daily_counts.rename(columns={'index': 'date'}, inplace=True)

    # Update the count for the specific date with total_sightings
    if total_sightings > 0:
        # Find the row corresponding to the last day of the previous week
        daily_counts.loc[daily_counts['date'] == last_day_previous_week_et.date(), 'count'] = total_sightings

    # Debugging issue of attributing sightings to the wrong day
    print("Final Daily Counts:")
    print(daily_counts)

    # Format the date range string for the title.
    if os.name == 'nt':  # Windows
        first_date_formatted = first_day_previous_week_et.strftime('%b %#d, %Y')
        last_date_formatted = last_day_previous_week_et.strftime('%b %#d, %Y')
        date_format = '%b %#d' # For x-axis ticks
    else:   # Mac/Linux. This doesn't seem to be necessary but I put it just in case
        first_date_formatted = first_day_previous_week_et.strftime('%b %-d, %Y')
        last_date_formatted = last_day_previous_week_et.strftime('%b %-d, %Y')
        date_format = '%b %-d' #F or x-axis ticks
    date_range_str = f"{first_date_formatted} - {last_date_formatted}"

    # Plot the line graph
    plt.figure(figsize=(8, 8))  # Square figure size (8x8 inches)
    sns.set_theme(style="darkgrid", palette="husl")

    # Create the line plot
    ax = sns.lineplot(
        x='date',
        y='count',
        data=daily_counts,
        marker='o',
        linewidth=3,
        markersize=10,
        color='#4C72B0',  # Blue color for the line
        markerfacecolor='#FF6F61',  # Coral color for markers
    )

    # Add labels and title
    plt.xlabel('Date', fontsize=12, fontweight='bold', labelpad=10)
    plt.ylabel('Number of Sightings', fontsize=12, fontweight='bold', labelpad=10)
    plt.title(f'{title} ({date_range_str})', fontsize=14, fontweight='bold', pad=15)

    # Set y-axis to only show whole numbers
    plt.gca().yaxis.set_major_locator(plt.MaxNLocator(integer=True))

    # Format x-axis dates for better readability
    plt.gca().xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter(date_format))

    # Ensure the x-axis has exactly 7 ticks (one for each day of the previous week)
    plt.gca().xaxis.set_major_locator(plt.MaxNLocator(7))

    # Add gridlines for better readability
    plt.grid(True, linestyle='--', alpha=0.95)

    # Set background colors
    ax.set_facecolor('#F0F0F0')  # Light gray background
    plt.gcf().set_facecolor('#FFFFFF')  # White figure background

    # Adjust layout with padding
    plt.tight_layout(rect=[0.05, 0.05, 0.95, 0.95])  # Add 5% padding on all sides, deals with the title and axis names getting slightly cut off the image

    # Save the figure to a temporary file
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
        try:
            plt.savefig(tmp_file.name, bbox_inches='tight', pad_inches=0.1, dpi=100)  # Add 0.1 inches of padding
            plt.close()

            # Open the saved image with Pillow to remove metadata
            with Image.open(tmp_file.name) as img:
                stripped_tmp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
                img.save(stripped_tmp_file.name, format='PNG', optimize=True)

            # Upload the stripped image
            with open(stripped_tmp_file.name, "rb") as file:
                upload_response = client.upload_blob(file.read())
        finally:
            #  Get rid of the temporary files
            os.unlink(tmp_file.name)
            os.unlink(stripped_tmp_file.name)

    return models.AppBskyEmbedImages.Image(image=upload_response.blob, alt='')

# ------------------------------
# Main Posting Logic
# ------------------------------
# Generate the daily stats text (this will mention if there were no sightings yesterday)
daily_text = generate_stats_text(daily_data, "Daily")

# Get the total_sightings value from daily_data, this is a fix for an issue with the daily_counts variable in the function that generates the line chart. Occasionaly it wouldn't count the correct amount of sightings
total_sightings = len(daily_data)

# Always generate the weekly line chart image.
line_chart = generate_line_chart(client, db_path, 'Number of Sightings per Day', total_sightings)

if line_chart:
    embed = models.AppBskyEmbedImages.Main(images=[line_chart])
    client.send_post(daily_text, embed=embed)
else:
    client.send_post(daily_text)

logging.info("Post successful!")