from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = "smartcampus_secret"

# ---------- DATABASE ----------
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    try:
        c.execute("ALTER TABLE seats ADD COLUMN location TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    c.execute("""CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT, role TEXT DEFAULT 'student', vendor_name TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS vendors(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, status TEXT DEFAULT 'Open')""")
    c.execute("""CREATE TABLE IF NOT EXISTS menu(id INTEGER PRIMARY KEY AUTOINCREMENT, vendor_name TEXT, item_name TEXT, price INTEGER, icon TEXT DEFAULT 'fa-bowl-food', availability TEXT DEFAULT 'Available')""")
    c.execute("""CREATE TABLE IF NOT EXISTS cart(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, vendor_name TEXT, item TEXT, price INTEGER, quantity INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT, student_name TEXT, vendor_name TEXT, item TEXT, quantity INTEGER, status TEXT DEFAULT 'Pending')""")
    c.execute("""CREATE TABLE IF NOT EXISTS rooms(id INTEGER PRIMARY KEY AUTOINCREMENT, room_name TEXT, status TEXT DEFAULT 'Available')""")
    c.execute("""CREATE TABLE IF NOT EXISTS seats(id INTEGER PRIMARY KEY AUTOINCREMENT, seat_no TEXT, status TEXT DEFAULT 'Available', location TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, description TEXT, date TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS room_bookings(id INTEGER PRIMARY KEY AUTOINCREMENT, room_name TEXT, student_name TEXT, booking_date TEXT, time_slot TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS event_rsvps(id INTEGER PRIMARY KEY AUTOINCREMENT, student_name TEXT, event_id INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS library_bookings(id INTEGER PRIMARY KEY AUTOINCREMENT, location TEXT, seat_no TEXT, student_name TEXT, booking_date TEXT, time_slot TEXT, status TEXT DEFAULT 'Pending')""")
    c.execute("""CREATE TABLE IF NOT EXISTS user_activity(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, action TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)""")

    columns_to_add = [
        ("room_bookings", "status", "TEXT DEFAULT 'Pending'"),
        ("vendors", "revenue", "INTEGER DEFAULT 0"),
        ("vendors", "orders_completed", "INTEGER DEFAULT 0"),
        ("vendors", "opening_time", "TEXT DEFAULT '09:00 AM'"),
        ("vendors", "closing_time", "TEXT DEFAULT '05:00 PM'"),
        ("vendors", "contact_name", "TEXT DEFAULT 'Manager'"),
        ("vendors", "phone", "TEXT DEFAULT 'N/A'"),
        ("vendors", "location", "TEXT DEFAULT 'Campus Food Court'"),
        ("menu", "category", "TEXT DEFAULT 'Main'"),
        ("menu", "diet", "TEXT DEFAULT 'Veg'"),
        ("menu", "description", "TEXT DEFAULT ''"),
        ("menu", "is_customizable", "TEXT DEFAULT 'No'"), 
        ("menu", "half_price", "INTEGER DEFAULT 0"),      
        ("menu", "addons", "TEXT DEFAULT ''"),            
        ("orders", "total_price", "INTEGER DEFAULT 0"),
        ("orders", "timestamp", "TEXT DEFAULT 'N/A'"),
        ("orders", "estimated_time", "TEXT DEFAULT 'Pending Vendor Approval'"),
        ("events", "status", "TEXT DEFAULT 'Pending'"),
        ("events", "category", "TEXT DEFAULT 'General'"),
        ("events", "time", "TEXT DEFAULT 'TBA'"),
        ("events", "location", "TEXT DEFAULT 'TBA'"),
        ("events", "organizer", "TEXT DEFAULT 'Student Club'"),
        ("events", "rsvp_count", "INTEGER DEFAULT 0"),
        ("events", "creator", "TEXT DEFAULT 'system'"), 
        ("events", "registration_link", "TEXT DEFAULT ''") 
    ]
    for table, col, dtype in columns_to_add:
        try: c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {dtype}")
        except sqlite3.OperationalError: pass 

    c.execute("INSERT OR IGNORE INTO users(username, password, role) VALUES('admin', 'admin123', 'admin')")
    c.execute("UPDATE rooms SET status='Tutorial room' WHERE status='Small Classroom'")
    c.execute("UPDATE rooms SET status='Classroom' WHERE status='Medium Classroom'")
    c.execute("DELETE FROM rooms WHERE room_name LIKE 'GD Room%'") 
    
    c.execute("SELECT COUNT(*) FROM rooms WHERE room_name='NLH101'")
    if c.fetchone()[0] == 0:
        for i in range(101, 105): c.execute("INSERT INTO rooms (room_name, status) VALUES (?, 'Lecture Hall')", (f"NLH{i}",))
        for i in range(105, 116): c.execute("INSERT INTO rooms (room_name, status) VALUES (?, 'Tutorial room')", (f"NTR{i}",))
        for i in range(116, 129): c.execute("INSERT INTO rooms (room_name, status) VALUES (?, 'Classroom')", (f"NCA{i}",))

    for loc in ['A block library', 'Hatchery', 'LRC', 'Law library']:
        c.execute("SELECT COUNT(*) FROM seats WHERE location=?", (loc,))
        if c.fetchone()[0] == 0:
            for i in range(1, 21): 
                c.execute("INSERT INTO seats (seat_no, location, status) VALUES (?, ?, 'Available')", (f"{i:02d}", loc))

    conn.commit(); conn.close()

init_db()

def log_act(msg):
    if "user" in session:
        conn = sqlite3.connect("database.db")
        conn.execute("INSERT INTO user_activity (username, action) VALUES (?, ?)", (session["user"], msg))
        conn.commit(); conn.close()

# ---------- AUTH ROUTES ----------
@app.route("/")
def home(): return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():
    username = request.form["username"]
    password = request.form["password"]
    conn = sqlite3.connect("database.db"); c = conn.cursor()
    c.execute("SELECT username, role FROM users WHERE username=? AND password=?", (username, password))
    user = c.fetchone()
    conn.close()
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
    conn = sqlite3.connect("database.db"); c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, 'student')", (username, password))
        conn.commit(); msg = "Registration successful! You can now log in."
    except sqlite3.IntegrityError: msg = "Username already exists."
    finally: conn.close()
    return render_template("login.html", error=msg)

@app.route("/logout")
def logout():
    log_act("Logged out")
    session.clear()
    return redirect("/")

@app.route("/dashboard")
def dashboard():
    if "user" not in session or session.get("role") != "student": return redirect("/")
    conn = sqlite3.connect("database.db"); c = conn.cursor()
    c.execute("SELECT * FROM vendors WHERE status='Open'")
    vendors = c.fetchall()
    c.execute("SELECT id, vendor_name, item, quantity, total_price, status, estimated_time, timestamp FROM orders WHERE student_name=? AND status IN ('Pending', 'Preparing', 'Ready to Pickup') ORDER BY id DESC", (session["user"],))
    active_orders = c.fetchall()
    c.execute("SELECT id, vendor_name, item, quantity, total_price, status, timestamp FROM orders WHERE student_name=? AND status IN ('Completed', 'Rejected') ORDER BY id DESC", (session["user"],))
    past_orders = c.fetchall()
    c.execute("SELECT * FROM rooms")
    rooms = c.fetchall()
    c.execute("SELECT * FROM seats")
    seats = c.fetchall()
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    c.execute("SELECT id, title, description, date, time, location, category, organizer, rsvp_count, creator, registration_link FROM events WHERE status='Approved' AND date >= ? ORDER BY date ASC", (today_str,))
    upcoming_events = c.fetchall()
    c.execute("""SELECT e.id, e.title, e.date, e.time, e.location, e.category, e.organizer 
                 FROM events e JOIN event_rsvps r ON e.id = r.event_id 
                 WHERE r.student_name=? AND (e.date < ? OR e.status='Completed') ORDER BY e.date DESC""", (session["user"], today_str))
    past_rsvps = c.fetchall()
    c.execute("SELECT event_id FROM event_rsvps WHERE student_name=?", (session["user"],))
    my_rsvps = [row[0] for row in c.fetchall()]

    c.execute("SELECT id, room_name, booking_date, time_slot, status FROM room_bookings WHERE student_name=? AND booking_date >= ? AND status NOT IN ('Rejected', 'Completed') ORDER BY booking_date ASC LIMIT 1", (session["user"], today_str))
    my_booking = c.fetchone()
    c.execute("SELECT id, room_name, booking_date, time_slot, status FROM room_bookings WHERE student_name=? AND (booking_date < ? OR status IN ('Rejected', 'Completed')) ORDER BY booking_date DESC", (session["user"], today_str))
    past_room_bookings = c.fetchall()

    c.execute("SELECT id, location, seat_no, booking_date, time_slot, status FROM library_bookings WHERE student_name=? AND status IN ('Pending', 'Approved') ORDER BY booking_date ASC LIMIT 1", (session["user"],))
    my_library_booking = c.fetchone()
    c.execute("SELECT id, location, seat_no, booking_date, time_slot, status FROM library_bookings WHERE student_name=? AND (booking_date < ? OR status IN ('Rejected', 'Completed')) ORDER BY booking_date DESC", (session["user"], today_str))
    past_library_bookings = c.fetchall()
    conn.close()
    return render_template("dashboard.html", user=session["user"], vendors=vendors, active_orders=active_orders, past_orders=past_orders, rooms=rooms, seats=seats, events=upcoming_events, past_rsvps=past_rsvps, my_rsvps=my_rsvps, my_booking=my_booking, past_room_bookings=past_room_bookings, my_library_booking=my_library_booking, past_library_bookings=past_library_bookings)

# ---------- ADMIN ROUTES ----------
@app.route("/admin")
def admin_panel():
    if "user" not in session or session.get("role") != "admin": return redirect("/")
    conn = sqlite3.connect("database.db"); c = conn.cursor()
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
        conn = sqlite3.connect("database.db"); c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, 'student')", (request.form["username"], request.form["password"]))
            conn.commit()
        except sqlite3.IntegrityError: pass
        conn.close()
    return redirect("/admin")

@app.route("/admin/edit_student/<int:id>", methods=["POST"])
def admin_edit_student(id):
    if session.get("role") == "admin":
        conn = sqlite3.connect("database.db"); c = conn.cursor()
        c.execute("UPDATE users SET username=?, password=? WHERE id=?", (request.form["username"], request.form["password"], id))
        conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/delete_student/<int:id>", methods=["POST"])
def admin_delete_student(id):
    if session.get("role") == "admin":
        conn = sqlite3.connect("database.db"); c = conn.cursor()
        c.execute("DELETE FROM users WHERE id=?", (id,))
        conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/add_seat", methods=["POST"])
def admin_add_seat():
    if session.get("role") == "admin":
        conn = sqlite3.connect("database.db"); c = conn.cursor()
        c.execute("INSERT INTO seats (seat_no, location, status) VALUES (?, ?, ?)", (request.form.get("seat_no"), request.form.get("location"), request.form.get("status", "Available")))
        conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/edit_seat/<int:id>", methods=["POST"])
def admin_edit_seat(id):
    if session.get("role") == "admin":
        conn = sqlite3.connect("database.db"); c = conn.cursor()
        c.execute("UPDATE seats SET seat_no=?, location=?, status=? WHERE id=?", (request.form.get("new_seat_no"), request.form.get("new_location"), request.form.get("new_status"), id))
        conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/delete_seat/<int:id>", methods=["POST"])
def admin_delete_seat(id):
    if session.get("role") == "admin":
        conn = sqlite3.connect("database.db"); c = conn.cursor()
        c.execute("DELETE FROM seats WHERE id=?", (id,))
        conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/add_event", methods=["POST"])
def admin_add_event():
    if session.get("role") == "admin":
        f = request.form
        conn = sqlite3.connect("database.db"); c = conn.cursor()
        c.execute("INSERT INTO events (title, description, date, time, location, category, organizer, status, creator, registration_link) VALUES (?, ?, ?, ?, ?, ?, ?, 'Approved', 'admin', ?)", 
                  (f["title"], f["desc"], f["date"], f["time"], f["location"], f["category"], f["organizer"], f.get("reg_link", "")))
        conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/edit_event/<int:id>", methods=["POST"])
def admin_edit_event(id):
    if session.get("role") == "admin":
        f = request.form
        conn = sqlite3.connect("database.db"); c = conn.cursor()
        c.execute("UPDATE events SET title=?, description=?, date=?, time=?, location=?, category=?, organizer=?, registration_link=? WHERE id=?", 
                  (f["title"], f["desc"], f["date"], f["time"], f["location"], f["category"], f["organizer"], f.get("reg_link", ""), id))
        conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/add_vendor", methods=["POST"])
def add_vendor():
    if session.get("role") == "admin":
        f = request.form; conn = sqlite3.connect("database.db"); c = conn.cursor()
        try:
            c.execute("INSERT INTO vendors (name, opening_time, closing_time, contact_name, phone, location) VALUES (?, ?, ?, ?, ?, ?)", (f["vendor_name"], f["opening_time"], f["closing_time"], f["contact_name"], f["phone"], f["location"]))
            c.execute("INSERT INTO users (username, password, role, vendor_name) VALUES (?, ?, 'vendor', ?)", (f["vendor_username"], f["vendor_password"], f["vendor_name"]))
            conn.commit()
        except: pass
        conn.close()
    return redirect("/admin")

@app.route("/admin/delete_vendor/<int:id>", methods=["POST"])
def delete_vendor(id):
    if session.get("role") == "admin":
        conn = sqlite3.connect("database.db"); c = conn.cursor()
        c.execute("SELECT name FROM vendors WHERE id=?", (id,)); vendor = c.fetchone()
        if vendor:
            c.execute("DELETE FROM menu WHERE vendor_name=?", (vendor[0],)); c.execute("DELETE FROM users WHERE vendor_name=?", (vendor[0],)); c.execute("DELETE FROM vendors WHERE id=?", (id,))
        conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/toggle_vendor/<int:id>", methods=["POST"])
def toggle_vendor(id):
    if session.get("role") == "admin":
        conn = sqlite3.connect("database.db"); c = conn.cursor()
        c.execute("UPDATE vendors SET status = CASE WHEN status='Open' THEN 'Closed' ELSE 'Open' END WHERE id=?", (id,))
        conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/add_food", methods=["POST"])
def add_food():
    if session.get("role") == "admin":
        f = request.form; conn = sqlite3.connect("database.db"); c = conn.cursor()
        c.execute("INSERT INTO menu (vendor_name, item_name, price, icon, category, diet, description, is_customizable, half_price, addons) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (f["vendor_name"], f["item_name"], f["price"], f["icon"] or "fa-bowl-food", f["category"], f["diet"], f["description"], f.get("is_customizable", "No"), f.get("half_price") or 0, f.get("addons", "")))
        conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/delete_food/<int:id>", methods=["POST"])
def delete_food(id):
    if session.get("role") == "admin":
        conn = sqlite3.connect("database.db"); c = conn.cursor()
        c.execute("DELETE FROM menu WHERE id=?", (id,)); conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/toggle_food/<int:id>", methods=["POST"])
def toggle_food(id):
    if session.get("role") == "admin":
        conn = sqlite3.connect("database.db"); c = conn.cursor()
        c.execute("UPDATE menu SET availability = CASE WHEN availability='Available' THEN 'Unavailable' ELSE 'Available' END WHERE id=?", (id,))
        conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/edit_food_price/<int:id>", methods=["POST"])
def edit_food_price(id):
    if session.get("role") == "admin":
        conn = sqlite3.connect("database.db"); c = conn.cursor()
        c.execute("UPDATE menu SET price=? WHERE id=?", (request.form["new_price"], id)); conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/add_room", methods=["POST"])
def add_room():
    if session.get("role") == "admin":
        conn = sqlite3.connect("database.db"); c = conn.cursor()
        c.execute("INSERT INTO rooms (room_name, status) VALUES (?, ?)", (request.form.get("room_name"), request.form.get("room_type")))
        conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/delete_room/<int:id>", methods=["POST"])
def delete_room(id):
    if session.get("role") == "admin":
        conn = sqlite3.connect("database.db"); c = conn.cursor()
        c.execute("DELETE FROM rooms WHERE id=?", (id,)); conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/edit_room/<int:id>", methods=["POST"])
def edit_room(id):
    if session.get("role") == "admin":
        conn = sqlite3.connect("database.db"); c = conn.cursor()
        c.execute("UPDATE rooms SET room_name=?, status=? WHERE id=?", (request.form.get("new_name"), request.form.get("new_type"), id))
        conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/room_action", methods=["POST"])
def admin_room_action():
    if session.get("role") == "admin":
        conn = sqlite3.connect("database.db"); c = conn.cursor()
        c.execute("UPDATE room_bookings SET status=? WHERE id=?", ("Approved" if request.form.get("action") == "approve" else "Rejected", request.form.get("request_id")))
        conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/library_action", methods=["POST"])
def admin_library_action():
    if session.get("role") == "admin":
        conn = sqlite3.connect("database.db"); c = conn.cursor()
        status = "Approved" if request.form.get("action") == "approve" else "Rejected"
        c.execute("UPDATE library_bookings SET status=? WHERE id=?", (status, request.form.get("request_id")))
        conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/event_action", methods=["POST"])
def admin_event_action():
    if session.get("role") == "admin":
        conn = sqlite3.connect("database.db"); c = conn.cursor()
        c.execute("UPDATE events SET status=? WHERE id=?", ("Approved" if request.form.get("action") == "approve" else "Rejected", request.form.get("request_id")))
        conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/admin/delete_event/<int:id>", methods=["POST"])
def delete_event(id):
    if session.get("role") == "admin":
        conn = sqlite3.connect("database.db"); c = conn.cursor()
        c.execute("DELETE FROM events WHERE id=?", (id,)); conn.commit(); conn.close()
    return redirect("/admin")

# ---------- VENDOR ROUTES ----------
def get_vendor_name():
    conn = sqlite3.connect("database.db"); c = conn.cursor()
    c.execute("SELECT vendor_name FROM users WHERE username=?", (session["user"],)); v_name = c.fetchone(); conn.close()
    return v_name[0] if v_name else "Unknown"

@app.route("/vendor")
def vendor_panel():
    if "user" not in session or session.get("role") != "vendor": return redirect("/")
    v_name = get_vendor_name(); conn = sqlite3.connect("database.db"); c = conn.cursor()
    
    c.execute("SELECT id, student_name, item, quantity, status, total_price, estimated_time, timestamp FROM orders WHERE vendor_name=? AND status NOT IN ('Completed', 'Rejected') ORDER BY id ASC", (v_name,))
    orders = c.fetchall()
    
    c.execute("SELECT id, student_name, item, quantity, status, total_price, estimated_time, timestamp FROM orders WHERE vendor_name=? AND status IN ('Completed', 'Rejected') ORDER BY id DESC", (v_name,))
    past_orders = c.fetchall()
    
    c.execute("SELECT SUM(total_price) FROM orders WHERE vendor_name=? AND status='Completed'", (v_name,))
    daily_revenue = c.fetchone()[0] or 0

    c.execute("SELECT * FROM menu WHERE vendor_name=?", (v_name,))
    menu_items = c.fetchall()
    
    conn.close()
    return render_template("vendor.html", vendor_name=v_name, orders=orders, past_orders=past_orders, daily_revenue=daily_revenue, menu_items=menu_items)

@app.route("/vendor/order_action/<int:order_id>", methods=["POST"])
def vendor_order_action(order_id):
    if session.get("role") == "vendor":
        action = request.form.get("action"); conn = sqlite3.connect("database.db"); c = conn.cursor()
        if action == "accept": c.execute("UPDATE orders SET status='Preparing', estimated_time=? WHERE id=?", (f"{request.form.get('prep_time', '15')} mins", order_id))
        elif action == "reject": c.execute("UPDATE orders SET status='Rejected', estimated_time='Order Rejected' WHERE id=?", (order_id,))
        elif action == "extend": c.execute("UPDATE orders SET estimated_time=? WHERE id=?", (f"{request.form.get('extra_time', '10')} mins (Extended)", order_id))
        elif action == "ready": c.execute("UPDATE orders SET status='Ready to Pickup', estimated_time='Ready Now!' WHERE id=?", (order_id,))
        elif action == "completed":
            c.execute("UPDATE orders SET status='Completed', estimated_time='Done' WHERE id=?", (order_id,))
            c.execute("SELECT vendor_name, total_price FROM orders WHERE id=?", (order_id,)); order = c.fetchone()
            if order: c.execute("UPDATE vendors SET revenue = revenue + ?, orders_completed = orders_completed + 1 WHERE name=?", (order[1], order[0]))
        conn.commit(); conn.close()
    return redirect("/vendor")

@app.route("/vendor/add_food", methods=["POST"])
def vendor_add_food():
    if session.get("role") == "vendor":
        f = request.form; conn = sqlite3.connect("database.db"); c = conn.cursor()
        c.execute("INSERT INTO menu (vendor_name, item_name, price, icon, category, diet, description, is_customizable, half_price, addons) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (get_vendor_name(), f["item_name"], f["price"], f["icon"] or "fa-bowl-food", f["category"], f["diet"], f["description"], f.get("is_customizable", "No"), f.get("half_price") or 0, f.get("addons", "")))
        conn.commit(); conn.close()
    return redirect("/vendor")

@app.route("/vendor/delete_food/<int:id>", methods=["POST"])
def vendor_delete_food(id):
    if session.get("role") == "vendor":
        conn = sqlite3.connect("database.db"); c = conn.cursor(); c.execute("DELETE FROM menu WHERE id=? AND vendor_name=?", (id, get_vendor_name())); conn.commit(); conn.close()
    return redirect("/vendor")

@app.route("/vendor/toggle_food/<int:id>", methods=["POST"])
def vendor_toggle_food(id):
    if session.get("role") == "vendor":
        conn = sqlite3.connect("database.db"); c = conn.cursor(); c.execute("UPDATE menu SET availability = CASE WHEN availability='Available' THEN 'Unavailable' ELSE 'Available' END WHERE id=? AND vendor_name=?", (id, get_vendor_name())); conn.commit(); conn.close()
    return redirect("/vendor")

@app.route("/vendor/edit_food_price/<int:id>", methods=["POST"])
def vendor_edit_food_price(id):
    if session.get("role") == "vendor":
        conn = sqlite3.connect("database.db"); c = conn.cursor(); c.execute("UPDATE menu SET price=? WHERE id=? AND vendor_name=?", (request.form["new_price"], id, get_vendor_name())); conn.commit(); conn.close()
    return redirect("/vendor")

# ---------- APIS FOR DASHBOARD ----------
@app.route("/get_menu/<vendor_name>")
def get_menu(vendor_name):
    conn = sqlite3.connect("database.db"); c = conn.cursor(); c.execute("SELECT item_name, price, icon, category, diet, description, is_customizable, half_price, addons FROM menu WHERE vendor_name=? AND availability='Available'", (vendor_name,)); menu = c.fetchall(); conn.close()
    return jsonify([{"name": m[0], "price": m[1], "icon": m[2], "category": m[3], "diet": m[4], "desc": m[5], "is_customizable": m[6], "half_price": m[7], "addons": m[8]} for m in menu])

@app.route("/add_to_cart", methods=["POST"])
def add_to_cart():
    data = request.json; user = session["user"]; conn = sqlite3.connect("database.db"); c = conn.cursor()
    c.execute("SELECT quantity FROM cart WHERE username=? AND item=? AND vendor_name=?", (user, data["item"], data.get("vendor_name", "Unknown")))
    if c.fetchone(): c.execute("UPDATE cart SET quantity=quantity+1 WHERE username=? AND item=? AND vendor_name=?", (user, data["item"], data.get("vendor_name", "Unknown")))
    else: c.execute("INSERT INTO cart(username, vendor_name, item, price, quantity) VALUES(?, ?, ?, ?, ?)", (user, data.get("vendor_name", "Unknown"), data["item"], data["price"], 1))
    conn.commit(); conn.close(); return jsonify({"status": "added"})

@app.route("/get_cart")
def get_cart():
    conn = sqlite3.connect("database.db"); c = conn.cursor(); c.execute("SELECT item, price, quantity, vendor_name FROM cart WHERE username=?", (session["user"],)); items = c.fetchall(); conn.close(); return jsonify(items)

@app.route("/checkout", methods=["POST"])
def checkout():
    user = session["user"]; timestamp = datetime.now().strftime("%Y-%m-%d %I:%M %p"); conn = sqlite3.connect("database.db"); c = conn.cursor()
    c.execute("SELECT vendor_name, item, price, quantity FROM cart WHERE username=?", (user,)); cart_items = c.fetchall()
    for item in cart_items: c.execute("INSERT INTO orders (student_name, vendor_name, item, quantity, total_price, timestamp, status) VALUES (?, ?, ?, ?, ?, ?, 'Pending')", (user, item[0], item[1], item[3], item[2] * item[3], timestamp))
    c.execute("DELETE FROM cart WHERE username=?", (user,)); conn.commit(); conn.close(); log_act("Placed food order"); return jsonify({"status": "order_placed"})

@app.route("/update_quantity", methods=["POST"])
def update_quantity():
    data = request.json; c = sqlite3.connect("database.db").cursor();
    if data["action"] == "increase": c.execute("UPDATE cart SET quantity=quantity+1 WHERE username=? AND item=?", (session["user"], data["item"]))
    else: c.execute("UPDATE cart SET quantity=quantity-1 WHERE username=? AND item=?", (session["user"], data["item"])); c.execute("DELETE FROM cart WHERE username=? AND item=? AND quantity<=0", (session["user"], data["item"]))
    c.connection.commit(); return jsonify({"status": "updated"})

@app.route("/remove_item", methods=["POST"])
def remove_item():
    c = sqlite3.connect("database.db").cursor(); c.execute("DELETE FROM cart WHERE username=? AND item=?", (session["user"], request.json["item"])); c.connection.commit(); return jsonify({"status": "removed"})

@app.route("/api/search")
def search():
    query = request.args.get("q", "").lower()
    if not query: return jsonify([])
    conn = sqlite3.connect("database.db"); c = conn.cursor()
    c.execute("SELECT item_name, price, icon, category, diet, description, is_customizable, half_price, addons, vendor_name FROM menu WHERE LOWER(item_name) LIKE '%' || LOWER(?) || '%' AND availability='Available'", (query,))
    menu = c.fetchall(); conn.close()
    return jsonify([{"name": m[0], "price": m[1], "icon": m[2], "category": m[3], "diet": m[4], "desc": m[5], "is_customizable": m[6], "half_price": m[7], "addons": m[8], "vendor_name": m[9]} for m in menu])

@app.route("/api/rooms/check")
def check_rooms():
    date = request.args.get("date"); time_slot = request.args.get("time"); conn = sqlite3.connect("database.db"); c = conn.cursor()
    c.execute("SELECT room_name, status FROM rooms"); all_rooms = c.fetchall()
    c.execute("SELECT room_name FROM room_bookings WHERE booking_date=? AND time_slot=? AND status NOT IN ('Rejected', 'Completed')", (date, time_slot)); booked_rooms = [row[0] for row in c.fetchall()] 
    results = [{"name": r[0], "type": r[1], "status": "Occupied" if r[0] in booked_rooms else "Available"} for r in all_rooms]
    conn.close(); return jsonify(results)

@app.route("/api/rooms/book", methods=["POST"])
def book_room():
    data = request.json; user = session["user"]; booking_date = datetime.strptime(data["date"], "%Y-%m-%d").date(); today = datetime.now().date()
    if (booking_date - today).days < 0: return jsonify({"status": "error", "message": "Cannot book in the past!"})
    if (booking_date - today).days > 2: return jsonify({"status": "error", "message": "Max 48 hours in advance."})
    conn = sqlite3.connect("database.db"); c = conn.cursor()
    c.execute("SELECT id FROM room_bookings WHERE student_name=? AND booking_date >= ? AND status NOT IN ('Rejected', 'Completed')", (user, today.strftime("%Y-%m-%d")))
    if c.fetchone(): conn.close(); return jsonify({"status": "error", "message": "You already have an active room booking."})
    c.execute("INSERT INTO room_bookings (room_name, student_name, booking_date, time_slot, status) VALUES (?, ?, ?, ?, 'Pending')", (data["room"], user, data["date"], data["time"]))
    conn.commit(); conn.close(); log_act(f"Booked room {data['room']}")
    return jsonify({"status": "success", "message": "Room requested! Waiting for Admin approval."})

@app.route("/api/rooms/cancel", methods=["POST"])
def cancel_booking():
    data = request.json; user = session["user"]; conn = sqlite3.connect("database.db"); c = conn.cursor()
    c.execute("SELECT booking_date, time_slot FROM room_bookings WHERE id=? AND student_name=?", (data["id"], user)); booking = c.fetchone()
    if not booking: conn.close(); return jsonify({"status": "error", "message": "Booking not found."})
    start_datetime = datetime.strptime(f"{booking[0]} {booking[1].split(' - ')[0]}", "%Y-%m-%d %I:%M %p")
    if (start_datetime - datetime.now()).total_seconds() < 1800: conn.close(); return jsonify({"status": "error", "message": "Too late! You cannot cancel a room within 30 minutes of the start time."})
    c.execute("DELETE FROM room_bookings WHERE id=? AND student_name=?", (data["id"], user)); conn.commit(); conn.close()
    return jsonify({"status": "success", "message": "Booking canceled successfully!"})

@app.route("/api/rooms/complete", methods=["POST"])
def complete_booking():
    conn = sqlite3.connect("database.db"); c = conn.cursor(); c.execute("UPDATE room_bookings SET status='Completed' WHERE id=? AND student_name=?", (request.json["id"], session["user"])); conn.commit(); conn.close(); return jsonify({"status": "success", "message": "Room marked as Completed!"})

@app.route("/api/library/check")
def check_library_seats():
    location = request.args.get("location"); date = request.args.get("date"); time_slot = request.args.get("time")
    conn = sqlite3.connect("database.db"); c = conn.cursor()
    c.execute("SELECT seat_no FROM seats WHERE location=?", (location,))
    all_seats = [row[0] for row in c.fetchall()]
    c.execute("SELECT seat_no FROM library_bookings WHERE location=? AND booking_date=? AND time_slot=? AND status NOT IN ('Rejected', 'Completed')", (location, date, time_slot))
    booked_seats = [row[0] for row in c.fetchall()]
    results = [{"seat_no": s, "status": "Sold" if s in booked_seats else "Available"} for s in all_seats]
    conn.close(); return jsonify(results)

@app.route("/api/library/book", methods=["POST"])
def book_library_seat():
    data = request.json; user = session["user"]; booking_date = datetime.strptime(data["date"], "%Y-%m-%d").date(); today = datetime.now().date()
    if booking_date < today: return jsonify({"status": "error", "message": "Cannot book past dates!"})
    conn = sqlite3.connect("database.db"); c = conn.cursor()
    c.execute("SELECT id FROM library_bookings WHERE student_name=? AND status IN ('Pending', 'Approved')", (user,))
    if c.fetchone(): conn.close(); return jsonify({"status": "error", "message": "You already have an active library reservation."})
    c.execute("INSERT INTO library_bookings (location, seat_no, student_name, booking_date, time_slot, status) VALUES (?, ?, ?, ?, ?, 'Pending')", (data["location"], data["seat"], user, data["date"], data["time"]))
    conn.commit(); conn.close(); log_act(f"Reserved seat {data['seat']} at {data['location']}"); return jsonify({"status": "success", "message": "Seat requested! Waiting for Admin approval."})

@app.route("/api/library/cancel", methods=["POST"])
def cancel_library_booking():
    data = request.json; user = session["user"]; conn = sqlite3.connect("database.db"); c = conn.cursor()
    c.execute("SELECT id FROM library_bookings WHERE id=? AND student_name=?", (data["id"], user))
    if not c.fetchone(): conn.close(); return jsonify({"status": "error", "message": "Booking not found."})
    c.execute("DELETE FROM library_bookings WHERE id=? AND student_name=?", (data["id"], user)); conn.commit(); conn.close()
    return jsonify({"status": "success", "message": "Reservation canceled successfully!"})

@app.route("/api/library/complete", methods=["POST"])
def complete_library_booking():
    data = request.json; user = session["user"]; conn = sqlite3.connect("database.db"); c = conn.cursor()
    c.execute("UPDATE library_bookings SET status='Completed' WHERE id=? AND student_name=?", (data["id"], user)); conn.commit(); conn.close()
    return jsonify({"status": "success", "message": "Seat marked as Completed!"})

@app.route("/api/events/submit", methods=["POST"])
def submit_event():
    data = request.json
    try:
        submitted_date = datetime.strptime(data["date"], "%Y-%m-%d").date()
        if submitted_date < datetime.now().date(): return jsonify({"status": "error", "message": "Cannot submit an event on a past date!"})
    except ValueError: return jsonify({"status": "error", "message": "Invalid date format."})
    
    organizer = data.get("organizer", session["user"])
    creator = session["user"]
    category = data.get("category") or data.get("cat", "General")
    
    conn = sqlite3.connect("database.db"); c = conn.cursor()
    c.execute("INSERT INTO events (title, description, date, time, location, category, organizer, status, creator, registration_link) VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending', ?, ?)", (data["title"], data["desc"], data["date"], data["time"], data["location"], category, organizer, creator, data.get("reg_link", "")))
    conn.commit(); conn.close(); log_act(f"Proposed event: {data['title']}"); return jsonify({"status": "success", "message": "Event submitted! Waiting for Admin approval."})

@app.route("/api/events/owner_action", methods=["POST"])
def owner_event_action():
    event_id = request.json["id"]; action = request.json["action"]; user = session["user"]
    conn = sqlite3.connect("database.db"); c = conn.cursor(); c.execute("SELECT creator FROM events WHERE id=?", (event_id,)); ev = c.fetchone()
    if ev and ev[0] == user:
        if action == 'completed': c.execute("UPDATE events SET status='Completed' WHERE id=?", (event_id,))
        elif action == 'cancel': c.execute("DELETE FROM events WHERE id=? AND status='Pending'", (event_id,))
        conn.commit(); conn.close(); return jsonify({"status": "success", "message": f"Event marked as {action.capitalize()}!"})
    conn.close(); return jsonify({"status": "error", "message": "Unauthorized."})

@app.route("/api/events/rsvp", methods=["POST"])
def rsvp_event():
    event_id = request.json["id"]; user = session["user"]; conn = sqlite3.connect("database.db"); c = conn.cursor()
    c.execute("SELECT id FROM event_rsvps WHERE student_name=? AND event_id=?", (user, event_id))
    if not c.fetchone():
        c.execute("INSERT INTO event_rsvps (student_name, event_id) VALUES (?, ?)")
        c.execute("UPDATE events SET rsvp_count = rsvp_count + 1 WHERE id=?", (event_id,))
        conn.commit()
    conn.close(); log_act("RSVP'd to an event"); return jsonify({"status": "success"})

if __name__ == "__main__":
    app.run(debug=True)