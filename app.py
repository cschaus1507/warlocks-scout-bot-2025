from flask import Flask, request, jsonify, render_template
import requests
import json
import os
from statbotics import Statbotics  # NEW: official Statbotics client

app = Flask(__name__)

# Load TBA API Key from environment variable
TBA_AUTH_KEY = os.getenv('TBA_AUTH_KEY')
TBA_API_BASE = 'https://www.thebluealliance.com/api/v3'

# Initialize Statbotics client
sb = Statbotics()

NOTES_FILE = 'team_notes.json'
FAVORITES_FILE = 'favorites.json'

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask():
    try:
        data = request.get_json()
        user_input = data.get('team_number')

        if not user_input:
            return jsonify({'reply': "Please provide a team number or a note!"})

        if "compare" in user_input.lower():
            return compare_teams(user_input)

        if "search notes" in user_input.lower():
            return search_notes(user_input)

        if "favorite" in user_input.lower() and "unfavorite" not in user_input.lower():
            return favorite_team(user_input)

        if "unfavorite" in user_input.lower():
            return unfavorite_team(user_input)

        if "list favorites" in user_input.lower():
            return list_favorites()

        if "list notes" in user_input.lower():
            return list_notes()

        if "note:" in user_input.lower():
            return add_note(user_input)

        if "delete:" in user_input.lower():
            return delete_note(user_input)

        if "edit:" in user_input.lower():
            return edit_note(user_input)

        return team_lookup(user_input)

    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'reply': "⚠️ Sorry, something unexpected happened. Please try again."})

# --- Team Lookup and Integrations ---

def team_lookup(user_input):
    team_number = extract_team_number(user_input)
    if not team_number:
        return jsonify({'reply': "Hmm... I didn't understand that team number. Please try again!"})

    headers = {"X-TBA-Auth-Key": TBA_AUTH_KEY}
    team_url = f"{TBA_API_BASE}/team/frc{team_number}"
    team_response = requests.get(team_url, headers=headers)

    if team_response.status_code != 200:
        return jsonify({'reply': f"Sorry, I couldn't find team {team_number}. Please double check the number."})

    team_info = team_response.json()
    nickname = team_info.get('nickname', 'Unknown Nickname')
    city = team_info.get('city', 'Unknown City')
    state = team_info.get('state_prov', '')
    country = team_info.get('country', '')

    events_url = f"{TBA_API_BASE}/team/frc{team_number}/events/2025/statuses"
    events_response = requests.get(events_url, headers=headers)
    if events_response.status_code == 200:
        events_info = events_response.json()
        event_summary = generate_event_summary(events_info)
    else:
        event_summary = "I couldn't load their current season info."

    # Fetch Statbotics 2025 data
    statbotics_info = fetch_statbotics_info(team_number)
    if statbotics_info:
        epa = statbotics_info.get('epa_end', 'unknown')
        epa_rank = statbotics_info.get('epa_rank', 'unknown')
        offense_epa = statbotics_info.get('auto_epa', 'unknown')
        defense_epa = statbotics_info.get('teleop_epa', 'unknown')

        statbotics_summary = (f"📊 EPA: {epa} (Rank #{epa_rank}) | "
                              f"Auto: {offense_epa} | Teleop: {defense_epa}")
    else:
        statbotics_summary = "📊 Statbotics data not available."
        statbotics_info = None

    scout_opinion = generate_scout_opinion(team_number)
    statbotics_opinion = generate_statbotics_opinion(statbotics_info)

    notes = load_team_notes()
    team_notes = notes.get(str(team_number), [])
    notes_text = " ".join(team_notes) if team_notes else "No custom notes yet."

    reply = (f"Team {team_number} - {nickname} is from {city}, {state}, {country}. "
             f"Here’s what I found about their 2025 season: {event_summary} "
             f"Scout opinion: {scout_opinion} {statbotics_opinion} "
             f"{statbotics_summary} "
             f"Notes: {notes_text}")

    return jsonify({'reply': reply})

# --- Helper Functions ---

def fetch_statbotics_info(team_number):
    try:
        return sb.get_team_year(int(team_number), 2025)
    except Exception as e:
        print(f"Error fetching Statbotics data for team {team_number}: {e}")
        return None

def extract_team_number(text):
    numbers = ''.join(c if c.isdigit() else ' ' for c in text).split()
    if numbers:
        return numbers[0]
    return None

def generate_event_summary(events_info):
    if not events_info:
        return "No events found."
    summaries = []
    for event_key, info in events_info.items():
        try:
            event_name = info.get('event_name', 'Unknown Event')
            playoff_status = info.get('playoff', {}).get('status', 'Unknown Status')
            rank = info.get('qual', {}).get('ranking', {}).get('rank', None)
            if rank:
                summaries.append(f"At {event_name}, they ranked #{rank} and {playoff_status.lower()}.")
            else:
                summaries.append(f"At {event_name}, {playoff_status.lower()}.")
        except Exception:
            continue
    return ' '.join(summaries)

def generate_scout_opinion(team_number):
    headers = {"X-TBA-Auth-Key": TBA_AUTH_KEY}
    awards_url = f"{TBA_API_BASE}/team/frc{team_number}/awards/2025"
    awards_response = requests.get(awards_url, headers=headers)
    num_awards = len(awards_response.json()) if awards_response.status_code == 200 else 0

    opr_url = f"{TBA_API_BASE}/team/frc{team_number}/oprs/2025"
    opr_response = requests.get(opr_url, headers=headers)
    opr = 0
    if opr_response.status_code == 200:
        oprs = opr_response.json()
        opr = oprs.get(f"frc{team_number}", 0)

    opinion_parts = []

    if opr > 90:
        opinion_parts.append("They are an elite scorer.")
    elif opr > 50:
        opinion_parts.append("They have strong scoring abilities.")
    elif opr > 0:
        opinion_parts.append("They contribute valuable points to their alliances.")
    else:
        opinion_parts.append("Scoring data is limited, but they could be an underdog!")

    if num_awards >= 3:
        opinion_parts.append("They have a reputation for excellence this season.")
    elif num_awards >= 1:
        opinion_parts.append("They've picked up some awards this year.")

    return " ".join(opinion_parts)

def generate_statbotics_opinion(statbotics_info):
    if not statbotics_info:
        return ""

    epa = statbotics_info.get('epa_end', 0)
    epa_rank = statbotics_info.get('epa_rank', 9999)

    opinion = []

    if epa > 95:
        opinion.append("🚀 This team is top-tier based on EPA.")
    elif epa > 85:
        opinion.append("💪 This team has strong overall performance.")
    elif epa > 65:
        opinion.append("✅ This team is solid and reliable.")
    else:
        opinion.append("🔎 This team may be developing or improving.")

    if epa_rank <= 20:
        opinion.append("🔥 They are ranked among the top 20 teams in the world!")

    return " ".join(opinion)

# (Notes and Favorites Management would go here - same as before)

if __name__ == '__main__':
    app.run(debug=True)
