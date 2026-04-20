from flask import Blueprint, request, jsonify, session
import sqlite3
from datetime import datetime

rooms_bp = Blueprint('rooms', __name__)

def log_act(msg):
    if "user" in session:
        conn = sqlite3.connect("database.db")
        conn.execute("INSERT INTO user_activity (username, action) VALUES (?, ?)", (session["user"], msg))
        conn.commit(); conn.close()

@rooms_bp.route("/api/rooms/check")
def check_rooms():
    date, time = request.args.get("date"), request.args.get("time")
    conn = sqlite3.connect("database.db"); c = conn.cursor()
    rooms = c.execute("SELECT room_name, status FROM rooms").fetchall()
    booked = [r[0] for r in c.execute("SELECT room_name FROM room_bookings WHERE booking_date=? AND time_slot=? AND status NOT IN ('Rejected', 'Completed')", (date, time)).fetchall()]
    conn.close()
    return jsonify([{"name": r[0], "type": r[1], "status": "Occupied" if r[0] in booked else "Available"} for r in rooms])

@rooms_bp.route("/api/rooms/book", methods=["POST"])
def book_room():
    data = request.json; u = session["user"]; booking_date = datetime.strptime(data["date"], "%Y-%m-%d").date(); today = datetime.now().date()
    if (booking_date - today).days < 0: return jsonify({"status": "error", "message": "Cannot book in the past!"})
    if (booking_date - today).days > 2: return jsonify({"status": "error", "message": "Max 48 hours in advance."})
    conn = sqlite3.connect("database.db"); c = conn.cursor()
    c.execute("SELECT id FROM room_bookings WHERE student_name=? AND booking_date >= ? AND status NOT IN ('Rejected', 'Completed')", (u, today.strftime("%Y-%m-%d")))
    if c.fetchone(): conn.close(); return jsonify({"status": "error", "message": "You already have an active room booking."})
    c.execute("INSERT INTO room_bookings (room_name, student_name, booking_date, time_slot, status) VALUES (?, ?, ?, ?, 'Pending')", (data["room"], u, data["date"], data["time"]))
    conn.commit(); conn.close(); log_act(f"Booked room {data['room']}")
    return jsonify({"status": "success", "message": "Room requested! Waiting for Admin approval."})

@rooms_bp.route("/api/rooms/cancel", methods=["POST"])
def cancel_booking():
    data = request.json; user = session["user"]; conn = sqlite3.connect("database.db"); c = conn.cursor()
    c.execute("SELECT booking_date, time_slot FROM room_bookings WHERE id=? AND student_name=?", (data["id"], user)); booking = c.fetchone()
    if not booking: conn.close(); return jsonify({"status": "error", "message": "Booking not found."})
    start_datetime = datetime.strptime(f"{booking[0]} {booking[1].split(' - ')[0]}", "%Y-%m-%d %I:%M %p")
    if (start_datetime - datetime.now()).total_seconds() < 1800: conn.close(); return jsonify({"status": "error", "message": "Too late! You cannot cancel a room within 30 minutes of the start time."})
    c.execute("DELETE FROM room_bookings WHERE id=? AND student_name=?", (data["id"], user)); conn.commit(); conn.close()
    return jsonify({"status": "success", "message": "Booking canceled successfully!"})

@rooms_bp.route("/api/rooms/complete", methods=["POST"])
def complete_booking():
    conn = sqlite3.connect("database.db"); c = conn.cursor(); c.execute("UPDATE room_bookings SET status='Completed' WHERE id=? AND student_name=?", (request.json["id"], session["user"])); conn.commit(); conn.close(); return jsonify({"status": "success", "message": "Room marked as Completed!"})