from flask import Flask, request, jsonify, render_template
import requests
import json
import os
from statbotics import Statbotics
import traceback
from datetime import datetime

app = Flask(__name__)

# Load API key from environment
TBA_AUTH_KEY = os.getenv('TBA_AUTH_KEY')
TBA_API_BASE = 'https://www.thebluealliance.com/api/v3'
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

        if "favorite" in user_input.lower() and "unfavorite" not in user_input.lower():
            return favorite_team(user_input)

        if "unfavorite" in user_input.lower():
            return unfavorite_team(user_input)

        if "list favorites" in user_input.lower():
            return list_favorites()

        if "note:" in user_input.lower():
            return add_note(user_input)

        if "list notes" in user_input.lower():
            return list_notes()

        return team_lookup(user_input)

    except Exception as e:
        traceback.print_exc()
        return jsonify({'reply': "⚠️ Sorry, something unexpected happened while scouting. Please try again."})

# --- Core Bot Functions ---

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

    events_list_url = f"{TBA_API_BASE}/team/frc{team_number}/events/2025"
    events_list_response = requests.get(events_list_url, headers=headers)
    events_list = events_list_response.json() if events_list_response.status_code == 200 else []

    events_status_url = f"{TBA_API_BASE}/team/frc{team_number}/events/2025/statuses"
    events_status_response = requests.get(events_status_url, headers=headers)
    events_info = events_status_response.json() if events_status_response.status_code == 200 else {}

    event_summary = generate_event_summary(events_info, events_list)

    statbotics_info = fetch_statbotics_info(team_number)

    if statbotics_info:
        epa_data = statbotics_info.get('epa', {})
        epa = epa_data.get('total_points', {}).get('mean', 'Not Available')
        epa_rank = epa_data.get('ranks', {}).get('total', {}).get('rank', 'Not Available')
        auto_epa = epa_data.get('breakdown', {}).get('auto_points', 'Not Available')
        teleop_epa = epa_data.get('breakdown', {}).get('teleop_points', 'Not Available')

        epa_summary = (
            f"\ud83d\udcca EPA Data:\n"
            f"Overall EPA: {round(epa, 1) if isinstance(epa, (int, float)) else epa} (Rank #{epa_rank})\n"
            f"Auto Phase EPA: {round(auto_epa, 1) if isinstance(auto_epa, (int, float)) else auto_epa}\n"
            f"Teleop Phase EPA: {round(teleop_epa, 1) if isinstance(teleop_epa, (int, float)) else teleop_epa}\n"
        )
    else:
        epa_summary = "\ud83d\udcca EPA Data not available."

    specialty_summary = generate_specialty_from_latest_event(team_number)

    notes = load_team_notes()
    team_notes = notes.get(str(team_number), [])
    notes_text = "\n".join(f"- {note}" for note in team_notes) if team_notes else "No custom notes yet."

    scout_opinion = generate_scout_opinion(team_number)
    statbotics_opinion = generate_statbotics_opinion(statbotics_info)

    reply = (
        f"\ud83c\udff7\ufe0f Team {team_number} - {nickname}\n"
        f"\ud83d\udccd Location: {city}, {state}, {country}\n\n"
        f"{epa_summary}\n"
        f"{specialty_summary}\n\n"
        f"\ud83d\udcdd Notes:\n{notes_text}\n\n"
        f"\ud83e\uddd0 Scout Opinion:\n{scout_opinion} {statbotics_opinion}\n\n"
        f"\ud83d\udcdc 2025 Season Summary:\n{event_summary}"
    )

    return jsonify({'reply': reply})

# --- Specialty Scoring ---

def generate_specialty_from_latest_event(team_number):
    try:
        events = sb.get_team_events(team=team_number, year=2025)
        if not events:
            return "\u2b50 Specialty Scoring data not available."

        latest_event = events[-1]
        breakdown = latest_event.get('breakdown', {})

        auto_coral = breakdown.get('auto_coral_points', 0)
        teleop_coral = breakdown.get('teleop_coral_points', 0)
        total_coral = auto_coral + teleop_coral
        barge_points = breakdown.get('barge_points', 0)
        processor_algae = breakdown.get('processor_algae_points', 0)
        endgame_points = breakdown.get('endgame_points', 0)

        specialties = []

        if total_coral > 30:
            specialties.append("\ud83e\udeb8 Coral Specialist")
        if processor_algae > 4:
            specialties.append("\ud83e\uddec Processor Algae Expert")
        if barge_points > 10:
            specialties.append("\ud83d\udea6 Strong Barge Scorer")

        if endgame_points >= 8:
            specialties.append("\ud83e\udc97 Deep Cage Climber")
        elif endgame_points >= 3:
            specialties.append("\ud83d\ude9c Shallow Cage Climber")
        else:
            specialties.append("\ud83d\udeb6\ufe0f No consistent climb detected")

        return "\u2b50 Specialty Scoring:\n" + " ".join(specialties)

    except Exception as e:
        print(f"Error generating specialty from event: {e}")
        return "\u2b50 Specialty Scoring data not available."

# --- Helper Utilities ---

def extract_team_number(text):
    numbers = ''.join(c if c.isdigit() else ' ' for c in text).split()
    return numbers[0] if numbers else None

def fetch_statbotics_info(team_number):
    try:
        return sb.get_team_year(int(team_number), 2025)
    except Exception:
        return None

def generate_event_summary(events_info, events_list):
    if not events_info:
        return "No events found."

    summaries = []
    event_key_to_name = {event['key']: event['name'] for event in events_list}

    for event_key, info in events_info.items():
        event_name = event_key_to_name.get(event_key, 'Unknown Event')
        rank = info.get('qual', {}).get('ranking', {}).get('rank', None)
        playoff_status = info.get('playoff', {}).get('status', '')

        if playoff_status == "won":
            summaries.append(f"\ud83c\udfc6 WON {event_name}!")
        elif rank:
            summaries.append(f"At {event_name}, ranked #{rank}.")
        else:
            summaries.append(f"At {event_name}, competed.")

    return ' '.join(summaries)

# --- Notes Management ---

def load_team_notes():
    if not os.path.exists(NOTES_FILE):
        with open(NOTES_FILE, 'w') as f:
            json.dump({}, f)
    with open(NOTES_FILE, 'r') as f:
        return json.load(f)

def save_team_notes(notes):
    with open(NOTES_FILE, 'w') as f:
        json.dump(notes, f, indent=2)

def add_note(user_input):
    try:
        split_parts = user_input.split("note:")
        team_part = split_parts[0].strip()
        note_text = split_parts[1].strip()

        team_number = extract_team_number(team_part)
        if not team_number:
            return jsonify({'reply': "I couldn't figure out which team you're noting."})

        notes = load_team_notes()
        team_key = str(team_number)

        if team_key not in notes:
            notes[team_key] = []
        notes[team_key].append(note_text)
        save_team_notes(notes)

        return jsonify({'reply': f"📝 Note added for Team {team_number}!"})

    except Exception:
        return jsonify({'reply': "⚠️ Something went wrong while saving your note."})

def list_notes():
    notes = load_team_notes()
    if not notes:
        return jsonify({'reply': "There are no saved notes yet."})

    output = []
    for team_key in sorted(notes.keys()):
        output.append(f"Team {team_key} has {len(notes[team_key])} notes.")

    return jsonify({'reply': "\n".join(output)})

# --- Favorites Management ---

def load_favorites():
    if not os.path.exists(FAVORITES_FILE):
        with open(FAVORITES_FILE, 'w') as f:
            json.dump([], f)
    with open(FAVORITES_FILE, 'r') as f:
        return json.load(f)

def save_favorites(favorites):
    with open(FAVORITES_FILE, 'w') as f:
        json.dump(favorites, f, indent=2)

def favorite_team(user_input):
    team_number = extract_team_number(user_input)
    if team_number:
        favorites = load_favorites()
        if team_number not in favorites:
            favorites.append(team_number)
        save_favorites(favorites)
        return jsonify({'reply': f"⭐ Team {team_number} has been added to your favorites!"})
    else:
        return jsonify({'reply': "⚠️ I couldn't find a valid team number to favorite."})

def unfavorite_team(user_input):
    team_number = extract_team_number(user_input)
    if team_number:
        favorites = load_favorites()
        if team_number in favorites:
            favorites.remove(team_number)
        save_favorites(favorites)
        return jsonify({'reply': f"🚫 Team {team_number} has been removed from your favorites."})
    else:
        return jsonify({'reply': "I couldn't find which team to unfavorite."})

def list_favorites():
    favorites = load_favorites()
    if favorites:
        return jsonify({'reply': f"⭐ Your favorite teams: {', '.join(favorites)}"})
    else:
        return jsonify({'reply': "You have no favorite teams yet."})

# --- Scout Opinion ---

def generate_scout_opinion(team_number):
    headers = {"X-TBA-Auth-Key": TBA_AUTH_KEY}
    awards_url = f"{TBA_API_BASE}/team/frc{team_number}/awards/2025"
    awards_response = requests.get(awards_url, headers=headers)
    num_awards = len(awards_response.json()) if awards_response.status_code == 200 else 0

    if num_awards >= 3:
        return "🏅 Multiple award-winning team this season."
    elif num_awards >= 1:
        return "🎖️ Recognized with at least one award."
    else:
        return "🧹 No awards yet — a true underdog story in progress."

def generate_statbotics_opinion(statbotics_info):
    if not statbotics_info:
        return ""

    try:
        epa_data = statbotics_info.get('epa', {})
        overall_epa = epa_data.get('total_points', {}).get('mean', 0)
    except Exception:
        overall_epa = 0

    if overall_epa > 95:
        return "🚀 Top-tier team with elite scoring capability."
    elif overall_epa > 85:
        return "💪 Strong team — capable of winning big matches."
    elif overall_epa > 65:
        return "✅ Reliable and solid alliance partner."
    elif overall_epa > 40:
        return "🔎 Middle-tier team — can surprise with good play."
    else:
        return "🧪 Developmental team — may be finding their stride."

if __name__ == '__main__':
    app.run(debug=True)
