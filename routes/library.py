from flask import Blueprint, request, jsonify, session
import sqlite3
from datetime import datetime

library_bp = Blueprint('library', __name__)

def log_act(msg):
    if "user" in session:
        conn = sqlite3.connect("database.db")
        conn.execute("INSERT INTO user_activity (username, action) VALUES (?, ?)", (session["user"], msg))
        conn.commit(); conn.close()

@library_bp.route("/api/library/check")
def check_library_seats():
    loc, date, time_slot = request.args.get("location"), request.args.get("date"), request.args.get("time")
    conn = sqlite3.connect("database.db"); c = conn.cursor()
    all_seats = [row[0] for row in c.execute("SELECT seat_no FROM seats WHERE location=?", (loc,)).fetchall()]
    booked_seats = [row[0] for row in c.execute("SELECT seat_no FROM library_bookings WHERE location=? AND booking_date=? AND time_slot=? AND status NOT IN ('Rejected', 'Completed')", (loc, date, time_slot)).fetchall()]
    results = [{"seat_no": s, "status": "Sold" if s in booked_seats else "Available"} for s in all_seats]
    conn.close(); return jsonify(results)

@library_bp.route("/api/library/book", methods=["POST"])
def book_library_seat():
    data = request.json; user = session["user"]; booking_date = datetime.strptime(data["date"], "%Y-%m-%d").date(); today = datetime.now().date()
    if booking_date < today: return jsonify({"status": "error", "message": "Cannot book past dates!"})
    conn = sqlite3.connect("database.db"); c = conn.cursor()
    c.execute("SELECT id FROM library_bookings WHERE student_name=? AND status IN ('Pending', 'Approved')", (user,))
    if c.fetchone(): conn.close(); return jsonify({"status": "error", "message": "You already have an active library reservation."})
    c.execute("INSERT INTO library_bookings (location, seat_no, student_name, booking_date, time_slot, status) VALUES (?, ?, ?, ?, ?, 'Pending')", (data["location"], data["seat"], user, data["date"], data["time"]))
    conn.commit(); conn.close(); log_act(f"Reserved seat {data['seat']} at {data['location']}")
    return jsonify({"status": "success", "message": "Seat requested! Waiting for Admin approval."})

@library_bp.route("/api/library/cancel", methods=["POST"])
def cancel_library_booking():
    data = request.json; user = session["user"]; conn = sqlite3.connect("database.db"); c = conn.cursor()
    c.execute("SELECT id FROM library_bookings WHERE id=? AND student_name=?", (data["id"], user))
    if not c.fetchone(): conn.close(); return jsonify({"status": "error", "message": "Booking not found."})
    c.execute("DELETE FROM library_bookings WHERE id=? AND student_name=?", (data["id"], user)); conn.commit(); conn.close()
    return jsonify({"status": "success", "message": "Reservation canceled successfully!"})

@library_bp.route("/api/library/complete", methods=["POST"])
def complete_library_booking():
    data = request.json; user = session["user"]; conn = sqlite3.connect("database.db"); c = conn.cursor()
    c.execute("UPDATE library_bookings SET status='Completed' WHERE id=? AND student_name=?", (data["id"], user)); conn.commit(); conn.close()
    return jsonify({"status": "success", "message": "Seat marked as Completed!"})