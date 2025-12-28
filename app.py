from flask import Flask, request, jsonify
from flask_cors import CORS
from db import get_db_connection
from datetime import timedelta
app = Flask(__name__)
CORS(app, origins=[
    "http://localhost:3000",
    "https://your-react-site.netlify.app"
])
 # allow frontend

# --------- TEST HOME ---------
@app.route("/")
def home():
    return "Backend running successfully"

# --------- REGISTER ---------
@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No data received"}), 400

    name = data.get("name").strip()
    email = data.get("email").strip()
    mobile = data.get("mobile").strip()
    password = data.get("password").strip()

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
            if cursor.fetchone():
                return jsonify({"success": False, "message": "Email already exists"}), 400

            cursor.execute(
                "INSERT INTO users (name, email, phone, password) VALUES (%s,%s,%s,%s)",
                (name, email, mobile, password)
            )
            conn.commit()
            user_id = cursor.lastrowid
    finally:
        conn.close()

    return jsonify({"success": True, "message": "Registration successful", "user_id": user_id})

# --------- LOGIN ---------
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No data received"}), 400

    email = data.get("email").strip()
    password = data.get("password").strip()

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM users WHERE email=%s AND password=%s",
                (email, password)
            )
            user = cursor.fetchone()
    finally:
        conn.close()

    if user:
        return jsonify({
            "success": True,
            "message": "Login Successful",
            "user": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"]
            }
        })
    else:
        return jsonify({"success": False, "message": "Invalid Email or Password"}), 401

# --------- ADD APPOINTMENT ---------
# --------- ADD APPOINTMENT ---------
@app.route("/appointments", methods=["POST"])
def add_appointment():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No data received"}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:

            # 🔴 CHECK FOR TIME CONFLICT AND GET EXISTING SLOT
            conflict_sql = """
                SELECT date, start_time, end_time
                FROM appointments
                WHERE date = %s
                AND (%s < end_time AND %s > start_time)
            """

            cursor.execute(conflict_sql, (
                data["date"],
                data["startTime"],
                data["endTime"]
            ))

            conflict = cursor.fetchone()

            if conflict:
                return jsonify({
                    "success": False,
                    "message": f"Already booked on {conflict['date']} from {conflict['start_time']} to {conflict['end_time']}"
                }), 409

            # ✅ INSERT IF NO CONFLICT
            insert_sql = """
                INSERT INTO appointments
                (user_id, title, date, start_time, end_time, type, location, notes, status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """

            cursor.execute(insert_sql, (
                data["user_id"],
                data["title"],
                data["date"],
                data["startTime"],
                data["endTime"],
                data["type"],
                data.get("location", ""),
                data.get("notes", ""),
                data.get("status", "Pending")
            ))

            conn.commit()
            appointment_id = cursor.lastrowid

    finally:
        conn.close()

    return jsonify({
        "success": True,
        "message": "Appointment booked successfully",
        "id": appointment_id
    })


# --------- GET APPOINTMENTS (with optional date) ---------
@app.route("/appointments", methods=["GET"])
def get_all_appointments():
    date_filter = request.args.get("date")  # optional ?date=YYYY-MM-DD
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            if date_filter:
                cursor.execute(
                    "SELECT * FROM appointments WHERE date=%s ORDER BY date, start_time",
                    (date_filter,)
                )
            else:
                cursor.execute(
                    "SELECT * FROM appointments ORDER BY date, start_time"
                )
            data = cursor.fetchall()

            # Convert date and times to strings for JSON
            for appt in data:
                appt["date"] = appt["date"].strftime("%Y-%m-%d") if appt.get("date") else ""
                for key in ["start_time", "end_time"]:
                    val = appt.get(key)
                    if isinstance(val, timedelta):
                        total_seconds = int(val.total_seconds())
                        hours = total_seconds // 3600
                        minutes = (total_seconds % 3600) // 60
                        seconds = total_seconds % 60
                        appt[key] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                    elif val is not None:
                        appt[key] = str(val)
    finally:
        conn.close()

    return jsonify(data)


# --------- UPDATE APPOINTMENT ---------
@app.route("/appointments/<int:id>", methods=["PUT"])
def update_appointment(id):
    data = request.json

    conn = get_db_connection()
    cursor = conn.cursor()

    sql = """
        UPDATE appointments
        SET
            title=%s,
            date=%s,
            start_time=%s,
            end_time=%s,
            status=%s,
            location=%s,
            notes=%s
        WHERE id=%s
    """

    cursor.execute(sql, (
        data["title"],
        data["date"],
        data["start_time"],
        data["end_time"],
        data["status"],
        data.get("location"),
        data.get("notes"),
        id
    ))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "Appointment updated successfully"})


# --------- DELETE APPOINTMENT ---------
@app.route("/appointments/<int:id>", methods=["DELETE"])
def delete_appointment(id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM appointments WHERE id=%s", (id,))
    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({"message": "Appointment deleted"})
# --------- GET APPOINTMENTS BY DATE RANGE ---------
@app.route("/appointments/range", methods=["GET"])
def get_appointments_by_range():
    start_date = request.args.get("start")
    end_date = request.args.get("end")

    if not start_date or not end_date:
        return jsonify({"message": "Start and End date required"}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT * FROM appointments
                WHERE date BETWEEN %s AND %s
                ORDER BY date, start_time
            """, (start_date, end_date))

            data = cursor.fetchall()

            for appt in data:
                appt["date"] = appt["date"].strftime("%Y-%m-%d")
                appt["start_time"] = str(appt["start_time"])
                appt["end_time"] = str(appt["end_time"])
    finally:
        conn.close()

    return jsonify(data)


# --------- RUN APP ---------
if __name__ == "__main__":
   app.run(host="0.0.0.0", port=5000)

