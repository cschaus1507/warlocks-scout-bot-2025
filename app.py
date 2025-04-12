from flask import Flask, request, jsonify, render_template
import requests
import json
import os

app = Flask(__name__)

# Load TBA API Key from environment variable
TBA_AUTH_KEY = os.getenv('TBA_AUTH_KEY')
TBA_API_BASE = 'https://www.thebluealliance.com/api/v3'

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

    events_url = f"{TBA_API_BASE}/team/frc{team_number}/events/2024/statuses"
    events_response = requests.get(events_url, headers=headers)
    if events_response.status_code == 200:
        events_info = events_response.json()
        event_summary = generate_event_summary(events_info)
    else:
        event_summary = "I couldn't load their current season info."

    statbotics_info = fetch_statbotics_info(team_number)
    if statbotics_info:
        epa = statbotics_info.get('epa', 'unknown')
        epa_rank = statbotics_info.get('epa_rank', 'unknown')
        offense_epa = statbotics_info.get('off_epa', 'unknown')
        defense_epa = statbotics_info.get('def_epa', 'unknown')

        statbotics_summary = (f"📊 EPA: {epa} (Rank #{epa_rank}) | "
                              f"Offense: {offense_epa} | Defense: {defense_epa}")
    else:
        statbotics_summary = "📊 Statbotics data not available."
        statbotics_info = None

    scout_opinion = generate_scout_opinion(team_number)
    statbotics_opinion = generate_statbotics_opinion(statbotics_info)

    notes = load_team_notes()
    team_notes = notes.get(str(team_number), [])
    notes_text = " ".join(team_notes) if team_notes else "No custom notes yet."

    reply = (f"Team {team_number} - {nickname} is from {city}, {state}, {country}. "
             f"Here’s what I found about their 2024 season: {event_summary} "
             f"Scout opinion: {scout_opinion} {statbotics_opinion} "
             f"{statbotics_summary} "
             f"Notes: {notes_text}")

    return jsonify({'reply': reply})

# --- Helper Functions ---

def fetch_statbotics_info(team_number):
    try:
        url = f"https://api.statbotics.io/v2/team/{team_number}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json()
    except requests.exceptions.Timeout:
        print(f"Timeout fetching Statbotics data for team {team_number}")
    except Exception as e:
        print(f"Statbotics fetch error: {e}")
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
    awards_url = f"{TBA_API_BASE}/team/frc{team_number}/awards/2024"
    awards_response = requests.get(awards_url, headers=headers)
    num_awards = len(awards_response.json()) if awards_response.status_code == 200 else 0

    opr_url = f"{TBA_API_BASE}/team/frc{team_number}/oprs/2024"
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

    epa = statbotics_info.get('epa', 0)
    epa_rank = statbotics_info.get('epa_rank', 9999)
    offense_epa = statbotics_info.get('off_epa', 0)
    defense_epa = statbotics_info.get('def_epa', 0)

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

    if offense_epa > 50:
        opinion.append("⚡ They have excellent offensive capabilities.")
    if defense_epa > 20:
        opinion.append("🛡️ They can play strong defense when needed.")

    return " ".join(opinion)

# --- Notes and Favorites Management ---

def load_team_notes():
    if not os.path.exists(NOTES_FILE):
        with open(NOTES_FILE, 'w') as f:
            json.dump({}, f)
    with open(NOTES_FILE, 'r') as f:
        return json.load(f)

def save_team_notes(notes):
    with open(NOTES_FILE, 'w') as f:
        json.dump(notes, f, indent=2)

def add_note_to_team(team_number, note):
    notes = load_team_notes()
    team_key = str(team_number)
    if team_key not in notes:
        notes[team_key] = []
    notes[team_key].append(note)
    save_team_notes(notes)

def load_favorites():
    if not os.path.exists(FAVORITES_FILE):
        with open(FAVORITES_FILE, 'w') as f:
            json.dump([], f)
    with open(FAVORITES_FILE, 'r') as f:
        return json.load(f)

def save_favorites(favorites):
    with open(FAVORITES_FILE, 'w') as f:
        json.dump(favorites, f, indent=2)

def add_favorite(team_number):
    favorites = load_favorites()
    team_key = str(team_number)
    if team_key not in favorites:
        favorites.append(team_key)
    save_favorites(favorites)

def remove_favorite(team_number):
    favorites = load_favorites()
    team_key = str(team_number)
    if team_key in favorites:
        favorites.remove(team_key)
    save_favorites(favorites)

# --- Favorite Commands ---

def favorite_team(user_input):
    team_number = extract_team_number(user_input)
    if team_number:
        add_favorite(team_number)
        return jsonify({'reply': f"⭐ Team {team_number} has been added to your favorites!"})
    else:
        return jsonify({'reply': "I couldn't find which team to favorite."})

def unfavorite_team(user_input):
    team_number = extract_team_number(user_input)
    if team_number:
        remove_favorite(team_number)
        return jsonify({'reply': f"🚫 Team {team_number} has been removed from your favorites."})
    else:
        return jsonify({'reply': "I couldn't find which team to unfavorite."})

def list_favorites():
    favorites = load_favorites()
    if favorites:
        return jsonify({'reply': f"⭐ Your favorite teams: {', '.join(favorites)}"})
    else:
        return jsonify({'reply': "You have no favorite teams yet."})

# --- Notes Commands ---

def list_notes():
    notes = load_team_notes()
    if not notes:
        return jsonify({'reply': "There are no saved notes yet."})
    team_list = ', '.join(sorted(notes.keys()))
    return jsonify({'reply': f"Teams with saved notes: {team_list}"})

def add_note(user_input):
    try:
        split_parts = user_input.split("note:")
        team_part = split_parts[0].strip()
        note_part = split_parts[1].strip()

        team_number = extract_team_number(team_part)
        if not team_number:
            return jsonify({'reply': "I couldn't figure out which team you're noting."})

        add_note_to_team(team_number, note_part)
        return jsonify({'reply': f"Got it! I saved your note for Team {team_number}."})
    except Exception:
        return jsonify({'reply': "Something went wrong while saving your note."})

def delete_note(user_input):
    try:
        split_parts = user_input.split("delete:")
        team_part = split_parts[0].strip()
        note_part = split_parts[1].strip()

        team_number = extract_team_number(team_part)
        notes = load_team_notes()
        team_key = str(team_number)

        if team_key in notes and note_part in notes[team_key]:
            notes[team_key].remove(note_part)
            if not notes[team_key]:
                del notes[team_key]
            save_team_notes(notes)
            return jsonify({'reply': f"Deleted the note for Team {team_number}."})
        else:
            return jsonify({'reply': f"I couldn't find that note for Team {team_number}."})
    except Exception:
        return jsonify({'reply': "Something went wrong while deleting the note."})

def edit_note(user_input):
    try:
        split_parts = user_input.split("edit:")
        team_part = split_parts[0].strip()
        edit_parts = split_parts[1].split("->")
        old_note = edit_parts[0].strip()
        new_note = edit_parts[1].strip()

        team_number = extract_team_number(team_part)
        notes = load_team_notes()
        team_key = str(team_number)

        if team_key in notes and old_note in notes[team_key]:
            notes[team_key].remove(old_note)
            notes[team_key].append(new_note)
            save_team_notes(notes)
            return jsonify({'reply': f"Updated the note for Team {team_number}."})
        else:
            return jsonify({'reply': f"I couldn't find that original note for Team {team_number}."})
    except Exception:
        return jsonify({'reply': "Something went wrong while editing the note. Format: '1507 edit: old note -> new note'."})

# --- Compare Command ---

def compare_teams(user_input):
    try:
        parts = user_input.lower().split("compare")[1].strip().split("vs")
        team1 = extract_team_number(parts[0])
        team2 = extract_team_number(parts[1])

        if not team1 or not team2:
            return jsonify({'reply': "I couldn't figure out which two teams to compare."})

        headers = {"X-TBA-Auth-Key": TBA_AUTH_KEY}
        opr1 = fetch_opr(team1)
        opr2 = fetch_opr(team2)

        reply = (f"Team {team1} OPR: {opr1:.1f}\n"
                 f"Team {team2} OPR: {opr2:.1f}\n")

        if opr1 > opr2:
            reply += f"🔮 Team {team1} tends to outscore Team {team2}."
        elif opr2 > opr1:
            reply += f"🔮 Team {team2} tends to outscore Team {team1}."
        else:
            reply += "🔮 These teams have similar scoring potential."

        return jsonify({'reply': reply})
    except Exception:
        return jsonify({'reply': "Something went wrong while comparing teams. Please try again!"})

def fetch_opr(team_number):
    try:
        opr_url = f"{TBA_API_BASE}/team/frc{team_number}/oprs/2024"
        headers = {"X-TBA-Auth-Key": TBA_AUTH_KEY}
        response = requests.get(opr_url, headers=headers)
        if response.status_code == 200:
            oprs = response.json()
            return oprs.get(f"frc{team_number}", 0)
    except Exception:
        return 0
    return 0

# --- Run the app ---

if __name__ == '__main__':
    app.run(debug=True)
