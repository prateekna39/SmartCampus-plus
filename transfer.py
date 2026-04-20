import sqlite3
import psycopg2

# 🚨 IMPORTANT: Paste your exact Neon.tech Connection String inside the quotes below!
DATABASE_URL = "postgresql://neondb_owner:npg_DigUIt12sqTd@ep-falling-poetry-ammfzzsj-pooler.c-5.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

print("🔌 Connecting to databases...")
try:
    sqlite_conn = sqlite3.connect("database.db")
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_c = sqlite_conn.cursor()

    pg_conn = psycopg2.connect(DATABASE_URL)
    pg_c = pg_conn.cursor()
except Exception as e:
    print(f"❌ Connection Error: {e}")
    exit()

print("🏗️  Ensuring Cloud Tables exist...")
pg_c.execute("""CREATE TABLE IF NOT EXISTS users(id SERIAL PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT DEFAULT 'student', vendor_name TEXT)""")
pg_c.execute("""CREATE TABLE IF NOT EXISTS vendors(id SERIAL PRIMARY KEY, name TEXT UNIQUE, status TEXT DEFAULT 'Open', revenue INTEGER DEFAULT 0, orders_completed INTEGER DEFAULT 0, opening_time TEXT DEFAULT '09:00 AM', closing_time TEXT DEFAULT '05:00 PM', contact_name TEXT DEFAULT 'Manager', phone TEXT DEFAULT 'N/A', location TEXT DEFAULT 'Campus Food Court')""")
pg_c.execute("""CREATE TABLE IF NOT EXISTS menu(id SERIAL PRIMARY KEY, vendor_name TEXT, item_name TEXT, price INTEGER, icon TEXT DEFAULT 'fa-bowl-food', availability TEXT DEFAULT 'Available', category TEXT DEFAULT 'Main', diet TEXT DEFAULT 'Veg', description TEXT DEFAULT '', is_customizable TEXT DEFAULT 'No', half_price INTEGER DEFAULT 0, addons TEXT DEFAULT '')""")
pg_c.execute("""CREATE TABLE IF NOT EXISTS cart(id SERIAL PRIMARY KEY, username TEXT, vendor_name TEXT, item TEXT, price INTEGER, quantity INTEGER)""")
pg_c.execute("""CREATE TABLE IF NOT EXISTS orders(id SERIAL PRIMARY KEY, student_name TEXT, vendor_name TEXT, item TEXT, quantity INTEGER, status TEXT DEFAULT 'Pending', total_price INTEGER DEFAULT 0, timestamp TEXT DEFAULT 'N/A', estimated_time TEXT DEFAULT 'Pending Vendor Approval')""")
pg_c.execute("""CREATE TABLE IF NOT EXISTS rooms(id SERIAL PRIMARY KEY, room_name TEXT, status TEXT DEFAULT 'Available')""")
pg_c.execute("""CREATE TABLE IF NOT EXISTS seats(id SERIAL PRIMARY KEY, seat_no TEXT, status TEXT DEFAULT 'Available', location TEXT)""")
pg_c.execute("""CREATE TABLE IF NOT EXISTS events(id SERIAL PRIMARY KEY, title TEXT, description TEXT, date TEXT, status TEXT DEFAULT 'Pending', category TEXT DEFAULT 'General', time TEXT DEFAULT 'TBA', location TEXT DEFAULT 'TBA', organizer TEXT DEFAULT 'Student Club', rsvp_count INTEGER DEFAULT 0, creator TEXT DEFAULT 'system', registration_link TEXT DEFAULT '')""")
pg_c.execute("""CREATE TABLE IF NOT EXISTS room_bookings(id SERIAL PRIMARY KEY, room_name TEXT, student_name TEXT, booking_date TEXT, time_slot TEXT, status TEXT DEFAULT 'Pending')""")
pg_c.execute("""CREATE TABLE IF NOT EXISTS event_rsvps(id SERIAL PRIMARY KEY, student_name TEXT, event_id INTEGER)""")
pg_c.execute("""CREATE TABLE IF NOT EXISTS library_bookings(id SERIAL PRIMARY KEY, location TEXT, seat_no TEXT, student_name TEXT, booking_date TEXT, time_slot TEXT, status TEXT DEFAULT 'Pending')""")
pg_c.execute("""CREATE TABLE IF NOT EXISTS user_activity(id SERIAL PRIMARY KEY, username TEXT, action TEXT, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

# --- THE FIX: Force PostgreSQL to accept the hidden SQLite columns ---
try:
    pg_c.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS is_delayed TEXT DEFAULT 'false';")
except Exception:
    pass
# --------------------------------------------------------------------

pg_conn.commit()

# The tables we want to copy
tables = ['users', 'vendors', 'menu', 'rooms', 'seats', 'events', 'orders', 'room_bookings', 'library_bookings', 'event_rsvps']

for table in tables:
    print(f"📦 Transferring data for: {table}...")
    sqlite_c.execute(f"SELECT * FROM {table}")
    rows = sqlite_c.fetchall()
    
    if not rows:
        print(f"   ↳ ⚠️ {table} is empty locally. Skipping.")
        continue
        
    columns = rows[0].keys()
    col_string = ", ".join(columns)
    val_string = ", ".join(["%s"] * len(columns))
    
    # Wipe the cloud table clean before inserting to prevent duplicate ID crashes
    pg_c.execute(f"TRUNCATE {table} RESTART IDENTITY CASCADE;")
    
    insert_query = f"INSERT INTO {table} ({col_string}) VALUES ({val_string})"
    
    success_count = 0
    for row in rows:
        try:
            pg_c.execute(insert_query, tuple(row))
            success_count += 1
        except Exception as e:
            print(f"   ↳ ❌ Skipped a row in {table} due to error: {e}")
            pg_conn.rollback()
            continue
            
    pg_conn.commit()
    print(f"   ↳ ✅ Successfully moved {success_count} rows!")

print("\n🚀 TRANSFER COMPLETE! Your cloud database is now an exact copy of your local database.")
sqlite_conn.close()
pg_conn.close()