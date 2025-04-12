# Warlocks Scout Bot

Welcome to the **Warlocks Scout Bot** — an advanced conversational chatbot designed to help FRC teams scout, research, and organize team data in real-time!

Built by the Warlocks (FRC Team 1507), this bot integrates with **The Blue Alliance** and **Statbotics.io** to provide comprehensive team insights.

---

## 🚀 Features

- 🔎 **Look up any FIRST Robotics team** — fetches real-time data from TBA and Statbotics
- 🛡️ **Scout Opinion Generator** — rates teams based on EPA, OPR, and awards
- 📊 **EPA / Offensive / Defensive Stats** — shown automatically
- 🔥 **Highlight Top 20 Teams** — world-class teams get a fire emoji
- 📝 **Save, Edit, and Delete Custom Notes** — keep personal scouting observations
- ⭐ **Favorite Teams** — track your top teams for alliance selection
- 🛠 **Compare Two Teams** — side-by-side stat comparison
- 🕵️ **Search Notes by Keyword** — find teams with key skills (e.g., defense)

---

## 🛠 Technologies Used

- Python 3
- Flask (backend framework)
- Gunicorn (for production WSGI server)
- HTML, CSS, JavaScript (frontend)
- The Blue Alliance API
- Statbotics.io API
- Hosted on Render.com

---

## 📦 How to Run Locally

1. Clone the repository:
    ```bash
    git clone https://github.com/YOUR-USERNAME/warlocks-scout-bot.git
    cd warlocks-scout-bot
    ```

2. Install dependencies:
    ```bash
    pip install Flask requests gunicorn
    ```

3. Run the application:
    ```bash
    python app.py
    ```

4. Open your browser and visit:
    ```
    http://localhost:5000
    ```

---

## 📂 Project Structure

