from flask import Flask, render_template, request, redirect, session, jsonify
import psycopg2
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "smartcampus_secret"

# Vercel Environment Variable for Database
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://neondb_owner:npg_DigUIt12sqTd@ep-falling-poetry-ammfzzsj-pooler.c-5.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

# ---------- CLOUD DATABASE SETUP ----------
def init_db():
    conn = get_db_connection()
    c = conn.cursor()

    # Create Cloud Tables with PostgreSQL Syntax
    c.execute("""CREATE TABLE IF NOT EXISTS users(id SERIAL PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT DEFAULT 'student', vendor_name TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS vendors(id SERIAL PRIMARY KEY, name TEXT UNIQUE, status TEXT DEFAULT 'Open', revenue INTEGER DEFAULT 0, orders_completed INTEGER DEFAULT 0, opening_time TEXT DEFAULT '09:00 AM', closing_time TEXT DEFAULT '05:00 PM', contact_name TEXT DEFAULT 'Manager', phone TEXT DEFAULT 'N/A', location TEXT DEFAULT 'Campus Food Court')""")
    c.execute("""CREATE TABLE IF NOT EXISTS menu(id SERIAL PRIMARY KEY, vendor_name TEXT, item_name TEXT, price INTEGER, icon TEXT DEFAULT 'fa-bowl-food', availability TEXT DEFAULT 'Available', category TEXT DEFAULT 'Main', diet TEXT DEFAULT 'Veg', description TEXT DEFAULT '', is_customizable TEXT DEFAULT 'No', half_price INTEGER DEFAULT 0, addons TEXT DEFAULT '')""")
    c.execute("""CREATE TABLE IF NOT EXISTS cart(id SERIAL PRIMARY KEY, username TEXT, vendor_name TEXT, item TEXT, price INTEGER, quantity INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS orders(id SERIAL PRIMARY KEY, student_name TEXT, vendor_name TEXT, item TEXT, quantity INTEGER, status TEXT DEFAULT 'Pending', total_price INTEGER DEFAULT 0, timestamp TEXT DEFAULT 'N/A', estimated_time TEXT DEFAULT 'Pending Vendor Approval')""")
    c.execute("""CREATE TABLE IF NOT EXISTS rooms(id SERIAL PRIMARY KEY, room_name TEXT, status TEXT DEFAULT 'Available')""")
    c.execute("""CREATE TABLE IF NOT EXISTS seats(id SERIAL PRIMARY KEY, seat_no TEXT, status TEXT DEFAULT 'Available', location TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS events(id SERIAL PRIMARY KEY, title TEXT, description TEXT, date TEXT, status TEXT DEFAULT 'Pending', category TEXT DEFAULT 'General', time TEXT DEFAULT 'TBA', location TEXT DEFAULT 'TBA', organizer TEXT DEFAULT 'Student Club', rsvp_count INTEGER DEFAULT 0, creator TEXT DEFAULT 'system', registration_link TEXT DEFAULT '')""")
    c.execute("""CREATE TABLE IF NOT EXISTS room_bookings(id SERIAL PRIMARY KEY, room_name TEXT, student_name TEXT, booking_date TEXT, time_slot TEXT, status TEXT DEFAULT 'Pending')""")
    c.execute("""CREATE TABLE IF NOT EXISTS event_rsvps(id SERIAL PRIMARY KEY, student_name TEXT, event_id INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS library_bookings(id SERIAL PRIMARY KEY, location TEXT, seat_no TEXT, student_name TEXT, booking_date TEXT, time_slot TEXT, status TEXT DEFAULT 'Pending')""")
    c.execute("""CREATE TABLE IF NOT EXISTS user_activity(id SERIAL PRIMARY KEY, username TEXT, action TEXT, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    # Seed initial data securely
    c.execute("INSERT INTO users (username, password, role) VALUES ('admin', 'admin123', 'admin') ON CONFLICT (username) DO NOTHING")
    
    c.execute("SELECT COUNT(*) FROM rooms WHERE room_name='NLH101'")
    if c.fetchone()[0] == 0:
        for i in range(101, 105): c.execute("INSERT INTO rooms (room_name, status) VALUES (%s, 'Lecture Hall')", (f"NLH{i}",))
        for i in range(105, 116): c.execute("INSERT INTO rooms (room_name, status) VALUES (%s, 'Tutorial room')", (f"NTR{i}",))
        for i in range(116, 129): c.execute("INSERT INTO rooms (room_name, status) VALUES (%s, 'Classroom')", (f"NCA{i}",))

    for loc in ['A block library', 'Hatchery', 'LRC', 'Law library']:
        c.execute("SELECT COUNT(*) FROM seats WHERE location=%s", (loc,))
        if c.fetchone()[0] == 0:
            for i in range(1, 21): 
                c.execute("INSERT INTO seats (seat_no, location, status) VALUES (%s, %s, 'Available')", (f"{i:02d}", loc))

    conn.commit()
    conn.close()

init_db()

def log_act(msg):
    if "user" in session:
        conn = get_db_connection()
        conn.cursor().execute("INSERT INTO user_activity (username, action) VALUES (%s, %s)", (session["user"], msg))
        conn.commit(); conn.close()

# ---------- AUTH ROUTES ----------
@app.route("/")
def home(): return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():
    username = request.form["username"]
    password = request.form["password"]
    conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT username, role FROM users WHERE username=%s AND password=%s", (username, password))
    user = c.fetchone(); conn.close()
    
    if user:
        session["user"] = user[0]; session["role"] = user[1]
        log_act("Logged in")
        if user[1] == "admin": return redirect("/admin")
        elif user[1] == "vendor": return redirect("/vendor")
        return redirect("/dashboard")
    return render_template("login.html", error="Invalid Credentials")

@app.route("/register", methods=["POST"])
def register():
    username = request.form["new_username"]; password = request.form["new_password"]
    conn = get_db_connection(); c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, 'student')", (username, password))
        conn.commit(); msg = "Registration successful! You can now log in."
    except psycopg2.IntegrityError: 
        conn.rollback(); msg = "Username already exists."
    finally: conn.close()
    return render_template("login.html", error=msg)

@app.route("/logout")
def logout():
    log_act("Logged out"); session.clear(); return redirect("/")

# ---------- DASHBOARD ----------
@app.route("/dashboard")
def dashboard():
    if "user" not in session or session.get("role") != "student": return redirect("/")
    conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT * FROM vendors WHERE status='Open'"); vendors = c.fetchall()
    c.execute("SELECT id, vendor_name, item, quantity, total_price, status, estimated_time, timestamp FROM orders WHERE student_name=%s AND status IN ('Pending', 'Preparing', 'Ready to Pickup') ORDER BY id DESC", (session["user"],))
    active_orders = c.fetchall()
    c.execute("SELECT id, vendor_name, item, quantity, total_price, status, timestamp FROM orders WHERE student_name=%s AND status IN ('Completed', 'Rejected') ORDER BY id DESC", (session["user"],))
    past_orders = c.fetchall()
    c.execute("SELECT * FROM rooms"); rooms = c.fetchall()
    c.execute("SELECT * FROM seats"); seats = c.fetchall()
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    c.execute("SELECT id, title, description, date, time, location, category, organizer, rsvp_count, creator, registration_link FROM events WHERE status='Approved' AND date >= %s ORDER BY date ASC", (today_str,))
    upcoming_events = c.fetchall()
    c.execute("""SELECT e.id, e.title, e.date, e.time, e.location, e.category, e.organizer 
                 FROM events e JOIN event_rsvps r ON e.id = r.event_id 
                 WHERE r.student_name=%s AND (e.date < %s OR e.status='Completed') ORDER BY e.date DESC""", (session["user"], today_str))
    past_rsvps = c.fetchall()
    c.execute("SELECT event_id FROM event_rsvps WHERE student_name=%s", (session["user"],))
    my_rsvps = [row[0] for row in c.fetchall()]

    c.execute("SELECT id, room_name, booking_date, time_slot, status FROM room_bookings WHERE student_name=%s AND booking_date >= %s AND status NOT IN ('Rejected', 'Completed') ORDER BY booking_date ASC LIMIT 1", (session["user"], today_str))
    my_booking = c.fetchone()
    c.execute("SELECT id, room_name, booking_date, time_slot, status FROM room_bookings WHERE student_name=%s AND (booking_date < %s OR status IN ('Rejected', 'Completed')) ORDER BY booking_date DESC", (session["user"], today_str))
    past_room_bookings = c.fetchall()

    c.execute("SELECT id, location, seat_no, booking_date, time_slot, status FROM library_bookings WHERE student_name=%s AND status IN ('Pending', 'Approved') ORDER BY booking_date ASC LIMIT 1", (session["user"],))
    my_library_booking = c.fetchone()
    c.execute("SELECT id, location, seat_no, booking_date, time_slot, status FROM library_bookings WHERE student_name=%s AND (booking_date < %s OR status IN ('Rejected', 'Completed')) ORDER BY booking_date DESC", (session["user"], today_str))
    past_library_bookings = c.fetchall()
    conn.close()
    return render_template("dashboard.html", user=session["user"], vendors=vendors, active_orders=active_orders, past_orders=past_orders, rooms=rooms, seats=seats, events=upcoming_events, past_rsvps=past_rsvps, my_rsvps=my_rsvps, my_booking=my_booking, past_room_bookings=past_room_bookings, my_library_booking=my_library_booking, past_library_bookings=past_library_bookings)

# ---------- ADMIN ROUTES ----------
@app.route("/admin")
def admin_panel():
    if "user" not in session or session.get("role") != "admin": return redirect("/")
    conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT * FROM vendors"); vendors = c.fetchall()
    c.execute("SELECT id, username, password, role FROM users WHERE role='student'"); students = c.fetchall()
    c.execute("SELECT * FROM menu"); menu_items = c.fetchall()
    c.execute("SELECT id, student_name, vendor_name, item, quantity, total_price, timestamp FROM orders WHERE status='Completed' ORDER BY id DESC"); history = c.fetchall()
    c.execute("SELECT * FROM rooms"); rooms = c.fetchall()
    c.execute("SELECT * FROM seats"); seats = c.fetchall()
    c.execute("SELECT id, title, description, date, time, location, category, organizer, status, registration_link FROM events ORDER BY date DESC"); events = c.fetchall()
    c.execute("SELECT id, room_name, student_name, booking_date, time_slot, status FROM room_bookings ORDER BY id DESC"); room_requests = c.fetchall()
    c.execute("SELECT id, location, seat_no, student_name, booking_date, time_slot, status FROM library_bookings ORDER BY id DESC"); library_requests = c.fetchall()
    conn.close()
    return render_template("admin.html", vendors=vendors, students=students, menu_items=menu_items, history=history, rooms=rooms, seats=seats, events=events, room_requests=room_requests, library_requests=library_requests)

@app.route("/admin/add_student", methods=["POST"])
def admin_add_student():
    if session.get("role") == "admin":
        conn = get_db_connection(); c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, 'student')", (request.form["username"], request.form["password"]))
            conn.commit()
        except psycopg2.IntegrityError: conn.rollback()
        conn.close()
    return redirect("/admin")

@app.route("/admin/edit_student/<int:id>", methods=["POST"])
def admin_edit_student(id):
    if session.get("role") == "admin":
        conn = get_db_connection(); c = conn.cursor()
        c.execute("UPDATE users SET username=%s, password=%s WHERE id=%s", (request.form["username"], request.form["password"], id))
        conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/delete_student/<int:id>", methods=["POST"])
def admin_delete_student(id):
    if session.get("role") == "admin":
        conn = get_db_connection(); c = conn.cursor()
        c.execute("DELETE FROM users WHERE id=%s", (id,))
        conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/add_seat", methods=["POST"])
def admin_add_seat():
    if session.get("role") == "admin":
        conn = get_db_connection(); c = conn.cursor()
        c.execute("INSERT INTO seats (seat_no, location, status) VALUES (%s, %s, %s)", (request.form.get("seat_no"), request.form.get("location"), request.form.get("status", "Available")))
        conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/edit_seat/<int:id>", methods=["POST"])
def admin_edit_seat(id):
    if session.get("role") == "admin":
        conn = get_db_connection(); c = conn.cursor()
        c.execute("UPDATE seats SET seat_no=%s, location=%s, status=%s WHERE id=%s", (request.form.get("new_seat_no"), request.form.get("new_location"), request.form.get("new_status"), id))
        conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/delete_seat/<int:id>", methods=["POST"])
def admin_delete_seat(id):
    if session.get("role") == "admin":
        conn = get_db_connection(); c = conn.cursor()
        c.execute("DELETE FROM seats WHERE id=%s", (id,))
        conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/add_event", methods=["POST"])
def admin_add_event():
    if session.get("role") == "admin":
        f = request.form
        conn = get_db_connection(); c = conn.cursor()
        c.execute("INSERT INTO events (title, description, date, time, location, category, organizer, status, creator, registration_link) VALUES (%s, %s, %s, %s, %s, %s, %s, 'Approved', 'admin', %s)", 
                  (f["title"], f["desc"], f["date"], f["time"], f["location"], f["category"], f["organizer"], f.get("reg_link", "")))
        conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/edit_event/<int:id>", methods=["POST"])
def admin_edit_event(id):
    if session.get("role") == "admin":
        f = request.form
        conn = get_db_connection(); c = conn.cursor()
        c.execute("UPDATE events SET title=%s, description=%s, date=%s, time=%s, location=%s, category=%s, organizer=%s, registration_link=%s WHERE id=%s", 
                  (f["title"], f["desc"], f["date"], f["time"], f["location"], f["category"], f["organizer"], f.get("reg_link", ""), id))
        conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/add_vendor", methods=["POST"])
def add_vendor():
    if session.get("role") == "admin":
        f = request.form; conn = get_db_connection(); c = conn.cursor()
        try:
            c.execute("INSERT INTO vendors (name, opening_time, closing_time, contact_name, phone, location) VALUES (%s, %s, %s, %s, %s, %s)", (f["vendor_name"], f["opening_time"], f["closing_time"], f["contact_name"], f["phone"], f["location"]))
            c.execute("INSERT INTO users (username, password, role, vendor_name) VALUES (%s, %s, 'vendor', %s)", (f["vendor_username"], f["vendor_password"], f["vendor_name"]))
            conn.commit()
        except: conn.rollback()
        conn.close()
    return redirect("/admin")

@app.route("/admin/delete_vendor/<int:id>", methods=["POST"])
def delete_vendor(id):
    if session.get("role") == "admin":
        conn = get_db_connection(); c = conn.cursor()
        c.execute("SELECT name FROM vendors WHERE id=%s", (id,)); vendor = c.fetchone()
        if vendor:
            c.execute("DELETE FROM menu WHERE vendor_name=%s", (vendor[0],)); c.execute("DELETE FROM users WHERE vendor_name=%s", (vendor[0],)); c.execute("DELETE FROM vendors WHERE id=%s", (id,))
        conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/toggle_vendor/<int:id>", methods=["POST"])
def toggle_vendor(id):
    if session.get("role") == "admin":
        conn = get_db_connection(); c = conn.cursor()
        c.execute("UPDATE vendors SET status = CASE WHEN status='Open' THEN 'Closed' ELSE 'Open' END WHERE id=%s", (id,))
        conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/add_food", methods=["POST"])
def add_food():
    if session.get("role") == "admin":
        f = request.form; conn = get_db_connection(); c = conn.cursor()
        c.execute("INSERT INTO menu (vendor_name, item_name, price, icon, category, diet, description, is_customizable, half_price, addons) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", (f["vendor_name"], f["item_name"], f["price"], f["icon"] or "fa-bowl-food", f["category"], f["diet"], f["description"], f.get("is_customizable", "No"), f.get("half_price") or 0, f.get("addons", "")))
        conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/delete_food/<int:id>", methods=["POST"])
def delete_food(id):
    if session.get("role") == "admin":
        conn = get_db_connection(); c = conn.cursor(); c.execute("DELETE FROM menu WHERE id=%s", (id,)); conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/toggle_food/<int:id>", methods=["POST"])
def toggle_food(id):
    if session.get("role") == "admin":
        conn = get_db_connection(); c = conn.cursor(); c.execute("UPDATE menu SET availability = CASE WHEN availability='Available' THEN 'Unavailable' ELSE 'Available' END WHERE id=%s", (id,)); conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/edit_food_price/<int:id>", methods=["POST"])
def edit_food_price(id):
    if session.get("role") == "admin":
        conn = get_db_connection(); c = conn.cursor(); c.execute("UPDATE menu SET price=%s WHERE id=%s", (request.form["new_price"], id)); conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/add_room", methods=["POST"])
def add_room():
    if session.get("role") == "admin":
        conn = get_db_connection(); c = conn.cursor(); c.execute("INSERT INTO rooms (room_name, status) VALUES (%s, %s)", (request.form.get("room_name"), request.form.get("room_type"))); conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/delete_room/<int:id>", methods=["POST"])
def delete_room(id):
    if session.get("role") == "admin":
        conn = get_db_connection(); c = conn.cursor(); c.execute("DELETE FROM rooms WHERE id=%s", (id,)); conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/edit_room/<int:id>", methods=["POST"])
def edit_room(id):
    if session.get("role") == "admin":
        conn = get_db_connection(); c = conn.cursor(); c.execute("UPDATE rooms SET room_name=%s, status=%s WHERE id=%s", (request.form.get("new_name"), request.form.get("new_type"), id)); conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/room_action", methods=["POST"])
def admin_room_action():
    if session.get("role") == "admin":
        conn = get_db_connection(); c = conn.cursor(); c.execute("UPDATE room_bookings SET status=%s WHERE id=%s", ("Approved" if request.form.get("action") == "approve" else "Rejected", request.form.get("request_id"))); conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/library_action", methods=["POST"])
def admin_library_action():
    if session.get("role") == "admin":
        conn = get_db_connection(); c = conn.cursor(); c.execute("UPDATE library_bookings SET status=%s WHERE id=%s", ("Approved" if request.form.get("action") == "approve" else "Rejected", request.form.get("request_id"))); conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/event_action", methods=["POST"])
def admin_event_action():
    if session.get("role") == "admin":
        conn = get_db_connection(); c = conn.cursor(); c.execute("UPDATE events SET status=%s WHERE id=%s", ("Approved" if request.form.get("action") == "approve" else "Rejected", request.form.get("request_id"))); conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/delete_event/<int:id>", methods=["POST"])
def delete_event(id):
    if session.get("role") == "admin":
        conn = get_db_connection(); c = conn.cursor(); c.execute("DELETE FROM events WHERE id=%s", (id,)); conn.commit(); conn.close()
    return redirect("/admin")

# ---------- VENDOR ROUTES ----------
def get_vendor_name():
    conn = get_db_connection(); c = conn.cursor(); c.execute("SELECT vendor_name FROM users WHERE username=%s", (session["user"],)); v_name = c.fetchone(); conn.close(); return v_name[0] if v_name else "Unknown"

@app.route("/vendor")
def vendor_panel():
    if "user" not in session or session.get("role") != "vendor": return redirect("/")
    v_name = get_vendor_name(); conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT id, student_name, item, quantity, status, total_price, estimated_time, timestamp FROM orders WHERE vendor_name=%s AND status NOT IN ('Completed', 'Rejected') ORDER BY id ASC", (v_name,))
    orders = c.fetchall()
    c.execute("SELECT id, student_name, item, quantity, status, total_price, estimated_time, timestamp FROM orders WHERE vendor_name=%s AND status IN ('Completed', 'Rejected') ORDER BY id DESC", (v_name,))
    past_orders = c.fetchall()
    c.execute("SELECT SUM(total_price) FROM orders WHERE vendor_name=%s AND status='Completed'", (v_name,))
    daily_revenue = c.fetchone()[0] or 0
    c.execute("SELECT * FROM menu WHERE vendor_name=%s", (v_name,))
    menu_items = c.fetchall(); conn.close()
    return render_template("vendor.html", vendor_name=v_name, orders=orders, past_orders=past_orders, daily_revenue=daily_revenue, menu_items=menu_items)

@app.route("/vendor/order_action/<int:order_id>", methods=["POST"])
def vendor_order_action(order_id):
    if session.get("role") == "vendor":
        action = request.form.get("action"); conn = get_db_connection(); c = conn.cursor()
        if action == "accept": c.execute("UPDATE orders SET status='Preparing', estimated_time=%s WHERE id=%s", (f"{request.form.get('prep_time', '15')} mins", order_id))
        elif action == "reject": c.execute("UPDATE orders SET status='Rejected', estimated_time='Order Rejected' WHERE id=%s", (order_id,))
        elif action == "extend": c.execute("UPDATE orders SET estimated_time=%s WHERE id=%s", (f"{request.form.get('extra_time', '10')} mins (Extended)", order_id))
        elif action == "ready": c.execute("UPDATE orders SET status='Ready to Pickup', estimated_time='Ready Now!' WHERE id=%s", (order_id,))
        elif action == "completed":
            c.execute("UPDATE orders SET status='Completed', estimated_time='Done' WHERE id=%s", (order_id,))
            c.execute("SELECT vendor_name, total_price FROM orders WHERE id=%s", (order_id,)); order = c.fetchone()
            if order: c.execute("UPDATE vendors SET revenue = revenue + %s, orders_completed = orders_completed + 1 WHERE name=%s", (order[1], order[0]))
        conn.commit(); conn.close()
    return redirect("/vendor")

@app.route("/vendor/add_food", methods=["POST"])
def vendor_add_food():
    if session.get("role") == "vendor":
        f = request.form; conn = get_db_connection(); c = conn.cursor()
        c.execute("INSERT INTO menu (vendor_name, item_name, price, icon, category, diet, description, is_customizable, half_price, addons) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", (get_vendor_name(), f["item_name"], f["price"], f["icon"] or "fa-bowl-food", f["category"], f["diet"], f["description"], f.get("is_customizable", "No"), f.get("half_price") or 0, f.get("addons", "")))
        conn.commit(); conn.close()
    return redirect("/vendor")

@app.route("/vendor/delete_food/<int:id>", methods=["POST"])
def vendor_delete_food(id):
    if session.get("role") == "vendor":
        conn = get_db_connection(); c = conn.cursor(); c.execute("DELETE FROM menu WHERE id=%s AND vendor_name=%s", (id, get_vendor_name())); conn.commit(); conn.close()
    return redirect("/vendor")

@app.route("/vendor/toggle_food/<int:id>", methods=["POST"])
def vendor_toggle_food(id):
    if session.get("role") == "vendor":
        conn = get_db_connection(); c = conn.cursor(); c.execute("UPDATE menu SET availability = CASE WHEN availability='Available' THEN 'Unavailable' ELSE 'Available' END WHERE id=%s AND vendor_name=%s", (id, get_vendor_name())); conn.commit(); conn.close()
    return redirect("/vendor")

@app.route("/vendor/edit_food_price/<int:id>", methods=["POST"])
def vendor_edit_food_price(id):
    if session.get("role") == "vendor":
        conn = get_db_connection(); c = conn.cursor(); c.execute("UPDATE menu SET price=%s WHERE id=%s AND vendor_name=%s", (request.form["new_price"], id, get_vendor_name())); conn.commit(); conn.close()
    return redirect("/vendor")

# ---------- APIS FOR DASHBOARD ----------
@app.route("/get_menu/<vendor_name>")
def get_menu(vendor_name):
    conn = get_db_connection(); c = conn.cursor(); c.execute("SELECT item_name, price, icon, category, diet, description, is_customizable, half_price, addons FROM menu WHERE vendor_name=%s AND availability='Available'", (vendor_name,)); menu = c.fetchall(); conn.close()
    return jsonify([{"name": m[0], "price": m[1], "icon": m[2], "category": m[3], "diet": m[4], "desc": m[5], "is_customizable": m[6], "half_price": m[7], "addons": m[8]} for m in menu])

@app.route("/add_to_cart", methods=["POST"])
def add_to_cart():
    data = request.json; user = session["user"]; conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT quantity FROM cart WHERE username=%s AND item=%s AND vendor_name=%s", (user, data["item"], data.get("vendor_name", "Unknown")))
    if c.fetchone(): c.execute("UPDATE cart SET quantity=quantity+1 WHERE username=%s AND item=%s AND vendor_name=%s", (user, data["item"], data.get("vendor_name", "Unknown")))
    else: c.execute("INSERT INTO cart(username, vendor_name, item, price, quantity) VALUES(%s, %s, %s, %s, %s)", (user, data.get("vendor_name", "Unknown"), data["item"], data["price"], 1))
    conn.commit(); conn.close(); return jsonify({"status": "added"})

@app.route("/get_cart")
def get_cart():
    conn = get_db_connection(); c = conn.cursor(); c.execute("SELECT item, price, quantity, vendor_name FROM cart WHERE username=%s", (session["user"],)); items = c.fetchall(); conn.close(); return jsonify(items)

@app.route("/checkout", methods=["POST"])
def checkout():
    user = session["user"]; timestamp = datetime.now().strftime("%Y-%m-%d %I:%M %p"); conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT vendor_name, item, price, quantity FROM cart WHERE username=%s", (user,)); cart_items = c.fetchall()
    for item in cart_items: c.execute("INSERT INTO orders (student_name, vendor_name, item, quantity, total_price, timestamp, status) VALUES (%s, %s, %s, %s, %s, %s, 'Pending')", (user, item[0], item[1], item[3], item[2] * item[3], timestamp))
    c.execute("DELETE FROM cart WHERE username=%s", (user,)); conn.commit(); conn.close(); log_act("Placed food order"); return jsonify({"status": "order_placed"})

@app.route("/update_quantity", methods=["POST"])
def update_quantity():
    data = request.json; conn = get_db_connection(); c = conn.cursor()
    if data["action"] == "increase": c.execute("UPDATE cart SET quantity=quantity+1 WHERE username=%s AND item=%s", (session["user"], data["item"]))
    else: c.execute("UPDATE cart SET quantity=quantity-1 WHERE username=%s AND item=%s", (session["user"], data["item"])); c.execute("DELETE FROM cart WHERE username=%s AND item=%s AND quantity<=0", (session["user"], data["item"]))
    conn.commit(); conn.close(); return jsonify({"status": "updated"})

@app.route("/remove_item", methods=["POST"])
def remove_item():
    conn = get_db_connection(); c = conn.cursor(); c.execute("DELETE FROM cart WHERE username=%s AND item=%s", (session["user"], request.json["item"])); conn.commit(); conn.close(); return jsonify({"status": "removed"})

@app.route("/api/search")
def search():
    query = request.args.get("q", "").lower()
    if not query: return jsonify([])
    conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT item_name, price, icon, category, diet, description, is_customizable, half_price, addons, vendor_name FROM menu WHERE LOWER(item_name) LIKE %s AND availability='Available'", (f"%{query}%",))
    menu = c.fetchall(); conn.close()
    return jsonify([{"name": m[0], "price": m[1], "icon": m[2], "category": m[3], "diet": m[4], "desc": m[5], "is_customizable": m[6], "half_price": m[7], "addons": m[8], "vendor_name": m[9]} for m in menu])

@app.route("/api/rooms/check")
def check_rooms():
    date = request.args.get("date"); time_slot = request.args.get("time"); conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT room_name, status FROM rooms"); all_rooms = c.fetchall()
    c.execute("SELECT room_name FROM room_bookings WHERE booking_date=%s AND time_slot=%s AND status NOT IN ('Rejected', 'Completed')", (date, time_slot)); booked_rooms = [row[0] for row in c.fetchall()] 
    results = [{"name": r[0], "type": r[1], "status": "Occupied" if r[0] in booked_rooms else "Available"} for r in all_rooms]
    conn.close(); return jsonify(results)

@app.route("/api/rooms/book", methods=["POST"])
def book_room():
    data = request.json; user = session["user"]; booking_date = datetime.strptime(data["date"], "%Y-%m-%d").date(); today = datetime.now().date()
    if (booking_date - today).days < 0: return jsonify({"status": "error", "message": "Cannot book in the past!"})
    if (booking_date - today).days > 2: return jsonify({"status": "error", "message": "Max 48 hours in advance."})
    conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT id FROM room_bookings WHERE student_name=%s AND booking_date >= %s AND status NOT IN ('Rejected', 'Completed')", (user, today.strftime("%Y-%m-%d")))
    if c.fetchone(): conn.close(); return jsonify({"status": "error", "message": "You already have an active room booking."})
    c.execute("INSERT INTO room_bookings (room_name, student_name, booking_date, time_slot, status) VALUES (%s, %s, %s, %s, 'Pending')", (data["room"], user, data["date"], data["time"]))
    conn.commit(); conn.close(); log_act(f"Booked room {data['room']}")
    return jsonify({"status": "success", "message": "Room requested! Waiting for Admin approval."})

@app.route("/api/rooms/cancel", methods=["POST"])
def cancel_booking():
    data = request.json; user = session["user"]; conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT booking_date, time_slot FROM room_bookings WHERE id=%s AND student_name=%s", (data["id"], user)); booking = c.fetchone()
    if not booking: conn.close(); return jsonify({"status": "error", "message": "Booking not found."})
    start_datetime = datetime.strptime(f"{booking[0]} {booking[1].split(' - ')[0]}", "%Y-%m-%d %I:%M %p")
    if (start_datetime - datetime.now()).total_seconds() < 1800: conn.close(); return jsonify({"status": "error", "message": "Too late! You cannot cancel a room within 30 minutes of the start time."})
    c.execute("DELETE FROM room_bookings WHERE id=%s AND student_name=%s", (data["id"], user)); conn.commit(); conn.close()
    return jsonify({"status": "success", "message": "Booking canceled successfully!"})

@app.route("/api/rooms/complete", methods=["POST"])
def complete_booking():
    conn = get_db_connection(); c = conn.cursor(); c.execute("UPDATE room_bookings SET status='Completed' WHERE id=%s AND student_name=%s", (request.json["id"], session["user"])); conn.commit(); conn.close(); return jsonify({"status": "success", "message": "Room marked as Completed!"})

@app.route("/api/library/check")
def check_library_seats():
    location = request.args.get("location"); date = request.args.get("date"); time_slot = request.args.get("time")
    conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT seat_no FROM seats WHERE location=%s", (location,))
    all_seats = [row[0] for row in c.fetchall()]
    c.execute("SELECT seat_no FROM library_bookings WHERE location=%s AND booking_date=%s AND time_slot=%s AND status NOT IN ('Rejected', 'Completed')", (location, date, time_slot))
    booked_seats = [row[0] for row in c.fetchall()]
    results = [{"seat_no": s, "status": "Sold" if s in booked_seats else "Available"} for s in all_seats]
    conn.close(); return jsonify(results)

@app.route("/api/library/book", methods=["POST"])
def book_library_seat():
    data = request.json; user = session["user"]; booking_date = datetime.strptime(data["date"], "%Y-%m-%d").date(); today = datetime.now().date()
    if booking_date < today: return jsonify({"status": "error", "message": "Cannot book past dates!"})
    conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT id FROM library_bookings WHERE student_name=%s AND status IN ('Pending', 'Approved')", (user,))
    if c.fetchone(): conn.close(); return jsonify({"status": "error", "message": "You already have an active library reservation."})
    c.execute("INSERT INTO library_bookings (location, seat_no, student_name, booking_date, time_slot, status) VALUES (%s, %s, %s, %s, %s, 'Pending')", (data["location"], data["seat"], user, data["date"], data["time"]))
    conn.commit(); conn.close(); log_act(f"Reserved seat {data['seat']} at {data['location']}"); return jsonify({"status": "success", "message": "Seat requested! Waiting for Admin approval."})

@app.route("/api/library/cancel", methods=["POST"])
def cancel_library_booking():
    data = request.json; user = session["user"]; conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT id FROM library_bookings WHERE id=%s AND student_name=%s", (data["id"], user))
    if not c.fetchone(): conn.close(); return jsonify({"status": "error", "message": "Booking not found."})
    c.execute("DELETE FROM library_bookings WHERE id=%s AND student_name=%s", (data["id"], user)); conn.commit(); conn.close()
    return jsonify({"status": "success", "message": "Reservation canceled successfully!"})

@app.route("/api/library/complete", methods=["POST"])
def complete_library_booking():
    data = request.json; user = session["user"]; conn = get_db_connection(); c = conn.cursor()
    c.execute("UPDATE library_bookings SET status='Completed' WHERE id=%s AND student_name=%s", (data["id"], user)); conn.commit(); conn.close()
    return jsonify({"status": "success", "message": "Seat marked as Completed!"})

@app.route("/api/events/submit", methods=["POST"])
def submit_event():
    data = request.json
    try:
        submitted_date = datetime.strptime(data["date"], "%Y-%m-%d").date()
        if submitted_date < datetime.now().date(): return jsonify({"status": "error", "message": "Cannot submit an event on a past date!"})
    except ValueError: return jsonify({"status": "error", "message": "Invalid date format."})
    
    organizer = data.get("organizer", session["user"]); creator = session["user"]; category = data.get("category") or data.get("cat", "General")
    conn = get_db_connection(); c = conn.cursor()
    c.execute("INSERT INTO events (title, description, date, time, location, category, organizer, status, creator, registration_link) VALUES (%s, %s, %s, %s, %s, %s, %s, 'Pending', %s, %s)", (data["title"], data["desc"], data["date"], data["time"], data["location"], category, organizer, creator, data.get("reg_link", "")))
    conn.commit(); conn.close(); log_act(f"Proposed event: {data['title']}"); return jsonify({"status": "success", "message": "Event submitted! Waiting for Admin approval."})

@app.route("/api/events/owner_action", methods=["POST"])
def owner_event_action():
    event_id = request.json["id"]; action = request.json["action"]; user = session["user"]
    conn = get_db_connection(); c = conn.cursor(); c.execute("SELECT creator FROM events WHERE id=%s", (event_id,)); ev = c.fetchone()
    if ev and ev[0] == user:
        if action == 'completed': c.execute("UPDATE events SET status='Completed' WHERE id=%s", (event_id,))
        elif action == 'cancel': c.execute("DELETE FROM events WHERE id=%s AND status='Pending'", (event_id,))
        conn.commit(); conn.close(); return jsonify({"status": "success", "message": f"Event marked as {action.capitalize()}!"})
    conn.close(); return jsonify({"status": "error", "message": "Unauthorized."})

@app.route("/api/events/rsvp", methods=["POST"])
def rsvp_event():
    event_id = request.json["id"]; user = session["user"]; conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT id FROM event_rsvps WHERE student_name=%s AND event_id=%s", (user, event_id))
    if not c.fetchone():
        c.execute("INSERT INTO event_rsvps (student_name, event_id) VALUES (%s, %s)", (user, event_id))
        c.execute("UPDATE events SET rsvp_count = rsvp_count + 1 WHERE id=%s", (event_id,))
        conn.commit()
    conn.close(); log_act("RSVP'd to an event"); return jsonify({"status": "success"})

if __name__ == "__main__":
    app.run(debug=True)