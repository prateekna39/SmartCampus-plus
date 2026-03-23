from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
from datetime import datetime

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

    # SAFE UPGRADE: Advanced Features & Customizations
    columns_to_add = [
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
        ("menu", "is_customizable", "TEXT DEFAULT 'No'"), # NEW
        ("menu", "half_price", "INTEGER DEFAULT 0"),      # NEW
        ("menu", "addons", "TEXT DEFAULT ''"),            # NEW
        ("orders", "total_price", "INTEGER DEFAULT 0"),
        ("orders", "timestamp", "TEXT DEFAULT 'N/A'"),
        ("orders", "estimated_time", "TEXT DEFAULT 'Pending Vendor Approval'")
    ]
    for table, col, dtype in columns_to_add:
        try:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {dtype}")
        except sqlite3.OperationalError:
            pass 

    c.execute("INSERT OR IGNORE INTO users(username, password, role) VALUES('admin', 'admin123', 'admin')")
    conn.commit()
    conn.close()

init_db()

# ---------- AUTH ROUTES ----------

@app.route("/")
def home():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():
    username = request.form["username"]
    password = request.form["password"]

    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT username, role FROM users WHERE username=? AND password=?", (username, password))
    user = c.fetchone()
    conn.close()

    if user:
        session["user"] = user[0]
        session["role"] = user[1]
        if user[1] == "admin": return redirect("/admin")
        elif user[1] == "vendor": return redirect("/vendor")
        return redirect("/dashboard")
        
    return render_template("login.html", error="Invalid Credentials")

@app.route("/register", methods=["POST"])
def register():
    username = request.form["new_username"]
    password = request.form["new_password"]
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, 'student')", (username, password))
        conn.commit()
        msg = "Registration successful! You can now log in."
    except sqlite3.IntegrityError:
        msg = "Username already exists."
    finally:
        conn.close()
    return render_template("login.html", error=msg)

@app.route("/dashboard")
def dashboard():
    if "user" not in session or session.get("role") != "student": return redirect("/")
    
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT * FROM vendors WHERE status='Open'")
    vendors = c.fetchall()
    
    c.execute("SELECT id, vendor_name, item, quantity, total_price, status, estimated_time, timestamp FROM orders WHERE student_name=? AND status IN ('Pending', 'Preparing', 'Ready to Pickup') ORDER BY id DESC", (session["user"],))
    active_orders = c.fetchall()
    
    c.execute("SELECT id, vendor_name, item, quantity, total_price, status, timestamp FROM orders WHERE student_name=? AND status IN ('Completed', 'Rejected') ORDER BY id DESC", (session["user"],))
    past_orders = c.fetchall()

    # FETCH RESTORED DATA
    c.execute("SELECT * FROM rooms")
    rooms = c.fetchall()
    c.execute("SELECT * FROM seats")
    seats = c.fetchall()
    c.execute("SELECT * FROM events")
    events = c.fetchall()
    
    conn.close()
    return render_template("dashboard.html", user=session["user"], vendors=vendors, active_orders=active_orders, past_orders=past_orders, rooms=rooms, seats=seats, events=events)
# ---------- ADMIN ROUTES ----------

@app.route("/admin")
def admin_panel():
    if "user" not in session or session.get("role") != "admin": return redirect("/")
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT * FROM vendors")
    vendors = c.fetchall()
    c.execute("SELECT * FROM users WHERE role='student'")
    students = c.fetchall()
    c.execute("SELECT * FROM menu")
    menu_items = c.fetchall()
    c.execute("SELECT id, student_name, vendor_name, item, quantity, total_price, timestamp FROM orders WHERE status='Completed' ORDER BY id DESC")
    history = c.fetchall()

    # FETCH RESTORED DATA
    c.execute("SELECT * FROM rooms")
    rooms = c.fetchall()
    c.execute("SELECT * FROM seats")
    seats = c.fetchall()
    c.execute("SELECT * FROM events")
    events = c.fetchall()

    conn.close()
    return render_template("admin.html", vendors=vendors, students=students, menu_items=menu_items, history=history, rooms=rooms, seats=seats, events=events)

@app.route("/admin/add_vendor", methods=["POST"])
def add_vendor():
    if session.get("role") == "admin":
        f = request.form
        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        try:
            c.execute("INSERT INTO vendors (name, opening_time, closing_time, contact_name, phone, location) VALUES (?, ?, ?, ?, ?, ?)", 
                      (f["vendor_name"], f["opening_time"], f["closing_time"], f["contact_name"], f["phone"], f["location"]))
            c.execute("INSERT INTO users (username, password, role, vendor_name) VALUES (?, ?, 'vendor', ?)", 
                      (f["vendor_username"], f["vendor_password"], f["vendor_name"]))
            conn.commit()
        except: pass
        conn.close()
    return redirect("/admin")

@app.route("/admin/delete_vendor/<int:id>", methods=["POST"])
def delete_vendor(id):
    if session.get("role") == "admin":
        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("SELECT name FROM vendors WHERE id=?", (id,))
        vendor = c.fetchone()
        if vendor:
            c.execute("DELETE FROM menu WHERE vendor_name=?", (vendor[0],))
            c.execute("DELETE FROM users WHERE vendor_name=?", (vendor[0],)) 
            c.execute("DELETE FROM vendors WHERE id=?", (id,))
        conn.commit()
        conn.close()
    return redirect("/admin")

@app.route("/admin/toggle_vendor/<int:id>", methods=["POST"])
def toggle_vendor(id):
    if session.get("role") == "admin":
        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("UPDATE vendors SET status = CASE WHEN status='Open' THEN 'Closed' ELSE 'Open' END WHERE id=?", (id,))
        conn.commit()
        conn.close()
    return redirect("/admin")

@app.route("/admin/add_food", methods=["POST"])
def add_food():
    if session.get("role") == "admin":
        f = request.form
        icon = f["icon"] or "fa-bowl-food"
        is_custom = f.get("is_customizable", "No")
        half_price = f.get("half_price", 0) if f.get("half_price") else 0
        addons = f.get("addons", "")
        
        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("INSERT INTO menu (vendor_name, item_name, price, icon, category, diet, description, is_customizable, half_price, addons) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                  (f["vendor_name"], f["item_name"], f["price"], icon, f["category"], f["diet"], f["description"], is_custom, half_price, addons))
        conn.commit()
        conn.close()
    return redirect("/admin")

@app.route("/admin/delete_food/<int:id>", methods=["POST"])
def delete_food(id):
    if session.get("role") == "admin":
        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("DELETE FROM menu WHERE id=?", (id,))
        conn.commit()
        conn.close()
    return redirect("/admin")

@app.route("/admin/toggle_food/<int:id>", methods=["POST"])
def toggle_food(id):
    if session.get("role") == "admin":
        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("UPDATE menu SET availability = CASE WHEN availability='Available' THEN 'Unavailable' ELSE 'Available' END WHERE id=?", (id,))
        conn.commit()
        conn.close()
    return redirect("/admin")

@app.route("/admin/edit_food_price/<int:id>", methods=["POST"])
def edit_food_price(id):
    if session.get("role") == "admin":
        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("UPDATE menu SET price=? WHERE id=?", (request.form["new_price"], id))
        conn.commit()
        conn.close()
    return redirect("/admin")


# ---------- VENDOR ROUTES ----------

def get_vendor_name():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT vendor_name FROM users WHERE username=?", (session["user"],))
    v_name = c.fetchone()
    conn.close()
    return v_name[0] if v_name else "Unknown"

@app.route("/vendor")
def vendor_panel():
    if "user" not in session or session.get("role") != "vendor": return redirect("/")
    
    v_name = get_vendor_name()
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT id, student_name, item, quantity, status, total_price, estimated_time FROM orders WHERE vendor_name=? AND status NOT IN ('Completed', 'Rejected') ORDER BY id ASC", (v_name,))
    orders = c.fetchall()
    c.execute("SELECT * FROM menu WHERE vendor_name=?", (v_name,))
    menu_items = c.fetchall()
    conn.close()
    return render_template("vendor.html", vendor_name=v_name, orders=orders, menu_items=menu_items)

@app.route("/vendor/order_action/<int:order_id>", methods=["POST"])
def vendor_order_action(order_id):
    if session.get("role") == "vendor":
        action = request.form.get("action")
        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        
        if action == "accept":
            eta = f"{request.form.get('prep_time', '15')} mins"
            c.execute("UPDATE orders SET status='Preparing', estimated_time=? WHERE id=?", (eta, order_id))
        elif action == "reject":
            c.execute("UPDATE orders SET status='Rejected', estimated_time='Order Rejected' WHERE id=?", (order_id,))
        elif action == "extend":
            eta = f"{request.form.get('extra_time', '10')} mins (Extended)"
            c.execute("UPDATE orders SET estimated_time=? WHERE id=?", (eta, order_id))
        elif action == "ready":
            c.execute("UPDATE orders SET status='Ready to Pickup', estimated_time='Ready Now!' WHERE id=?", (order_id,))
        elif action == "completed":
            c.execute("UPDATE orders SET status='Completed', estimated_time='Done' WHERE id=?", (order_id,))
            c.execute("SELECT vendor_name, total_price FROM orders WHERE id=?", (order_id,))
            order = c.fetchone()
            if order:
                c.execute("UPDATE vendors SET revenue = revenue + ?, orders_completed = orders_completed + 1 WHERE name=?", (order[1], order[0]))
                
        conn.commit()
        conn.close()
    return redirect("/vendor")

@app.route("/vendor/add_food", methods=["POST"])
def vendor_add_food():
    if session.get("role") == "vendor":
        f = request.form
        icon = f["icon"] or "fa-bowl-food"
        v_name = get_vendor_name()
        is_custom = f.get("is_customizable", "No")
        half_price = f.get("half_price", 0) if f.get("half_price") else 0
        addons = f.get("addons", "")
        
        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("INSERT INTO menu (vendor_name, item_name, price, icon, category, diet, description, is_customizable, half_price, addons) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                  (v_name, f["item_name"], f["price"], icon, f["category"], f["diet"], f["description"], is_custom, half_price, addons))
        conn.commit()
        conn.close()
    return redirect("/vendor")

@app.route("/vendor/delete_food/<int:id>", methods=["POST"])
def vendor_delete_food(id):
    if session.get("role") == "vendor":
        v_name = get_vendor_name()
        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("DELETE FROM menu WHERE id=? AND vendor_name=?", (id, v_name))
        conn.commit()
        conn.close()
    return redirect("/vendor")

@app.route("/vendor/toggle_food/<int:id>", methods=["POST"])
def vendor_toggle_food(id):
    if session.get("role") == "vendor":
        v_name = get_vendor_name()
        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("UPDATE menu SET availability = CASE WHEN availability='Available' THEN 'Unavailable' ELSE 'Available' END WHERE id=? AND vendor_name=?", (id, v_name))
        conn.commit()
        conn.close()
    return redirect("/vendor")

@app.route("/vendor/edit_food_price/<int:id>", methods=["POST"])
def vendor_edit_food_price(id):
    if session.get("role") == "vendor":
        v_name = get_vendor_name()
        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("UPDATE menu SET price=? WHERE id=? AND vendor_name=?", (request.form["new_price"], id, v_name))
        conn.commit()
        conn.close()
    return redirect("/vendor")


# ---------- CART & ORDER APIs ----------

@app.route("/get_menu/<vendor_name>")
def get_menu(vendor_name):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT item_name, price, icon, category, diet, description, is_customizable, half_price, addons FROM menu WHERE vendor_name=? AND availability='Available'", (vendor_name,))
    menu = c.fetchall()
    conn.close()
    return jsonify([{"name": m[0], "price": m[1], "icon": m[2], "category": m[3], "diet": m[4], "desc": m[5], "is_customizable": m[6], "half_price": m[7], "addons": m[8]} for m in menu])

@app.route("/add_to_cart", methods=["POST"])
def add_to_cart():
    data = request.json
    user = session["user"]
    item = data["item"] # This string might now contain "(Half) + Naan"
    price = data["price"]
    vendor = data.get("vendor_name", "Unknown")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT quantity FROM cart WHERE username=? AND item=? AND vendor_name=?", (user, item, vendor))
    existing = c.fetchone()
    if existing: c.execute("UPDATE cart SET quantity=quantity+1 WHERE username=? AND item=? AND vendor_name=?", (user, item, vendor))
    else: c.execute("INSERT INTO cart(username, vendor_name, item, price, quantity) VALUES(?, ?, ?, ?, ?)", (user, vendor, item, price, 1))
    conn.commit()
    conn.close()
    return jsonify({"status": "added"})

@app.route("/get_cart")
def get_cart():
    user = session["user"]
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT item, price, quantity, vendor_name FROM cart WHERE username=?", (user,))
    items = c.fetchall()
    conn.close()
    return jsonify(items)

@app.route("/checkout", methods=["POST"])
def checkout():
    user = session["user"]
    timestamp = datetime.now().strftime("%Y-%m-%d %I:%M %p")
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT vendor_name, item, price, quantity FROM cart WHERE username=?", (user,))
    cart_items = c.fetchall()
    
    for item in cart_items:
        total = item[2] * item[3] 
        c.execute("INSERT INTO orders (student_name, vendor_name, item, quantity, total_price, timestamp, status) VALUES (?, ?, ?, ?, ?, ?, 'Pending')", 
                  (user, item[0], item[1], item[3], total, timestamp))
                  
    c.execute("DELETE FROM cart WHERE username=?", (user,))
    conn.commit()
    conn.close()
    return jsonify({"status": "order_placed"})

@app.route("/update_quantity", methods=["POST"])
def update_quantity():
    data = request.json; c = sqlite3.connect("database.db").cursor();
    if data["action"] == "increase": c.execute("UPDATE cart SET quantity=quantity+1 WHERE username=? AND item=?", (session["user"], data["item"]))
    else: c.execute("UPDATE cart SET quantity=quantity-1 WHERE username=? AND item=?", (session["user"], data["item"])); c.execute("DELETE FROM cart WHERE username=? AND item=? AND quantity<=0", (session["user"], data["item"]))
    c.connection.commit(); return jsonify({"status": "updated"})

@app.route("/remove_item", methods=["POST"])
def remove_item():
    c = sqlite3.connect("database.db").cursor(); c.execute("DELETE FROM cart WHERE username=? AND item=?", (session["user"], request.json["item"])); c.connection.commit(); return jsonify({"status": "removed"})

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)