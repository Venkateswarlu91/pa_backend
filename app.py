from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
from db import get_db_connection

app = Flask(__name__)
CORS(app)

# ------------------ UTIL ------------------
def delete_expired_appointments():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM appointments WHERE date < %s",
                (date.today(),)
            )
            conn.commit()
    finally:
        conn.close()

# ------------------ HOME ------------------
@app.route("/")
def home():
    return "Backend running successfully"

# ------------------ REGISTER ------------------
@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()

    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    mobile = data.get("mobile", "").strip()
    password = data.get("password", "").strip()

    if not name or not email or not password:
        return jsonify({"success": False, "message": "All fields required"}), 400

    hashed_password = generate_password_hash(password)

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
            if cursor.fetchone():
                return jsonify({"success": False, "message": "Email already exists"}), 400

            cursor.execute(
                "INSERT INTO users (name, email, phone, password) VALUES (%s,%s,%s,%s)",
                (name, email, mobile, hashed_password)
            )
            conn.commit()
    finally:
        conn.close()

    return jsonify({"success": True, "message": "Registration successful"}), 201

# ------------------ LOGIN ------------------
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email", "")
    password = data.get("password", "")

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, name, email, password FROM users WHERE email=%s",
                (email,)
            )
            user = cursor.fetchone()
    finally:
        conn.close()

    if not user or not check_password_hash(user["password"], password):
        return jsonify({"success": False, "message": "Invalid credentials"}), 401

    return jsonify({"success": True, "user": user}), 200

# ------------------ ADD APPOINTMENT ------------------
@app.route("/appointments", methods=["POST"])
def add_appointment():
    delete_expired_appointments()
    data = request.get_json()

    start_time = data.get("startTime") or data.get("start_time")
    end_time = data.get("endTime") or data.get("end_time")

    if not start_time or not end_time:
        return jsonify({"success": False, "message": "Start and end time required"}), 400

    appt_date = datetime.strptime(data["date"], "%Y-%m-%d").date()

    if appt_date < date.today():
        return jsonify({"success": False, "message": "Past date not allowed"}), 400

    if appt_date == date.today() and start_time <= datetime.now().strftime("%H:%M"):
        return jsonify({"success": False, "message": "Past time not allowed"}), 400

    if end_time <= start_time:
        return jsonify({"success": False, "message": "Invalid time range"}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id FROM appointments
                WHERE date=%s AND (%s < end_time AND %s > start_time)
            """, (data["date"], start_time, end_time))

            if cursor.fetchone():
                return jsonify({"success": False, "message": "Time slot already booked"}), 409

            cursor.execute("""
                INSERT INTO appointments
                (user_id, title, date, start_time, end_time, type, location, notes, status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                data["user_id"],
                data["title"],
                data["date"],
                start_time,
                end_time,
                data["type"],
                data.get("location", ""),
                data.get("notes", ""),
                "Pending"
            ))
            conn.commit()
    finally:
        conn.close()

    return jsonify({"success": True, "message": "Appointment added"}), 201

# ------------------ GET APPOINTMENTS ------------------
@app.route("/appointments", methods=["GET"])
def get_appointments():
    delete_expired_appointments()
    filter_date = request.args.get("date")

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            if filter_date:
                cursor.execute(
                    "SELECT * FROM appointments WHERE date=%s ORDER BY start_time",
                    (filter_date,)
                )
            else:
                cursor.execute(
                    "SELECT * FROM appointments ORDER BY date, start_time"
                )

            data = cursor.fetchall()
            for a in data:
                a["date"] = a["date"].strftime("%Y-%m-%d")
                a["start_time"] = str(a["start_time"])
                a["end_time"] = str(a["end_time"])
    finally:
        conn.close()

    return jsonify(data), 200





# ---------- GET APPOINTMENTS BY DATE RANGE ----------
@app.route("/appointments/range", methods=["GET"])
def get_appointments_by_range():

    start_date = request.args.get("start")
    end_date = request.args.get("end")

    if not start_date or not end_date:
        return jsonify({
            "success": False,
            "message": "start and end dates are required"
        }), 400

    try:
        start_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_obj = datetime.strptime(end_date, "%Y-%m-%d").date()

        if end_obj < start_obj:
            return jsonify({
                "success": False,
                "message": "End date cannot be before start date"
            }), 400

    except ValueError:
        return jsonify({
            "success": False,
            "message": "Invalid date format (YYYY-MM-DD)"
        }), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT *
                FROM appointments
                WHERE date BETWEEN %s AND %s
                ORDER BY date, start_time
            """, (start_date, end_date))

            appointments = cursor.fetchall()

            # format date & time
            for appt in appointments:
                appt["date"] = appt["date"].strftime("%Y-%m-%d")
                appt["start_time"] = str(appt["start_time"])
                appt["end_time"] = str(appt["end_time"])

    finally:
        conn.close()

    return jsonify({
        "success": True,
        "appointments": appointments
    }), 200

# ------------------ UPDATE APPOINTMENT ------------------
@app.route("/appointments/<int:id>", methods=["PUT"])
def update_appointment(id):
    delete_expired_appointments()
    data = request.get_json()

    start_time = data.get("startTime") or data.get("start_time")
    end_time = data.get("endTime") or data.get("end_time")

    if not start_time or not end_time:
        return jsonify({"success": False, "message": "Start and end time required"}), 400

    appt_date = datetime.strptime(data["date"], "%Y-%m-%d").date()

    if appt_date < date.today():
        return jsonify({"success": False, "message": "Past date not allowed"}), 400

    if end_time <= start_time:
        return jsonify({"success": False, "message": "Invalid time range"}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM appointments WHERE id=%s", (id,))
            if not cursor.fetchone():
                return jsonify({"success": False, "message": "Appointment not found"}), 404

            cursor.execute("""
                SELECT id FROM appointments
                WHERE date=%s AND id!=%s AND (%s < end_time AND %s > start_time)
            """, (data["date"], id, start_time, end_time))

            if cursor.fetchone():
                return jsonify({"success": False, "message": "Time conflict"}), 409

            cursor.execute("""
                UPDATE appointments
                SET title=%s, date=%s, start_time=%s, end_time=%s,
                    status=%s, location=%s, notes=%s
                WHERE id=%s
            """, (
                data["title"],
                data["date"],
                start_time,
                end_time,
                data.get("status", "Pending"),
                data.get("location", ""),
                data.get("notes", ""),
                id
            ))
            conn.commit()
    finally:
        conn.close()

    return jsonify({"success": True, "message": "Appointment updated"}), 200

# ------------------ DELETE APPOINTMENT ------------------
@app.route("/appointments/<int:id>", methods=["DELETE"])
def delete_appointment(id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM appointments WHERE id=%s", (id,))
            if cursor.rowcount == 0:
                return jsonify({"success": False, "message": "Not found"}), 404
            conn.commit()
    finally:
        conn.close()

    return jsonify({"success": True, "message": "Appointment deleted"}), 200

# ------------------ RUN ------------------

if __name__ == "__main__":
    app.run()
