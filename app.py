from flask import Flask, request, jsonify, render_template
import requests
import json
import os
from datetime import datetime
from statbotics import Statbotics
import traceback

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

        # --- IMPORTANT: Check more specific commands first ---
        if "compare" in user_input.lower():
            return compare_teams(user_input)

        if "search notes" in user_input.lower():
            return search_notes(user_input)

        if "list favorites" in user_input.lower():
            return list_favorites()

        if "list notes" in user_input.lower():
            return list_notes()

        if "unfavorite" in user_input.lower():
            return unfavorite_team(user_input)

        if "favorite" in user_input.lower():
            return favorite_team(user_input)

        if "delete note" in user_input.lower():
            return delete_note(user_input)

        if "edit note" in user_input.lower():
            return edit_note(user_input)

        if "note" in user_input.lower():
            return add_note(user_input)

        # Default: treat input as team lookup
        return team_lookup(user_input)

    except Exception as e:
        traceback.print_exc()
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

    # --- EPA Summary
    if statbotics_info:
        epa_data = statbotics_info.get('epa', {})
        epa = epa_data.get('total_points', {}).get('mean', 'Not Available')
        epa_rank = epa_data.get('ranks', {}).get('total', {}).get('rank', 'Not Available')
        auto_epa = epa_data.get('breakdown', {}).get('auto_points', 'Not Available')
        teleop_epa = epa_data.get('breakdown', {}).get('teleop_points', 'Not Available')

        epa_summary = (
            f"📊 EPA Data:\n"
            f"Overall EPA: {round(epa, 1) if isinstance(epa, (int, float)) else epa} (Rank #{epa_rank})\n"
            f"Auto Phase EPA: {round(auto_epa, 1) if isinstance(auto_epa, (int, float)) else auto_epa}\n"
            f"Teleop Phase EPA: {round(teleop_epa, 1) if isinstance(teleop_epa, (int, float)) else teleop_epa}\n"
        )
    else:
        epa_summary = "📊 EPA Data not available."

    # Fetch Last Event Statistics (NEW)
    last_event_stats = generate_last_event_statistics(team_number)

    # --- Load notes
    notes = load_team_notes()
    team_notes = notes.get(str(team_number), [])
    notes_text = "\n".join(f"- {note['text']} (added {note['timestamp']})" for note in team_notes) if team_notes else "No custom notes yet."

    # --- Generate scouting opinion
    scout_opinion = generate_scout_opinion(team_number)
    statbotics_opinion = generate_statbotics_opinion(statbotics_info)

    reply = (
        f"🏷️ Team {team_number} - {nickname}\n"
        f"📍 Location: {city}, {state}, {country}\n\n"
        
        f"{epa_summary}\n\n"
        
        f"{last_event_stats}\n\n"
        
        f"📝 Notes:\n"
        f"{notes_text}\n\n"
        
        f"🧠 Scout Opinion:\n"
        f"{scout_opinion} {statbotics_opinion}\n\n"
        
        f"📜 2025 Season Summary:\n"
        f"{event_summary}"
    )

    return jsonify({'reply': reply})

# --- Helper Functions ---

def extract_team_number(text):
    numbers = ''.join(c if c.isdigit() else ' ' for c in text).split()
    for num in numbers:
        if len(num) >= 3:
            return num
    return None

def generate_event_summary(events_info, events_list):
    if not events_info:
        return "No events found."

    summaries = []
    event_key_to_name = {event['key']: event['name'] for event in events_list}

    for event_key, info in events_info.items():
        try:
            event_name = event_key_to_name.get(event_key, 'Unknown Event')
            rank = info.get('qual', {}).get('ranking', {}).get('rank', None)
            playoff_status = info.get('playoff', {}).get('status', '')

            if playoff_status == "won":
                summaries.append(f"🏆 WON {event_name}!")
            elif rank:
                summaries.append(f"At {event_name}, they ranked #{rank}.")
            else:
                summaries.append(f"At {event_name}, they competed.")
        except Exception:
            continue
    return ' '.join(summaries)

def fetch_statbotics_info(team_number):
    try:
        data = sb.get_team_year(int(team_number), 2025)
        return data
    except Exception as e:
        print(f"Error fetching Statbotics data for team {team_number}: {e}")
        return None

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
        epa_rank = epa_data.get('ranks', {}).get('total', {}).get('rank', 9999)
        auto_epa = epa_data.get('breakdown', {}).get('auto_points', 0)
        teleop_epa = epa_data.get('breakdown', {}).get('teleop_points', 0)

        # Specialty stats
        auto_coral = epa_data.get('breakdown', {}).get('auto_coral_points', 0)
        teleop_coral = epa_data.get('breakdown', {}).get('teleop_coral_points', 0)
        total_coral = auto_coral + teleop_coral

        processor_algae = epa_data.get('breakdown', {}).get('processor_algae_points', 0)
        net_algae = epa_data.get('breakdown', {}).get('net_algae_points', 0)
        barge_points = epa_data.get('breakdown', {}).get('barge_points', 0)

    except Exception:
        overall_epa = 0
        epa_rank = 9999
        auto_epa = 0
        teleop_epa = 0
        total_coral = 0
        processor_algae = 0
        net_algae = 0
        barge_points = 0

    opinion_parts = []

    # EPA strength
    if overall_epa > 95:
        opinion_parts.append("🚀 Top-tier team with elite scoring capability.")
    elif overall_epa > 85:
        opinion_parts.append("💪 Strong team — capable of winning big matches.")
    elif overall_epa > 65:
        opinion_parts.append("✅ Reliable and solid alliance partner.")
    elif overall_epa > 40:
        opinion_parts.append("🔎 Middle-tier team — can surprise with good play.")
    else:
        opinion_parts.append("🧪 Developmental team — may be finding their stride.")

    # Top 20
    if epa_rank <= 20:
        opinion_parts.append("🔥 Ranked among the top 20 worldwide — elite company!")

    # Auto strength
    if auto_epa > 20:
        opinion_parts.append("⚡ Excellent autonomous routine — fast starter!")
    elif auto_epa > 12:
        opinion_parts.append("⚙️ Solid and consistent auto.")

    # Teleop strength
    if teleop_epa > 35:
        opinion_parts.append("🎯 High teleop scoring threat — dominates midgame.")
    elif teleop_epa > 20:
        opinion_parts.append("🏹 Good teleop contributor.")

    # Coral Specialist
    if total_coral > 50:
        opinion_parts.append("🪸 Coral Specialist — dominates coral scoring!")

    # Algae Master
    if processor_algae > 5 or net_algae > 8:
        opinion_parts.append("🧪 Algae Handling Expert!")

    # Barge Dominator
    if barge_points > 15:
        opinion_parts.append("🛶 Barge Scoring Specialist!")

    return " ".join(opinion_parts)
    
def generate_last_event_statistics(team_number):
    try:
        headers = {
            "X-TBA-Auth-Key": TBA_AUTH_KEY
        }

        # Step 1: Pull events
        events_url = f"{TBA_API_BASE}/team/frc{team_number}/events/2025/simple"
        events_response = requests.get(events_url, headers=headers)
        events_response.raise_for_status()
        events = events_response.json()

        if not events:
            return "⭐ Last Event Statistics data not available."

        # Find latest event
        latest_event = sorted(events, key=lambda e: e.get('end_date', ''))[-1]
        event_key = latest_event.get('key')

        if not event_key:
            return "⭐ Last Event Statistics data not available."

        # Step 2: Pull matches
        matches_url = f"{TBA_API_BASE}/event/{event_key}/matches"
        matches_response = requests.get(matches_url, headers=headers)
        matches_response.raise_for_status()
        matches = matches_response.json()

        if not matches:
            return "⭐ Last Event Statistics data not available."

        # Initialize totals
        total_auto_coral = 0
        total_teleop_coral = 0
        total_algae_processor = 0
        total_barge_algae = 0
        match_count = 0

        for match in matches:
            alliances = match.get('alliances', {})
            blue = alliances.get('blue', {})
            red = alliances.get('red', {})

            found_team = False
            breakdown = {}

            if f"frc{team_number}" in blue.get('team_keys', []):
                breakdown = blue.get('score_breakdown', {})
                found_team = True
            elif f"frc{team_number}" in red.get('team_keys', []):
                breakdown = red.get('score_breakdown', {})
                found_team = True

            if not found_team or not breakdown:
                continue

            total_auto_coral += breakdown.get('autoCoralPoints', 0)
            total_teleop_coral += breakdown.get('teleopCoralPoints', 0)
            total_algae_processor += breakdown.get('algaePoints', 0)
            total_barge_algae += breakdown.get('endGameBargePoints', 0)

            match_count += 1

        if match_count == 0:
            return "⭐ Last Event Statistics data not available."

        # Calculate averages
        avg_coral = (total_auto_coral + total_teleop_coral) / match_count
        avg_processor_algae = total_algae_processor / match_count
        avg_barge_algae = total_barge_algae / match_count

        # Format the output nicely
        stats_report = (
            f"📊 Last Event Statistics:\n"
            f"• Average Coral Points: {avg_coral:.1f}\n"
            f"• Average Processor Algae Points: {avg_processor_algae:.1f}\n"
            f"• Average Barge Algae Points: {avg_barge_algae:.1f}\n"
        )

        return stats_report

    except Exception as e:
        print(f"Error generating last event stats: {e}")
        return "⭐ Last Event Statistics data not available."

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
        return jsonify({'reply': "⚠️ I couldn't find a valid team number to favorite."})

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
        return jsonify({'reply': "⭐ Your favorite teams:\n" + "\n".join(favorites)})
    else:
        return jsonify({'reply': "You have no favorite teams yet."})

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

def add_note_to_team(team_number, note_text):
    notes = load_team_notes()
    team_key = str(team_number)
    timestamp = datetime.now().strftime("%Y-%m-%d")
    if team_key not in notes:
        notes[team_key] = []
    notes[team_key].append({"text": note_text, "timestamp": timestamp})
    save_team_notes(notes)

def add_note(user_input):
    try:
        if "note:" in user_input.lower():
            split_parts = user_input.split("note:")
        elif "note" in user_input.lower():
            split_parts = user_input.split("note")
        else:
            return jsonify({'reply': "⚠️ Please type 'note:' followed by team number and your note."})

        team_part = split_parts[0].strip()
        note_text = split_parts[1].strip()

        team_number = extract_team_number(team_part)
        if not team_number:
            team_number = extract_team_number(note_text)

        if not team_number:
            return jsonify({'reply': "⚠️ I still couldn't figure out which team you're noting. Please try again."})

        cleaned_note_text = " ".join([word for word in note_text.split() if not word.isdigit()])

        add_note_to_team(team_number, cleaned_note_text)
        return jsonify({'reply': f"📝 Note added for Team {team_number}!"})
    except Exception:
        return jsonify({'reply': "⚠️ Something went wrong while saving your note."})

def generate_notes_display(team_number):
    notes = load_team_notes()
    team_key = str(team_number)
    if team_key not in notes or not notes[team_key]:
        return "No custom notes yet."

    output = []
    for idx, note in enumerate(notes[team_key], 1):
        output.append(f"{idx}. {note['text']} (added {note['timestamp']})")
    return "\n".join(output)

def list_notes():
    notes = load_team_notes()
    if not notes:
        return jsonify({'reply': "There are no saved notes yet."})
    output = []
    for team_key in sorted(notes.keys()):
        output.append(f"Team {team_key} has {len(notes[team_key])} notes.")
    return jsonify({'reply': "\n".join(output)})

def delete_note(user_input):
    try:
        split_parts = user_input.split("delete note")
        team_part = split_parts[1].strip()
        parts = team_part.split()
        note_index = int(parts[0]) - 1
        team_number = extract_team_number(" ".join(parts[2:]))

        notes = load_team_notes()
        team_key = str(team_number)

        if team_key in notes and 0 <= note_index < len(notes[team_key]):
            deleted_note = notes[team_key].pop(note_index)
            if not notes[team_key]:
                del notes[team_key]
            save_team_notes(notes)
            return jsonify({'reply': f"🗑️ Deleted note: \"{deleted_note['text']}\" for Team {team_number}."})
        else:
            return jsonify({'reply': "Couldn't find that note to delete."})
    except Exception:
        return jsonify({'reply': "Something went wrong while deleting the note."})

def edit_note(user_input):
    try:
        split_parts = user_input.split("edit note")
        team_part = split_parts[1].strip()
        parts = team_part.split("->")
        left = parts[0].strip().split()
        note_index = int(left[0]) - 1
        team_number = extract_team_number(" ".join(left[2:]))

        new_text = parts[1].strip()

        notes = load_team_notes()
        team_key = str(team_number)

        if team_key in notes and 0 <= note_index < len(notes[team_key]):
            notes[team_key][note_index]["text"] = new_text
            notes[team_key][note_index]["timestamp"] = datetime.now().strftime("%Y-%m-%d")
            save_team_notes(notes)
            return jsonify({'reply': f"✏️ Edited note for Team {team_number}."})
        else:
            return jsonify({'reply': "Couldn't find that note to edit."})
    except Exception:
        return jsonify({'reply': "Something went wrong while editing the note."})

if __name__ == '__main__':
    app.run(debug=True)
