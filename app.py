from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
from datetime import datetime
import time

app = Flask(__name__)
app.secret_key = "smartcampus_secret"

# ---------- DATABASE ----------

def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT, role TEXT DEFAULT 'student', vendor_name TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS vendors(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, status TEXT DEFAULT 'Open')""")
    c.execute("""CREATE TABLE IF NOT EXISTS menu(id INTEGER PRIMARY KEY AUTOINCREMENT, vendor_name TEXT, item_name TEXT, price INTEGER, icon TEXT DEFAULT 'fa-bowl-food', availability TEXT DEFAULT 'Available')""")
    c.execute("""CREATE TABLE IF NOT EXISTS cart(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, vendor_name TEXT, item TEXT, price INTEGER, quantity INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT, student_name TEXT, vendor_name TEXT, item TEXT, quantity INTEGER, status TEXT DEFAULT 'Pending')""")
    c.execute("""CREATE TABLE IF NOT EXISTS rooms(id INTEGER PRIMARY KEY AUTOINCREMENT, room_name TEXT, status TEXT DEFAULT 'Available')""")
    c.execute("""CREATE TABLE IF NOT EXISTS seats(id INTEGER PRIMARY KEY AUTOINCREMENT, seat_no TEXT, status TEXT DEFAULT 'Available')""")
    c.execute("""CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, description TEXT, date TEXT)""")

    columns_to_add = [
        ("vendors", "revenue", "INTEGER DEFAULT 0"), ("vendors", "orders_completed", "INTEGER DEFAULT 0"),
        ("vendors", "opening_time", "TEXT DEFAULT '09:00 AM'"), ("vendors", "closing_time", "TEXT DEFAULT '05:00 PM'"),
        ("vendors", "contact_name", "TEXT DEFAULT 'N/A'"), ("vendors", "phone", "TEXT DEFAULT 'N/A'"), ("vendors", "location", "TEXT DEFAULT 'Campus Food Court'"),
        ("menu", "category", "TEXT DEFAULT 'Main'"), ("menu", "diet", "TEXT DEFAULT 'Veg'"), ("menu", "description", "TEXT DEFAULT ''"),
        ("menu", "is_customizable", "TEXT DEFAULT 'No'"), ("menu", "half_price", "INTEGER DEFAULT 0"), ("menu", "addons", "TEXT DEFAULT ''"),
        ("orders", "total_price", "INTEGER DEFAULT 0"), ("orders", "timestamp", "TEXT DEFAULT 'N/A'"), ("orders", "estimated_time", "TEXT DEFAULT 'Pending Vendor Approval'"),
        ("users", "status", "TEXT DEFAULT 'Active'"), ("orders", "is_delayed", "TEXT DEFAULT 'No'"), ("orders", "target_timestamp", "REAL DEFAULT 0")
    ]
    for table, col, dtype in columns_to_add:
        try: c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {dtype}")
        except sqlite3.OperationalError: pass 

    c.execute("INSERT OR IGNORE INTO users(username, password, role) VALUES('admin', 'admin123', 'admin')")
    c.execute("SELECT COUNT(*) FROM seats")
    if c.fetchone()[0] == 0:
        for i in range(1, 13): c.execute("INSERT INTO seats (seat_no) VALUES (?)", (f"L-Seat {i}",))
    conn.commit(); conn.close()

init_db()

# ---------- AUTH ROUTES ----------

@app.route("/")
def home(): return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():
    conn = sqlite3.connect("database.db"); c = conn.cursor()
    c.execute("SELECT username, role, status FROM users WHERE username=? AND password=?", (request.form["username"], request.form["password"]))
    user = c.fetchone(); conn.close()
    if user:
        if user[2] == 'Blocked': return render_template("login.html", error="Account Blocked.")
        session["user"], session["role"] = user[0], user[1]
        if user[1] == "admin": return redirect("/admin")
        elif user[1] == "vendor": return redirect("/vendor")
        return redirect("/dashboard")
    return render_template("login.html", error="Invalid Credentials")

@app.route("/register", methods=["POST"])
def register():
    conn = sqlite3.connect("database.db"); c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password, role, status) VALUES (?, ?, 'student', 'Active')", (request.form["new_username"], request.form["new_password"]))
        conn.commit(); msg = "Registration successful!"
    except: msg = "Username already exists."
    conn.close(); return render_template("login.html", error=msg)

@app.route("/logout")
def logout(): session.clear(); return redirect("/")

# ---------- STUDENT ROUTES ----------

@app.route("/dashboard")
def dashboard():
    if session.get("role") != "student": return redirect("/")
    conn = sqlite3.connect("database.db"); c = conn.cursor()
    c.execute("SELECT * FROM vendors WHERE status='Open'"); vendors = c.fetchall()
    c.execute("SELECT id, vendor_name, item, quantity, total_price, status, estimated_time, timestamp, target_timestamp FROM orders WHERE student_name=? AND status IN ('Pending', 'Preparing', 'Ready to Pickup') ORDER BY id DESC", (session["user"],))
    active_orders = c.fetchall()
    c.execute("SELECT id, vendor_name, item, quantity, total_price, status, timestamp FROM orders WHERE student_name=? AND status IN ('Completed', 'Rejected') ORDER BY id DESC", (session["user"],))
    past_orders = c.fetchall()
    c.execute("SELECT * FROM rooms"); rooms = c.fetchall()
    c.execute("SELECT * FROM seats"); seats = c.fetchall()
    c.execute("SELECT * FROM events ORDER BY id DESC"); events = c.fetchall()
    conn.close()
    return render_template("dashboard.html", user=session["user"], vendors=vendors, active_orders=active_orders, past_orders=past_orders, rooms=rooms, seats=seats, events=events)

@app.route("/api/search")
def search_food():
    q = request.args.get('q', '').lower(); conn = sqlite3.connect("database.db"); c = conn.cursor()
    c.execute("SELECT item_name, price, icon, category, diet, description, is_customizable, half_price, addons, vendor_name FROM menu WHERE availability='Available'")
    menu = c.fetchall(); conn.close(); results = []
    for m in menu:
        if q in m[0].lower() or q in m[5].lower() or q in m[9].lower():
            results.append({"name": m[0], "price": m[1], "icon": m[2], "category": m[3], "diet": m[4], "desc": m[5], "is_customizable": m[6], "half_price": m[7], "addons": m[8], "vendor_name": m[9]})
    return jsonify(results)

# FIXED: STUDENT AUTO-REFRESH API (Now tracks ETA too)
@app.route("/api/student/check_orders")
def check_student_orders():
    if session.get("role") != "student": return jsonify([])
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT id, status, estimated_time FROM orders WHERE student_name=? AND status NOT IN ('Completed', 'Rejected')", (session["user"],))
    orders = c.fetchall()
    conn.close()
    return jsonify([{"id": o[0], "status": o[1], "eta": o[2]} for o in orders])

# ---------- ADMIN ROUTES ----------

@app.route("/admin")
def admin_panel():
    if session.get("role") != "admin": return redirect("/")
    conn = sqlite3.connect("database.db"); c = conn.cursor()
    c.execute("SELECT * FROM vendors"); vendors = c.fetchall()
    c.execute("SELECT id, username, password, role, status FROM users WHERE role='student'"); students = c.fetchall()
    c.execute("SELECT * FROM menu"); menu_items = c.fetchall()
    c.execute("SELECT id, student_name, vendor_name, item, quantity, total_price, timestamp FROM orders WHERE status='Completed' ORDER BY id DESC"); history = c.fetchall()
    c.execute("SELECT * FROM rooms"); rooms = c.fetchall()
    c.execute("SELECT * FROM seats"); seats = c.fetchall()
    c.execute("SELECT * FROM events"); events = c.fetchall()
    conn.close()
    return render_template("admin.html", vendors=vendors, students=students, menu_items=menu_items, history=history, rooms=rooms, seats=seats, events=events)

@app.route("/admin/add_vendor", methods=["POST"])
def add_vendor():
    f = request.form; conn = sqlite3.connect("database.db"); c = conn.cursor()
    contact = f.get("contact_name", "").strip() or "N/A"; phone = f.get("phone", "").strip() or "N/A"
    try:
        c.execute("INSERT INTO vendors (name, opening_time, closing_time, contact_name, phone, location) VALUES (?, ?, ?, ?, ?, ?)", (f["vendor_name"], f["opening_time"], f["closing_time"], contact, phone, f["location"]))
        c.execute("INSERT INTO users (username, password, role, vendor_name, status) VALUES (?, ?, 'vendor', ?, 'Active')", (f["vendor_username"], f["vendor_password"], f["vendor_name"]))
        conn.commit()
    except: pass
    conn.close(); return redirect("/admin")

@app.route("/admin/edit_vendor/<int:id>", methods=["POST"])
def edit_vendor(id):
    f = request.form; conn = sqlite3.connect("database.db"); c = conn.cursor()
    c.execute("UPDATE vendors SET opening_time=?, closing_time=?, location=?, contact_name=?, phone=? WHERE id=?", (f["opening_time"], f["closing_time"], f["location"], f.get("contact_name", "N/A"), f.get("phone", "N/A"), id))
    conn.commit(); conn.close(); return redirect("/admin")

@app.route("/admin/delete_vendor/<int:id>", methods=["POST"])
def delete_vendor(id):
    conn = sqlite3.connect("database.db"); c = conn.cursor()
    c.execute("SELECT name FROM vendors WHERE id=?", (id,)); v = c.fetchone()
    if v: c.execute("DELETE FROM menu WHERE vendor_name=?", (v[0],)); c.execute("DELETE FROM users WHERE vendor_name=?", (v[0],)); c.execute("DELETE FROM vendors WHERE id=?", (id,))
    conn.commit(); conn.close(); return redirect("/admin")

@app.route("/admin/toggle_vendor/<int:id>", methods=["POST"])
def toggle_vendor(id):
    conn = sqlite3.connect("database.db"); c = conn.cursor(); c.execute("UPDATE vendors SET status = CASE WHEN status='Open' THEN 'Closed' ELSE 'Open' END WHERE id=?", (id,)); conn.commit(); conn.close(); return redirect("/admin")

@app.route("/admin/add_food", methods=["POST"])
def admin_add_food():
    f = request.form; conn = sqlite3.connect("database.db"); c = conn.cursor()
    c.execute("INSERT INTO menu (vendor_name, item_name, price, icon, category, diet, description, is_customizable, half_price, addons) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (f["vendor_name"], f["item_name"], f["price"], f["icon"] or "fa-bowl-food", f["category"], f["diet"], f["description"], f.get("is_customizable", "No"), f.get("half_price", 0) or 0, f.get("addons", "")))
    conn.commit(); conn.close(); return redirect("/admin")

@app.route("/admin/delete_food/<int:id>", methods=["POST"])
def admin_delete_food(id):
    conn = sqlite3.connect("database.db"); c = conn.cursor(); c.execute("DELETE FROM menu WHERE id=?", (id,)); conn.commit(); conn.close(); return redirect("/admin")

@app.route("/admin/toggle_food/<int:id>", methods=["POST"])
def admin_toggle_food(id):
    conn = sqlite3.connect("database.db"); c = conn.cursor(); c.execute("UPDATE menu SET availability = CASE WHEN availability='Available' THEN 'Unavailable' ELSE 'Available' END WHERE id=?", (id,)); conn.commit(); conn.close(); return redirect("/admin")

@app.route("/admin/edit_food_price/<int:id>", methods=["POST"])
def admin_edit_food_price(id):
    conn = sqlite3.connect("database.db"); c = conn.cursor(); c.execute("UPDATE menu SET price=? WHERE id=?", (request.form["new_price"], id)); conn.commit(); conn.close(); return redirect("/admin")

@app.route("/admin/edit_student/<int:id>", methods=["POST"])
def edit_student(id):
    conn = sqlite3.connect("database.db"); c = conn.cursor(); c.execute("UPDATE users SET username=?, password=? WHERE id=? AND role='student'", (request.form["username"], request.form["password"], id)); conn.commit(); conn.close(); return redirect("/admin")

@app.route("/admin/toggle_student/<int:id>", methods=["POST"])
def toggle_student(id):
    conn = sqlite3.connect("database.db"); c = conn.cursor(); c.execute("UPDATE users SET status = CASE WHEN status='Active' THEN 'Blocked' ELSE 'Active' END WHERE id=? AND role='student'", (id,)); conn.commit(); conn.close(); return redirect("/admin")

@app.route("/admin/delete_student/<int:id>", methods=["POST"])
def delete_student(id):
    conn = sqlite3.connect("database.db"); c = conn.cursor(); c.execute("DELETE FROM users WHERE id=? AND role='student'", (id,)); conn.commit(); conn.close(); return redirect("/admin")

@app.route("/admin/add_event", methods=["POST"])
def add_event():
    conn = sqlite3.connect("database.db"); c = conn.cursor(); c.execute("INSERT INTO events (title, description, date) VALUES (?, ?, ?)", (request.form["title"], request.form["description"], request.form["date"])); conn.commit(); conn.close(); return redirect("/admin")

@app.route("/admin/delete_event/<int:id>", methods=["POST"])
def delete_event(id):
    conn = sqlite3.connect("database.db"); c = conn.cursor(); c.execute("DELETE FROM events WHERE id=?", (id,)); conn.commit(); conn.close(); return redirect("/admin")

@app.route("/admin/toggle_room/<int:id>", methods=["POST"])
def toggle_room(id):
    conn = sqlite3.connect("database.db"); c = conn.cursor(); c.execute("UPDATE rooms SET status = CASE WHEN status='Available' THEN 'Occupied' ELSE 'Available' END WHERE id=?", (id,)); conn.commit(); conn.close(); return redirect("/admin")

@app.route("/admin/toggle_seat/<int:id>", methods=["POST"])
def toggle_seat(id):
    conn = sqlite3.connect("database.db"); c = conn.cursor(); c.execute("UPDATE seats SET status = CASE WHEN status='Available' THEN 'Occupied' ELSE 'Available' END WHERE id=?", (id,)); conn.commit(); conn.close(); return redirect("/admin")

# ---------- VENDOR ROUTES ----------

def get_vendor_name():
    conn = sqlite3.connect("database.db"); c = conn.cursor(); c.execute("SELECT vendor_name FROM users WHERE username=?", (session["user"],)); v = c.fetchone(); conn.close(); return v[0] if v else "Unknown"

@app.route("/vendor")
def vendor_panel():
    if session.get("role") != "vendor": return redirect("/")
    v_name = get_vendor_name()
    conn = sqlite3.connect("database.db"); c = conn.cursor()
    c.execute("SELECT id, student_name, item, quantity, status, total_price, estimated_time, target_timestamp FROM orders WHERE vendor_name=? AND status NOT IN ('Completed', 'Rejected') ORDER BY id ASC", (v_name,))
    orders = c.fetchall()
    c.execute("SELECT * FROM menu WHERE vendor_name=?", (v_name,)); menu_items = c.fetchall()
    today_date = datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT id, student_name, item, quantity, total_price, timestamp, is_delayed FROM orders WHERE vendor_name=? AND status='Completed' AND timestamp LIKE ? ORDER BY id DESC", (v_name, f"{today_date}%"))
    today_history = c.fetchall()
    today_revenue = sum(o[4] for o in today_history)
    delayed_count = sum(1 for o in today_history if o[6] == 'Yes')
    conn.close()
    return render_template("vendor.html", vendor_name=v_name, orders=orders, menu_items=menu_items, today_history=today_history, today_revenue=today_revenue, today_orders_count=len(today_history), delayed_count=delayed_count)

@app.route("/api/vendor/pending_count")
def vendor_pending_count():
    if session.get("role") != "vendor": return jsonify({"count": 0})
    conn = sqlite3.connect("database.db"); c = conn.cursor(); c.execute("SELECT COUNT(*) FROM orders WHERE vendor_name=? AND status='Pending'", (get_vendor_name(),)); count = c.fetchone()[0]; conn.close()
    return jsonify({"count": count})

@app.route("/vendor/order_action/<int:order_id>", methods=["POST"])
def vendor_order_action(order_id):
    action = request.form.get("action"); conn = sqlite3.connect("database.db"); c = conn.cursor()
    now_ts = time.time()
    
    if action == "accept": 
        mins = int(request.form.get('prep_time', '15'))
        target_ts = now_ts + (mins * 60)
        c.execute("UPDATE orders SET status='Preparing', estimated_time=?, target_timestamp=? WHERE id=?", (f"{mins} mins", target_ts, order_id))
    elif action == "reject": 
        c.execute("UPDATE orders SET status='Rejected', estimated_time='Order Rejected' WHERE id=?", (order_id,))
    elif action == "extend": 
        extra_mins = int(request.form.get('extra_time', '10'))
        c.execute("SELECT target_timestamp FROM orders WHERE id=?", (order_id,))
        current_target = c.fetchone()[0]
        if current_target == 0: current_target = now_ts
        new_target = current_target + (extra_mins * 60)
        c.execute("UPDATE orders SET estimated_time=?, is_delayed='Yes', target_timestamp=? WHERE id=?", (f"Extended by {extra_mins}m", new_target, order_id))
    elif action == "ready": 
        c.execute("UPDATE orders SET status='Ready to Pickup', estimated_time='Ready Now!' WHERE id=?", (order_id,))
    elif action == "completed":
        c.execute("UPDATE orders SET status='Completed', estimated_time='Done' WHERE id=?", (order_id,))
        c.execute("SELECT vendor_name, total_price FROM orders WHERE id=?", (order_id,)); order = c.fetchone()
        if order: c.execute("UPDATE vendors SET revenue = revenue + ?, orders_completed = orders_completed + 1 WHERE name=?", (order[1], order[0]))
        
    conn.commit(); conn.close(); return redirect("/vendor")

@app.route("/vendor/add_food", methods=["POST"])
def vendor_add_food():
    f = request.form; conn = sqlite3.connect("database.db"); c = conn.cursor()
    c.execute("INSERT INTO menu (vendor_name, item_name, price, icon, category, diet, description, is_customizable, half_price, addons) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (get_vendor_name(), f["item_name"], f["price"], f["icon"] or "fa-bowl-food", f["category"], f["diet"], f["description"], f.get("is_customizable", "No"), f.get("half_price", 0) or 0, f.get("addons", "")))
    conn.commit(); conn.close(); return redirect("/vendor")

@app.route("/vendor/delete_food/<int:id>", methods=["POST"])
def vendor_delete_food(id):
    conn = sqlite3.connect("database.db"); c = conn.cursor(); c.execute("DELETE FROM menu WHERE id=? AND vendor_name=?", (id, get_vendor_name())); conn.commit(); conn.close(); return redirect("/vendor")

@app.route("/vendor/toggle_food/<int:id>", methods=["POST"])
def vendor_toggle_food(id):
    conn = sqlite3.connect("database.db"); c = conn.cursor(); c.execute("UPDATE menu SET availability = CASE WHEN availability='Available' THEN 'Unavailable' ELSE 'Available' END WHERE id=? AND vendor_name=?", (id, get_vendor_name())); conn.commit(); conn.close(); return redirect("/vendor")

@app.route("/vendor/edit_food_price/<int:id>", methods=["POST"])
def vendor_edit_food_price(id):
    conn = sqlite3.connect("database.db"); c = conn.cursor(); c.execute("UPDATE menu SET price=? WHERE id=? AND vendor_name=?", (request.form["new_price"], id, get_vendor_name())); conn.commit(); conn.close(); return redirect("/vendor")

# ---------- CART APIs ----------
@app.route("/get_menu/<vendor_name>")
def get_menu(vendor_name):
    conn = sqlite3.connect("database.db"); c = conn.cursor(); c.execute("SELECT item_name, price, icon, category, diet, description, is_customizable, half_price, addons FROM menu WHERE vendor_name=? AND availability='Available'", (vendor_name,)); menu = c.fetchall(); conn.close()
    return jsonify([{"name": m[0], "price": m[1], "icon": m[2], "category": m[3], "diet": m[4], "desc": m[5], "is_customizable": m[6], "half_price": m[7], "addons": m[8], "vendor_name": vendor_name} for m in menu])

@app.route("/add_to_cart", methods=["POST"])
def add_to_cart():
    d = request.json; user = session["user"]; conn = sqlite3.connect("database.db"); c = conn.cursor()
    c.execute("SELECT quantity FROM cart WHERE username=? AND item=? AND vendor_name=?", (user, d["item"], d.get("vendor_name", "Unknown")))
    if c.fetchone(): c.execute("UPDATE cart SET quantity=quantity+1 WHERE username=? AND item=? AND vendor_name=?", (user, d["item"], d.get("vendor_name", "Unknown")))
    else: c.execute("INSERT INTO cart(username, vendor_name, item, price, quantity) VALUES(?, ?, ?, ?, ?)", (user, d.get("vendor_name", "Unknown"), d["item"], d["price"], 1))
    conn.commit(); conn.close(); return jsonify({"status": "added"})

@app.route("/get_cart")
def get_cart():
    conn = sqlite3.connect("database.db"); c = conn.cursor(); c.execute("SELECT item, price, quantity, vendor_name FROM cart WHERE username=?", (session["user"],)); items = c.fetchall(); conn.close(); return jsonify(items)

@app.route("/checkout", methods=["POST"])
def checkout():
    user = session["user"]; ts = datetime.now().strftime("%Y-%m-%d %I:%M %p"); conn = sqlite3.connect("database.db"); c = conn.cursor()
    c.execute("SELECT vendor_name, item, price, quantity FROM cart WHERE username=?", (user,)); cart = c.fetchall()
    for item in cart: c.execute("INSERT INTO orders (student_name, vendor_name, item, quantity, total_price, timestamp, status) VALUES (?, ?, ?, ?, ?, ?, 'Pending')", (user, item[0], item[1], item[3], item[2]*item[3], ts))
    c.execute("DELETE FROM cart WHERE username=?", (user,)); conn.commit(); conn.close(); return jsonify({"status": "order_placed"})

@app.route("/update_quantity", methods=["POST"])
def update_quantity():
    d = request.json; c = sqlite3.connect("database.db").cursor()
    if d["action"] == "increase": c.execute("UPDATE cart SET quantity=quantity+1 WHERE username=? AND item=?", (session["user"], d["item"]))
    else: c.execute("UPDATE cart SET quantity=quantity-1 WHERE username=? AND item=?", (session["user"], d["item"])); c.execute("DELETE FROM cart WHERE username=? AND item=? AND quantity<=0", (session["user"], d["item"]))
    c.connection.commit(); return jsonify({"status": "updated"})

@app.route("/remove_item", methods=["POST"])
def remove_item():
    c = sqlite3.connect("database.db").cursor(); c.execute("DELETE FROM cart WHERE username=? AND item=?", (session["user"], request.json["item"])); c.connection.commit(); return jsonify({"status": "removed"})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)