from flask import Flask, request, jsonify, render_template
import requests
import json
import os
from statbotics import Statbotics

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
        print(f"Unexpected error inside /ask: {e}")
        return jsonify({'reply': "⚠️ Sorry, something unexpected happened while scouting. Please try again."})

# --- Team Lookup and Integrations ---

def team_lookup(user_input):
    team_number = extract_team_number(user_input)
    if not team_number:
        return jsonify({'reply': "Hmm... I didn't understand that team number. Please try again!"})

    headers = {"X-TBA-Auth-Key": TBA_AUTH_KEY}

    # Pull team general info
    team_url = f"{TBA_API_BASE}/team/frc{team_number}"
    team_response = requests.get(team_url, headers=headers)

    if team_response.status_code != 200:
        return jsonify({'reply': f"Sorry, I couldn't find team {team_number}. Please double check the number."})

    team_info = team_response.json()
    nickname = team_info.get('nickname', 'Unknown Nickname')
    city = team_info.get('city', 'Unknown City')
    state = team_info.get('state_prov', '')
    country = team_info.get('country', '')

    # Pull event names
    events_list_url = f"{TBA_API_BASE}/team/frc{team_number}/events/2025"
    events_list_response = requests.get(events_list_url, headers=headers)
    events_list = events_list_response.json() if events_list_response.status_code == 200 else []

    # Pull event statuses
    events_status_url = f"{TBA_API_BASE}/team/frc{team_number}/events/2025/statuses"
    events_status_response = requests.get(events_status_url, headers=headers)
    events_info = events_status_response.json() if events_status_response.status_code == 200 else {}

    event_summary = generate_event_summary(events_info, events_list)

    # Pull Statbotics data
    statbotics_info = fetch_statbotics_info(team_number)
    if statbotics_info:
        epa_data = statbotics_info.get('epa', {})
        epa = epa_data.get('total_points', {}).get('mean', 'Not Available')
        epa_rank = epa_data.get('ranks', {}).get('total', {}).get('rank', 'Not Available')
        auto_epa = epa_data.get('breakdown', {}).get('auto_points', 'Not Available')
        teleop_epa = epa_data.get('breakdown', {}).get('teleop_points', 'Not Available')

        statbotics_summary = (
            f"\ud83d\udcca Overall EPA: {round(epa, 1) if isinstance(epa, (int, float)) else epa} (Rank #{epa_rank})\n"
            f"\ud83d\ude80 Auto Points EPA: {round(auto_epa, 1) if isinstance(auto_epa, (int, float)) else auto_epa}\n"
            f"\ud83c\udf39 Teleop Points EPA: {round(teleop_epa, 1) if isinstance(teleop_epa, (int, float)) else teleop_epa}"
        )
    else:
        statbotics_summary = "\ud83d\udcca Statbotics data not available."

    notes = load_team_notes()
    team_notes = notes.get(str(team_number), [])
    notes_text = " ".join(team_notes) if team_notes else "No custom notes yet."

    scout_opinion = generate_scout_opinion(team_number)
    statbotics_opinion = generate_statbotics_opinion(statbotics_info)

    reply = (
        f"Team {team_number} - {nickname} is from {city}, {state}, {country}.\n\n"
        f"\ud83c\udfc6 2025 Season Summary:\n{event_summary}\n\n"
        f"{statbotics_summary}\n\n"
        f"\ud83d\udcdd Notes:\n{notes_text}\n\n"
        f"\ud83e\udde0 Scout Opinion:\n{scout_opinion} {statbotics_opinion}"
    )

    return jsonify({'reply': reply})

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
        return jsonify({'reply': "Something went wrong while editing the note."})

# --- Main ---

if __name__ == '__main__':
    app.run(debug=True)

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

if __name__ == '__main__':
    app.run(debug=True)
