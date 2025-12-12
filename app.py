from flask import Flask, render_template, request, redirect, session, jsonify
from database import get_db, init_db
from werkzeug.security import generate_password_hash, check_password_hash
from ai_ml import predict_capacity_ml, load_model
from llm_integration import ask_llm
from flask import send_from_directory
import csv
import xml.etree.ElementTree as ET
import pandas as pd
from PyPDF2 import PdfReader

def insert_flight(db, row):
    if not isinstance(row, dict):
        row = row.to_dict()

    airline = row.get("airline", "").strip()
    flight_no = row.get("flight_no", "").strip()
    origin = row.get("origin", "").upper().strip()
    destination = row.get("destination", "").upper().strip()
    capacity = int(row.get("capacity", 0))
    cargo_type = row.get("cargo_type", "General").strip()

    date = str(row.get("date", "")).strip().replace("/", "-")

    parts = date.split("-")
    if len(parts) == 3 and len(parts[0]) == 2:
        date = f"{parts[2]}-{parts[1]}-{parts[0]}"

    db.execute("""
        INSERT INTO flights (airline, flight_no, origin, destination, date, capacity, cargo_type)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (airline, flight_no, origin, destination, date, capacity, cargo_type))

RATE_CARD = {
    "General": 12,            # ₹12 per kg
    "Pharma": 20,
    "Dangerous Goods": 35,
    "High Value": 50,
    "Perishables": 18,
    "Animals": 40
}

app = Flask(__name__)
app.secret_key = "secret123"

#init_db()


# --------------------------
# AUTH HELPERS
# --------------------------
def is_logged_in():
    return "user_id" in session


def current_role():
    return session.get("role")


# --------------------------
# HOME
# --------------------------
@app.route("/")
def home():
    return render_template("index.html")


# --------------------------
# REGISTER
# --------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])
        role = request.form["role"]

        db = get_db()
        try:
            db.execute("INSERT INTO users(username,password,role) VALUES(?,?,?)",
                       (username, password, role))
            db.commit()
            return redirect("/login")
        except:
            return "User already exists"

    return render_template("register.html")


# --------------------------
# LOGIN
# --------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            return redirect("/")
        return "Invalid credentials"

    return render_template("login.html")


# --------------------------
# LOGOUT
# --------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# --------------------------
# AIRLINE: Upload flight
# --------------------------
@app.route("/upload", methods=["GET", "POST"])
def upload():
    if current_role() != "airline":
        return "Unauthorized"

    if request.method == "POST":
        db = get_db()
        db.execute(
            """
            INSERT INTO flights(airline, flight_no, origin, destination, date, capacity, cargo_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.form["airline"],
                request.form["flight_no"],
                request.form["origin"],
                request.form["destination"],
                request.form["date"],
                request.form["capacity"],
                request.form["cargo_type"]
            )
        )
        db.commit()
        return render_template("upload.html", message="Flight uploaded!")

    return render_template("upload.html")


import csv, json, os
import pandas as pd  # for Excel
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


@app.route("/upload_csv", methods=["GET", "POST"])
def upload_csv():
    if current_role() != "airline":
        return "Unauthorized"

    message = ""

    if request.method == "POST":
        file = request.files.get("datafile")

        if not file:
            return render_template("upload_csv.html", message="No file selected!")

        filename = secure_filename(file.filename)
        if not filename.endswith(".csv"):
            return render_template("upload_csv.html", message="Only CSV files are allowed!")

        filepath = os.path.join("uploads", filename)
        file.save(filepath)

        db = get_db()

        try:
            with open(filepath, "r") as f:
                reader = csv.DictReader(f)

                for row in reader:
                    insert_flight(db, row)

            db.commit()
            message = "CSV flights uploaded successfully!"

        except Exception as e:
            message = f"Error uploading CSV: {str(e)}"

    return render_template("upload_csv.html", message=message)

def parse_csv(filepath, db):
    with open(filepath, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            insert_flight(db, row)





# SEARCH (AIRLINE view)
# --------------------------
@app.route("/search", methods=["GET", "POST"])
def search():
    if not is_logged_in():
        return redirect("/login")

    results = []
    interline = []

    if request.method == "POST":
        db = get_db()
        origin = request.form["origin"]
        dest = request.form["destination"]
        date = request.form["date"]
        cargo_type = request.form["cargo_type"]

        query = """
            SELECT * FROM flights 
            WHERE origin=? AND destination=? AND date=?
        """
        params = [origin, dest, date]

        if cargo_type:
            query += " AND cargo_type=?"
            params.append(cargo_type)

        results = db.execute(query, params).fetchall()

        first_legs = db.execute(
            "SELECT * FROM flights WHERE origin=? AND date=?",
            (origin, date)
        ).fetchall()

        second_legs = db.execute(
            "SELECT * FROM flights WHERE destination=? AND date=?",
            (dest, date)
        ).fetchall()

        for f1 in first_legs:
            for f2 in second_legs:
                if f1["destination"] == f2["origin"]:

                    if f1["cargo_type"] != f2["cargo_type"]:
                        continue

                    interline.append({
                        "legs": [f1, f2],
                        "capacity": min(f1["capacity"], f2["capacity"]),
                        "cargo_type": f1["cargo_type"]
                    })

    # remove duplicate interline routes
    unique = []
    seen = set()

    for r in interline:
        key = (r["legs"][0]["origin"], r["legs"][0]["destination"], r["legs"][1]["destination"], r["capacity"])
        if key not in seen:
            unique.append(r)
            seen.add(key)

    return render_template("search.html", results=results, interline=unique)


@app.route("/interline", methods=["GET", "POST"])
def interline():
    db = get_db()
    routes = []

    if request.method == "POST":
        origin = request.form["origin"].upper()
        destination = request.form["destination"].upper()
        date = request.form["date"]


        # Get all possible first-leg flights
        first_legs = db.execute(
            "SELECT * FROM flights WHERE origin=? AND date=?",
            (origin, date)
        ).fetchall()

        # Get all possible second-leg flights
        second_legs = db.execute(
            "SELECT * FROM flights WHERE destination=? AND date=?",
            (destination, date)
        ).fetchall()

        # MATCH INTERLINE CONNECTIONS
        for f1 in first_legs:
            for f2 in second_legs:
                if f1["destination"] == f2["origin"]:
                    routes.append({
                        "legs": [f1, f2],
                        "capacity": min(f1["capacity"], f2["capacity"])
                    })

    return render_template("interline.html", routes=routes)

# --------------------------
# FORWARDER SEARCH & BOOKING
# --------------------------
@app.route("/forwarder_search", methods=["GET", "POST"])
def forwarder_search():
    if current_role() != "forwarder":
        return "Unauthorized"

    db = get_db()
    results = []
    interline = []

    # 🔒 DEFAULTS (IMPORTANT – prevents Jinja crash)
    cheapest = None
    quickest = None
    best_value = None

    if request.method == "POST":
        origin = request.form["origin"].upper()
        dest = request.form["destination"].upper()
        date = request.form["date"]

        results = db.execute(
            "SELECT * FROM flights WHERE origin=? AND destination=? AND date=?",
            (origin, dest, date)
        ).fetchall()

        # --- Interline logic ---
        first_legs = db.execute(
            "SELECT * FROM flights WHERE origin=? AND date=?",
            (origin, date)
        ).fetchall()

        second_legs = db.execute(
            "SELECT * FROM flights WHERE destination=? AND date=?",
            (dest, date)
        ).fetchall()

        for f1 in first_legs:
            for f2 in second_legs:
                if f1["destination"] == f2["origin"]:
                    interline.append({
                        "legs": [f1, f2],
                        "capacity": min(f1["capacity"], f2["capacity"]),
                        "price": RATE_CARD.get(f1["cargo_type"], 15),
                        "transit": 12 + 8   # fake transit hours for demo
                    })

        # --- Build unified list for matrix ---
        all_options = []

        for f in results:
            all_options.append({
                "price": RATE_CARD.get(f["cargo_type"], 15),
                "transit": 12,   # demo value
                "flight": f
            })

        for r in interline:
            all_options.append({
                "price": r["price"],
                "transit": r["transit"],
                "flight": r
            })

        if all_options:
            cheapest = min(all_options, key=lambda x: x["price"])
            quickest = min(all_options, key=lambda x: x["transit"])
            best_value = min(all_options, key=lambda x: x["price"] * x["transit"])

    return render_template(
        "forwarder_search.html",
        results=results,
        interline=interline,
        cheapest=cheapest,
        quickest=quickest,
        best_value=best_value
    )

# --------------------------
# BOOKING
# --------------------------
@app.route("/book", methods=["POST"])
def book():
    if current_role() != "forwarder":
        return "Unauthorized"

    db = get_db()
    flight_id = request.form["flight_id"]

    actual_weight = float(request.form["actual_weight"])
    length = float(request.form["length"])
    width = float(request.form["width"])
    height = float(request.form["height"])

    # Fetch flight info
    flight = db.execute("SELECT * FROM flights WHERE id=?", (flight_id,)).fetchone()
    if not flight:
        return "Flight not found"

    # Volume weight
    volumetric_weight = (length * width * height) / 6000
    chargeable_weight = max(actual_weight, volumetric_weight)

    # Price
    cargo_type = flight["cargo_type"] or "General"
    rate = RATE_CARD.get(cargo_type, 15)
    total_price = rate * chargeable_weight

    # Capacity check
    if chargeable_weight > flight["capacity"]:
        return "Not enough capacity"

    new_capacity = flight["capacity"] - chargeable_weight
    db.execute("UPDATE flights SET capacity=? WHERE id=?", (new_capacity, flight_id))

    import time
    expires_at = int(time.time()) + 120

    # Insert booking
    db.execute("""
        INSERT INTO bookings(user_id, flight_id, actual_weight, volumetric_weight, 
        chargeable_weight, weight, status, expires_at, price, total, payment_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    (
        session["user_id"], flight_id,
        actual_weight, volumetric_weight, chargeable_weight,
        chargeable_weight,  # weight column used internally
        "HOLD", expires_at,
        rate, total_price, "UNPAID"
    ))

    db.commit()
    return redirect("/bookings")


# --------------------------
# VIEW BOOKINGS
# --------------------------
@app.route("/bookings")
def bookings_view():
    if not is_logged_in():
        return redirect("/login")

    db = get_db()
    import time
    now = int(time.time())

    # 1️⃣ Find expired HOLD bookings
    expired = db.execute(
        "SELECT * FROM bookings WHERE status='HOLD' AND expires_at < ?",
        (now,)
    ).fetchall()

    # 2️⃣ Auto-expire them + restore capacity
    for b in expired:
        flight = db.execute("SELECT * FROM flights WHERE id=?", (b["flight_id"],)).fetchone()

        # Restore capacity
        restored = flight["capacity"] + b["weight"]
        db.execute("UPDATE flights SET capacity=? WHERE id=?", (restored, b["flight_id"]))

        # Change status to EXPIRED
        db.execute("UPDATE bookings SET status='CANCELLED' WHERE id=?", (b["id"],))

    db.commit()

    bookings = db.execute("SELECT * FROM bookings").fetchall()

    return render_template("booking_management.html", bookings=bookings)




@app.route("/api/emirates")
def api_emirates():
    return jsonify([
        {"airline": "Emirates", "flight_no": "EK215", "origin": "DXB", "destination": "LAX", "date": "2025-12-10", "capacity": 9500, "cargo_type": "Pharma"},
        {"airline": "Emirates", "flight_no": "EK7", "origin": "DXB", "destination": "LHR", "date": "2025-12-10", "capacity": 8000, "cargo_type": "Dangerous Goods"}
    ])
@app.route("/api/qatar")
def api_qatar():
    return jsonify([
        {"airline": "Qatar Airways", "flight_no": "QR17", "origin": "DOH", "destination": "LHR", "date": "2025-12-10", "capacity": 8500, "cargo_type": "Pharma"},
        {"airline": "Qatar Airways", "flight_no": "QR571", "origin": "DEL", "destination": "DOH", "date": "2025-12-10", "capacity": 4800, "cargo_type": "General"}
    ])

@app.route("/api/lufthansa")
def api_lufthansa():
    return jsonify([
        {"airline": "Lufthansa", "flight_no": "LH401", "origin": "FRA", "destination": "JFK", "date": "2025-12-10", "capacity": 9000, "cargo_type": "Perishables"},
        {"airline": "Lufthansa", "flight_no": "LH900", "origin": "FRA", "destination": "LHR", "date": "2025-12-10", "capacity": 5500, "cargo_type": "General"}
    ])
@app.route("/api/klm")
def api_klm():
    return jsonify([
        {"airline": "KLM", "flight_no": "KL641", "origin": "AMS", "destination": "JFK", "date": "2025-12-10", "capacity": 6200, "cargo_type": "General"},
        {"airline": "KLM", "flight_no": "KL871", "origin": "DEL", "destination": "AMS", "date": "2025-12-10", "capacity": 4300, "cargo_type": "Perishables"}
    ])


@app.route("/api/british_airways")
def api_ba():
    return jsonify([
        {"airline": "British Airways", "flight_no": "BA108", "origin": "DXB", "destination": "LHR", "date": "2025-12-10", "capacity": 6500, "cargo_type": "High Value"},
        {"airline": "British Airways", "flight_no": "BA118", "origin": "DOH", "destination": "LHR", "date": "2025-12-10", "capacity": 7800, "cargo_type": "General"}
    ])

import requests

@app.route("/import_all_airlines", methods=["POST"])
def import_all_airlines():
    db = get_db()
    sources = [
        "http://127.0.0.1:5000/api/emirates",
        "http://127.0.0.1:5000/api/qatar",
        "http://127.0.0.1:5000/api/lufthansa",
        "http://127.0.0.1:5000/api/klm",
        "http://127.0.0.1:5000/api/british_airways"
    ]

    for url in sources:
        feed = requests.get(url).json()
        for f in feed:
            db.execute("""
                INSERT INTO flights(airline, flight_no, origin, destination, date, capacity, cargo_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (f["airline"], f["flight_no"], f["origin"], f["destination"], f["date"], f["capacity"], f["cargo_type"]))

    db.commit()
    return redirect("/big_feed")


@app.route("/big_feed")
def big_feed():
    flights = get_db().execute("SELECT * FROM flights WHERE capacity > 6000").fetchall()
    return render_template("big_airline_feed.html", flights=flights)

# --------------------------
# WORKSPACE
# --------------------------
@app.route("/workspace", methods=["GET", "POST"])
def workspace():
    db = get_db()
    if request.method == "POST":
        db.execute("INSERT INTO messages(sender,text) VALUES(?,?)",
                   (request.form["sender"], request.form["text"]))
        db.commit()

    messages = db.execute("SELECT * FROM messages").fetchall()
    return render_template("workspace.html", messages=messages)




@app.route("/confirm_booking", methods=["POST"])
def confirm_booking():
    booking_id = request.form["id"]

    db = get_db()
    b = db.execute("SELECT * FROM bookings WHERE id=?", (booking_id,)).fetchone()

    import time
    now = int(time.time())

    if b["status"] != "HOLD":
        return "Cannot confirm"

    if now > b["expires_at"]:
        return "Hold expired"

    db.execute("UPDATE bookings SET status='CONFIRMED' WHERE id=?", (booking_id,))
    db.commit()

    return redirect("/bookings")


@app.route("/airline_optimizer")
def airline_optimizer():
    if current_role() != "airline":
        return "Unauthorized"

    db = get_db()

    flights = db.execute("SELECT * FROM flights").fetchall()
    bookings = db.execute("SELECT * FROM bookings WHERE status='CONFIRMED'").fetchall()

    total_capacity = sum(f["capacity"] for f in flights)
    total_used = sum(b["weight"] for b in bookings)
    unused_capacity = total_capacity - total_used

    # Per route breakdown
    route_stats = {}
    for f in flights:
        key = f"{f['origin']} → {f['destination']}"
        if key not in route_stats:
            route_stats[key] = {"capacity": 0, "used": 0}

        route_stats[key]["capacity"] += f["capacity"]

    for b in bookings:
        flight = db.execute("SELECT * FROM flights WHERE id=?", (b["flight_id"],)).fetchone()
        key = f"{flight['origin']} → {flight['destination']}"
        route_stats[key]["used"] += b["weight"]

    recommendations = []

    for route, stats in route_stats.items():
        capacity = stats["capacity"]
        used = stats["used"]
        unused = capacity - used

        if unused > capacity * 0.50:
            recommendations.append({
                "route": route,
                "message": "⚠ High unused space. Consider offering discounts or interline partnerships."
            })
        elif used > capacity * 0.90:
            recommendations.append({
                "route": route,
                "message": "🔥 High demand! Increase pricing or add more frequency."
            })

    return render_template("airline_optimizer.html",
                           flights=flights,
                           bookings=bookings,
                           total_capacity=total_capacity,
                           total_used=total_used,
                           unused_capacity=unused_capacity,
                           route_stats=route_stats,
                           recommendations=recommendations)


@app.route("/ai/predict_capacity_ml", methods=["GET","POST"])
def predict_capacity_ml_route():
    """
    GET params: origin, destination, date (YYYY-MM-DD), cargo_type (optional)
    """
    data = request.get_json() if request.is_json else request.values
    origin = data.get("origin")
    destination = data.get("destination")
    date = data.get("date")
    cargo_type = data.get("cargo_type","General")
    if not origin or not destination:
        return jsonify({"ok": False, "error": "origin and destination required"}), 400
    try:
        res = predict_capacity_ml(origin, destination, date, cargo_type)
        return jsonify({"ok": True, "result": res})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/ai/chat", methods=["POST"])
def ai_chat():
    try:
        data = request.get_json()
        msg = data.get("message", "").upper()

        db = get_db()

        # ------------------------------------------
        # 1️⃣ AIRPORT EXTRACTION (Dynamic Detection)
        # ------------------------------------------
        airports = ["DEL","DXB","DOH","FRA","JFK","LHR","AMS","BOM","MAA","HYD"]

        origin = None
        destination = None

        for ap in airports:
            if f"{ap}" in msg:
                if origin is None:
                    origin = ap
                elif destination is None:
                    destination = ap

        # If user typed "FRA - JFK" or "FRA to JFK"
        import re
        match = re.findall(r'\b[A-Z]{3}\b', msg)
        if len(match) >= 2:
            origin = match[0]
            destination = match[1]

        # ------------------------------------------
        # 2️⃣ Give real route answer if airports found
        # ------------------------------------------
        if origin and destination:
            flights = db.execute(
                "SELECT airline, flight_no, capacity FROM flights WHERE origin=? AND destination=?",
                (origin, destination)
            ).fetchall()

            if flights:
                ans = f"Best routes from {origin} → {destination}:\n"
                for f in flights:
                    ans += f"• {f['airline']} {f['flight_no']} – Capacity: {f['capacity']} kg\n"
                return jsonify({"ok": True, "response": {"text": ans}})
            else:
                return jsonify({
                    "ok": True,
                    "response": {
                        "text": f"No direct flights found for {origin} → {destination}. Try checking interline routes."
                    }
                })

        # ------------------------------------------
        # 3️⃣ Special rules (pharma, dangerous goods, etc.)
        # ------------------------------------------
        if "PHARMA" in msg:
            return jsonify({"ok": True, "response": {
                "text": "Pharma cargo should use cold-chain routes. FRA → JFK recommended via Lufthansa Cargo."
            }})

        # ------------------------------------------
        # 4️⃣ Generic flight questions ("best route", "suggest", etc.)
        # ------------------------------------------
        if "ROUTE" in msg or "BEST" in msg or "SUGGEST" in msg:
            return jsonify({"ok": True, "response": {
                "text": "Tell me origin & destination (e.g., FRA → JFK) so I can find the best route."
            }})

        # ------------------------------------------
        # 5️⃣ DEFAULT HELP MESSAGE
        # ------------------------------------------
        return jsonify({
            "ok": True,
            "response": {
                "text": "Ask me things like:\n• Best route FRA to JFK\n• Capacity from DEL to DXB\n• Pharma cargo route advice"
            }
        })

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

from flask import send_file
from reportlab.pdfgen import canvas
import os

@app.route("/download_invoice/<int:booking_id>")
def download_invoice(booking_id):
    print("INVOICE ROUTE WORKING FOR ID:", booking_id)   # DEBUG PRINT

    db = get_db()

    booking = db.execute("SELECT * FROM bookings WHERE id=?", (booking_id,)).fetchone()
    if not booking:
        return "Booking not found"

    flight = db.execute("SELECT * FROM flights WHERE id=?", (booking['flight_id'],)).fetchone()

    # File path
    filepath = f"invoice_{booking_id}.pdf"

    # Create PDF
    c = canvas.Canvas(filepath)
    c.setFont("Helvetica", 12)

    c.drawString(40, 800, "CARGO AIRWAY BILL / INVOICE")
    c.drawString(40, 780, f"Invoice #: {booking_id}")
    c.drawString(40, 760, f"Flight: {flight['airline']} {flight['flight_no']}")
    c.drawString(40, 740, f"Route: {flight['origin']} → {flight['destination']}")
    c.drawString(40, 720, f"Date: {flight['date']}")

    c.drawString(40, 690, f"Actual Weight: {booking['actual_weight']} kg")
    c.drawString(40, 670, f"Volumetric Weight: {booking['volumetric_weight']:.2f} kg")
    c.drawString(40, 650, f"Chargeable Weight: {booking['chargeable_weight']:.2f} kg")

    c.drawString(40, 620, f"Rate per kg: ₹{booking['price']}")
    c.drawString(40, 600, f"Total Amount: ₹{booking['total']:.2f}")

    c.drawString(40, 560, "Thank you for choosing Cargo Network Portal!")
    c.save()

    return send_file(filepath, as_attachment=True)
from werkzeug.utils import secure_filename

PROFILE_UPLOAD_FOLDER = "profile_pics"
if not os.path.exists(PROFILE_UPLOAD_FOLDER):
    os.makedirs(PROFILE_UPLOAD_FOLDER)


@app.route("/profile")
def profile():
    if not is_logged_in():
        return redirect("/login")

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    return render_template("profile.html", user=user)


@app.route("/edit_profile", methods=["GET", "POST"])
def edit_profile():
    if not is_logged_in():
        return redirect("/login")

    db = get_db()

    if request.method == "POST":
        email = request.form["email"]
        phone = request.form["phone"]
        company = request.form["company"]

        # Profile Picture Upload
        file = request.files.get("profile_pic")
        filename = None
        if file and file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join(PROFILE_UPLOAD_FOLDER, filename))

            db.execute("UPDATE users SET profile_pic=? WHERE id=?", (filename, session["user_id"]))

        db.execute("""
            UPDATE users SET email=?, phone=?, company=? WHERE id=?
        """, (email, phone, company, session["user_id"]))

        db.commit()
        return redirect("/profile")

    user = db.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    return render_template("edit_profile.html", user=user)
@app.route('/profile_pics/<filename>')
def profile_pic(filename):
    return send_from_directory(PROFILE_UPLOAD_FOLDER, filename)

@app.route("/map")
def map_view():
    return render_template("map.html")
@app.route("/api/all_routes")
def api_all_routes():
    db = get_db()
    flights = db.execute("SELECT origin, destination FROM flights").fetchall()

    # airport coords: (Add more later)
    airport_coords = {
        "DEL": {"lat": 28.5562, "lng": 77.1000},
        "DXB": {"lat": 25.2532, "lng": 55.3657},
        "DOH": {"lat": 25.2854, "lng": 51.5310},
        "LHR": {"lat": 51.4700, "lng": -0.4543},
        "JFK": {"lat": 40.6413, "lng": -73.7781},
        "FRA": {"lat": 50.0379, "lng": 8.5622}
    }

    routes = []

    for f in flights:
        origin = airport_coords.get(f["origin"])
        dest = airport_coords.get(f["destination"])

        if origin and dest:
            routes.append({
                "startLat": origin["lat"],
                "startLng": origin["lng"],
                "endLat": dest["lat"],
                "endLng": dest["lng"]
            })

    return jsonify(routes)
@app.route("/chat/<int:booking_id>", methods=["GET", "POST"])
def chat(booking_id):
    db = get_db()

    booking = db.execute("SELECT * FROM bookings WHERE id=?", (booking_id,)).fetchone()
    if not booking:
        return "Booking not found"

    # Only airline or forwarder involved can chat
    user_id = session["user_id"]

    if request.method == "POST":
        msg = request.form["message"]
        db.execute("""
            INSERT INTO booking_messages(booking_id, sender_id, message, timestamp)
            VALUES (?, ?, ?, datetime('now'))
        """, (booking_id, user_id, msg))
        db.commit()
        return redirect(f"/chat/{booking_id}")

    messages = db.execute(
        "SELECT * FROM booking_messages WHERE booking_id=? ORDER BY id ASC",
        (booking_id,)
    ).fetchall()

    return render_template("chat.html", booking=booking, messages=messages)
@app.route("/chat/unread_count")
def unread_count():
    if "user_id" not in session:
        return jsonify({"unread": 0})

    db = get_db()
    unread = db.execute("""
        SELECT COUNT(*) AS c FROM booking_messages
        WHERE receiver_id = ? AND is_read = 0
    """, (session["user_id"],)).fetchone()["c"]

    return jsonify({"unread": unread})
@app.route("/cancel_booking/<int:id>")
def cancel_booking(id):
    db = get_db()
    b = db.execute("SELECT * FROM bookings WHERE id=?", (id,)).fetchone()

    import time
    now = int(time.time())
    elapsed = now - b["confirmed_at"]

    penalty_fee = 0

    if elapsed > 300:
        penalty_fee = 0.10 * b["total"]  # 🔥 10% penalty

    # restore capacity
    db.execute(
        "UPDATE flights SET capacity = capacity + ? WHERE id=?",
        (b["weight"], b["flight_id"])
    )

    db.execute("""
        UPDATE bookings
        SET status='CANCELLED', penalty_paid=?
        WHERE id=?
    """, (penalty_fee, id))

    db.commit()
    return redirect("/bookings")
@app.route("/modify_booking/<int:id>")
def modify_booking(id):
    db = get_db()
    b = db.execute("SELECT * FROM bookings WHERE id=?", (id,)).fetchone()

    import time
    elapsed = int(time.time()) - b["confirmed_at"]

    penalty = 0
    if elapsed > 300:
        penalty = 0.05 * b["total"]  # 5% modify fee

    return f"""
        Modify booking {id}<br>
        Penalty applicable: ₹{penalty:.2f}<br>
        (Demo screen)
    """

if __name__ == "__main__":
    with app.app_context():
        init_db()

    app.run(debug=True)
