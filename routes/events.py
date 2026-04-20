from flask import Blueprint, request, jsonify, session
import sqlite3
from datetime import datetime

events_bp = Blueprint('events', __name__)

def log_act(msg):
    if "user" in session:
        conn = sqlite3.connect("database.db")
        conn.execute("INSERT INTO user_activity (username, action) VALUES (?, ?)", (session["user"], msg))
        conn.commit(); conn.close()

@events_bp.route("/api/events/submit", methods=["POST"])
def submit_event():
    data = request.json
    try:
        if datetime.strptime(data["date"], "%Y-%m-%d").date() < datetime.now().date(): return jsonify({"status": "error", "message": "Cannot submit an event on a past date!"})
    except ValueError: return jsonify({"status": "error", "message": "Invalid date format."})
    organizer = data.get("organizer", session["user"]); creator = session["user"]
    conn = sqlite3.connect("database.db"); c = conn.cursor()
    c.execute("INSERT INTO events (title, description, date, time, location, category, organizer, status, creator, registration_link) VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending', ?, ?)", (data["title"], data["desc"], data["date"], data["time"], data["location"], data["category"], organizer, creator, data.get("reg_link", "")))
    conn.commit(); conn.close(); log_act(f"Proposed event: {data['title']}"); return jsonify({"status": "success", "message": "Event submitted! Waiting for Admin approval."})

@events_bp.route("/api/events/owner_action", methods=["POST"])
def owner_event_action():
    event_id = request.json["id"]; action = request.json["action"]; user = session["user"]
    conn = sqlite3.connect("database.db"); c = conn.cursor(); c.execute("SELECT creator FROM events WHERE id=?", (event_id,)); ev = c.fetchone()
    if ev and ev[0] == user:
        if action == 'completed': c.execute("UPDATE events SET status='Completed' WHERE id=?", (event_id,))
        elif action == 'cancel': c.execute("DELETE FROM events WHERE id=? AND status='Pending'", (event_id,))
        conn.commit(); conn.close(); return jsonify({"status": "success", "message": f"Event marked as {action.capitalize()}!"})
    conn.close(); return jsonify({"status": "error", "message": "Unauthorized."})

@events_bp.route("/api/events/rsvp", methods=["POST"])
def rsvp_event():
    event_id = request.json["id"]; user = session["user"]; conn = sqlite3.connect("database.db"); c = conn.cursor()
    c.execute("SELECT id FROM event_rsvps WHERE student_name=? AND event_id=?", (user, event_id))
    if not c.fetchone():
        c.execute("INSERT INTO event_rsvps (student_name, event_id) VALUES (?, ?)")
        c.execute("UPDATE events SET rsvp_count = rsvp_count + 1 WHERE id=?", (event_id,))
        conn.commit()
    conn.close(); log_act("RSVP'd to an event"); return jsonify({"status": "success"})