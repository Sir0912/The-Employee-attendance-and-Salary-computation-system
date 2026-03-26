from flask import Flask, render_template, request, redirect, send_from_directory, url_for, session, jsonify, send_file
from flask_socketio import SocketIO
from datetime import datetime
import pymysql
from werkzeug.security import generate_password_hash, check_password_hash
import io, csv
import os
from datetime import timedelta
import threading
import time

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
app.secret_key = "blackpower"




# =====================================================
# DATABASE CONNECTION (SAFE VERSION - NO GLOBAL CURSOR)
# =====================================================
def get_connection():
    return pymysql.connect(
        host="localhost",
        user="root",
        password="Myservermybestfriend09941991294",
        database="opti_test",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )


# =====================================================
# ADMIN CREDENTIALS
# =====================================================
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_HASH = generate_password_hash("admin123")

# =====================================================
# HELPER FUNCTIONS
# =====================================================
def get_salary_per_minute():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT salary_per_minute FROM opti_settings WHERE id = 1")
    result = cursor.fetchone()

    cursor.close()
    conn.close()

    if result:
        return float(result["salary_per_minute"])
    return 5.00


# =====================================================
# AUTH ROUTES
# =====================================================
@app.route("/", methods=["GET"])
def landing_page():
    return render_template("admin_login.html", error=None)


@app.route("/log_in_admin", methods=["POST"])
def log_in_admin():
    
    admin = request.form.get("username")
    password = request.form.get("password")

    if admin == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
        session["admin"] = admin
        return redirect(url_for("admin_dashboard"))

    return render_template("admin_login.html", error="Invalid credentials")


@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("landing_page"))


# =====================================================
# DASHBOARD
# =====================================================
@app.route("/admin_dashboard")
def admin_dashboard():
    if "admin" not in session:
        return redirect(url_for("landing_page"))

    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT opti.name, opti_rec.time_in, opti_rec.time_out,
               opti_rec.duration, opti_rec.salary,
               opti_rec.late_minutes, opti_rec.undertime_minutes,
               opti_rec.id, opti_rec.id_employee
        FROM opti_rec
        JOIN opti ON opti_rec.id_employee = opti.id_employee
        WHERE DATE(opti_rec.time_in)=%s
        ORDER BY opti_rec.id DESC
    """, (today,))
    records = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) AS total FROM opti")
    total_employees = cursor.fetchone()["total"]

    cursor.execute("""SELECT COUNT(*) AS present FROM opti_rec WHERE DATE(time_in)=%s AND time_out IS NULL""", (today,))
    present_today = cursor.fetchone()["present"]

    cursor.execute("SELECT IFNULL(SUM(salary),0) AS total_salary FROM opti_rec WHERE DATE(time_in)=%s", (today,))
    total_salary = cursor.fetchone()["total_salary"]

    cursor.execute("SELECT * FROM opti ORDER BY id_employee ASC")
    employees = cursor.fetchall()

    cursor.close()
    conn.close()

    salary_rate = get_salary_per_minute()

    return render_template(
        "admin_dashboard.html",
        admin_name=session.get("admin", "Admin"),
        total_employees=total_employees,
        present_today=present_today,
        total_salary=total_salary,
        records=records,
        employees=employees,
        salary_rate=salary_rate
    )

# =====================================================
# EXPORT TO EXCEL (RESTORED - SAFE VERSION)
# =====================================================
@app.route("/export_excel")
def export_excel():
    if "admin" not in session:
        return redirect(url_for("landing_page"))

    today = datetime.now().strftime("%Y-%m-%d")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT opti.name, opti_rec.time_in, opti_rec.time_out,
               opti_rec.duration, opti_rec.salary
        FROM opti_rec
        JOIN opti ON opti_rec.id_employee = opti.id_employee
        WHERE DATE(opti_rec.time_in)=%s
        ORDER BY opti_rec.id DESC
    """, (today,))

    records = cursor.fetchall()

    cursor.close()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["Name", "Time In", "Time Out", "Duration (min)", "Salary"])

    for r in records:
        writer.writerow([
            r["name"],
            r["time_in"].strftime("%H:%M") if r["time_in"] else "",
            r["time_out"].strftime("%H:%M") if r["time_out"] else "",
            r.get("duration", ""),
            r.get("salary", "")
        ])

    output.seek(0)

    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"attendance_{today}.csv"
    )

# =====================================================
# HISTORY_RECORDS FOLDER & ARCHIVE FUNCTION
# =====================================================

@app.route("/history_records")
def history_records():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM opti_history ORDER BY created_at DESC")
    files = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("history_records.html", files=files)

@app.route("/history_download/<filename>")
def history_download(filename):
    return send_file(os.path.join(HISTORY_FOLDER, filename), as_attachment=True)

HISTORY_FOLDER = "history_records"
os.makedirs(HISTORY_FOLDER, exist_ok=True)

def archive_yesterday_records():
    conn = get_connection()
    cursor = conn.cursor()
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    cursor.execute("""
        SELECT o.name, r.time_in, r.time_out, r.duration, r.salary
        FROM opti_rec r
        JOIN opti o ON r.id_employee = o.id_employee
        WHERE DATE(r.time_in) = %s
    """, (yesterday,))
    records = cursor.fetchall()

    if records:
        filename = f"attendance_{yesterday}.csv"
        path = os.path.join(HISTORY_FOLDER, filename)
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Name", "Time In", "Time Out", "Duration (min)", "Salary"])
            for r in records:
                writer.writerow([
                    r["name"],
                    r["time_in"].strftime("%H:%M") if r["time_in"] else "",
                    r["time_out"].strftime("%H:%M") if r["time_out"] else "",
                    r.get("duration", ""),
                    r.get("salary", "")
                ])
        # save in history table
        cursor.execute("INSERT INTO opti_history (filename) VALUES (%s)", (filename,))
    
    cursor.close()
    conn.close()

HISTORY_FOLDER = os.path.join(os.getcwd(), "history_records")
os.makedirs(HISTORY_FOLDER, exist_ok=True)

@app.route("/history_records_api")
def history_records_api():
    files = [f for f in os.listdir(HISTORY_FOLDER) if f.endswith(".csv")]  # FIXED
    return jsonify(files)

@app.route("/history_records/download/<filename>")
def download_history_file(filename):
    return send_from_directory(HISTORY_FOLDER, filename, as_attachment=True)

# =====================================================
# SALARY RATE API
# =====================================================
@app.route("/api/get_salary_rate")
def get_salary_rate():
    return jsonify({"salary_per_minute": get_salary_per_minute()})


@app.route("/api/update_salary_rate", methods=["POST"])
def update_salary_rate():
    data = request.json
    new_rate = float(data.get("salary_per_minute", 5.00))

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE opti_settings SET salary_per_minute=%s WHERE id=1", (new_rate,))
    cursor.close()
    conn.close()

    return jsonify({"status": "success", "salary_per_minute": new_rate})


# =====================================================
# EMPLOYEE MANAGEMENT
# =====================================================
@app.route("/add_employee", methods=["POST"])
def add_employee():
    data = request.form
    conn = get_connection()
    cursor = conn.cursor()

    # Check for duplicate name
    cursor.execute("""
        SELECT id_employee FROM opti WHERE name=%s
    """, (data.get("name_inp"),))
    existing_name = cursor.fetchone()

    if existing_name:
        cursor.close()
        conn.close()
        return jsonify({"status": "error", "message": "Employee with this name already exists!"})

    # Check for duplicate RFID
    cursor.execute("""
        SELECT id_employee FROM opti WHERE rfid=%s
    """, (data.get("rfid_inp"),))
    existing_rfid = cursor.fetchone()

    if existing_rfid:
        cursor.close()
        conn.close()
        return jsonify({"status": "error", "message": "Employee with this RFID already exists!"})

    # Check for duplicate email
    cursor.execute("""
        SELECT id_employee FROM opti WHERE email=%s
    """, (data.get("email_inp"),))
    existing_email = cursor.fetchone()

    if existing_email:
        cursor.close()
        conn.close()
        return jsonify({"status": "error", "message": "Employee with this email already exists!"})

    # Find next available ID
    cursor.execute("SELECT id_employee FROM opti ORDER BY id_employee ASC")
    existing_ids = [row["id_employee"] for row in cursor.fetchall()]

    next_id = 1
    for eid in existing_ids:
        if eid == next_id:
            next_id += 1
        else:
            break

    # Insert new employee
    cursor.execute("""
        INSERT INTO opti (id_employee, name, age, sex, email, number, rfid)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
    """, (
        next_id,
        data.get("name_inp"),
        data.get("age_inp"),
        data.get("sex_inp"),
        data.get("email_inp"),
        data.get("num_inp"),
        data.get("rfid_inp"),
    ))

    cursor.execute("SELECT * FROM opti WHERE id_employee=%s", (next_id,))
    new_emp = cursor.fetchone()

    cursor.close()
    conn.close()

    return jsonify(new_emp)


@app.route("/drop_employee", methods=["POST"])
def drop_employee():
    emp_id = int(request.form.get("employ_id"))
    conn = get_connection()
    cursor = conn.cursor()
    # Just delete, don't renumber IDs
    cursor.execute("DELETE FROM opti WHERE id_employee=%s", (emp_id,))
    cursor.close()
    conn.close()
    return jsonify({"status": "success"})

# =====================================================
# SCAN RFID (UNCHANGED LOGIC)
# =====================================================
@app.route("/scan", methods=["POST"])
def scan():
    uid = request.json.get("uid").replace(" ", "").upper()
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")

    conn = get_connection()
    cursor = conn.cursor()

    # Find employee by RFID
    cursor.execute("""
        SELECT * FROM opti
        WHERE UPPER(REPLACE(rfid,' ',''))=%s
    """, (uid,))
    employee = cursor.fetchone()

    if not employee:
        cursor.close()
        conn.close()
        return jsonify({"status": "not_found"})

    # Check today's attendance record
    cursor.execute("""
        SELECT * FROM opti_rec
        WHERE id_employee=%s AND DATE(time_in)=%s
    """, (employee["id_employee"], today_str))
    record = cursor.fetchone()

    # ---------- TIME IN ----------
    if not record:
        cursor.execute("""
            INSERT INTO opti_rec (id_employee, time_in)
            VALUES (%s,%s)
        """, (employee["id_employee"], now))

        cursor.execute("""
            SELECT id FROM opti_rec
            WHERE id_employee=%s AND time_in=%s
        """, (employee["id_employee"], now))
        new_record = cursor.fetchone()

        # Compute present count and total salary
        cursor.execute("""
            SELECT COUNT(*) AS present
            FROM opti_rec
            WHERE DATE(time_in)=CURDATE() AND time_out IS NULL
        """)
        present_count = cursor.fetchone()["present"]

        cursor.execute("""
            SELECT IFNULL(SUM(salary),0) AS total_salary
            FROM opti_rec
            WHERE DATE(time_in)=CURDATE()
        """)
        total_salary = cursor.fetchone()["total_salary"]

        cursor.close()
        conn.close()

        socketio.emit("attendance_update", {
            "action": "time_in",
            "record_id": new_record["id"],
            "employee_id": employee["id_employee"],
            "name": employee["name"],
            "time_in": now.strftime("%I:%M %p"),
            "time_out": "-",
            "duration": 0,
            "salary": 0,
            "present_count": present_count,
            "total_salary": float(total_salary)
        })

        return jsonify({"status": "time_in"})

    # ---------- TIME OUT ----------
    elif record and not record["time_out"]:
        duration_min = int((now - record["time_in"]).total_seconds() // 60)
        salary = duration_min * get_salary_per_minute()

        cursor.execute("""
            UPDATE opti_rec
            SET time_out=%s, duration=%s, salary=%s
            WHERE id=%s
        """, (now, duration_min, salary, record["id"]))

        # Compute present count and total salary
        cursor.execute("""
            SELECT COUNT(*) AS present
            FROM opti_rec
            WHERE DATE(time_in)=CURDATE() AND time_out IS NULL
        """)
        present_count = cursor.fetchone()["present"]

        cursor.execute("""
            SELECT IFNULL(SUM(salary),0) AS total_salary
            FROM opti_rec
            WHERE DATE(time_in)=CURDATE()
        """)
        total_salary = cursor.fetchone()["total_salary"]

        cursor.close()
        conn.close()

        socketio.emit("attendance_update", {
            "action": "time_out",
            "record_id": record["id"],
            "employee_id": employee["id_employee"],
            "name": employee["name"],
            "time_in": record["time_in"].strftime("%I:%M %p"),
            "time_out": now.strftime("%I:%M %p"),
            "duration": duration_min,
            "salary": salary,
            "present_count": present_count,
            "total_salary": float(total_salary)
        })

        return jsonify({"status": "time_out"})

    else:
        cursor.close()
        conn.close()
        return jsonify({"status": "already_done"})


# =====================================================
# STATS API
# =====================================================
@app.route("/dashboard_stats_api")
def dashboard_stats_api():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) AS total FROM opti")
    total = cursor.fetchone()["total"]

    cursor.execute("""
        SELECT COUNT(*) AS present
        FROM opti_rec
        WHERE DATE(time_in)=CURDATE() AND time_out IS NULL
    """)
    present = cursor.fetchone()["present"]

    cursor.execute("""
        SELECT IFNULL(SUM(salary),0) AS total_salary
        FROM opti_rec
        WHERE DATE(time_in)=CURDATE()
    """)
    total_salary = cursor.fetchone()["total_salary"]

    cursor.close()
    conn.close()

    return jsonify({
        "total_employees": total,
        "present_today": present,
        "total_salary": float(total_salary)
    })
# =====================================================
# ATTENDANCE TABLE API (FIXED VERSION)
# =====================================================
@app.route("/attendance_table_api")
def attendance_table_api():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT r.id, o.name,
           DATE_FORMAT(r.time_in, '%h:%i %p') AS time_in,
           DATE_FORMAT(r.time_out, '%h:%i %p') AS time_out
    FROM opti_rec r
    JOIN opti o ON r.id_employee = o.id_employee
    WHERE DATE(r.time_in) = CURDATE()
    ORDER BY r.id DESC
""")
    records = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify(records)

# =====================================================
# SALARY TABLE API (FIXED)
# =====================================================
@app.route("/salary_table_api")
def salary_table_api():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT r.id, o.name, r.time_in, r.time_out, r.salary, r.duration
            FROM opti_rec r
            JOIN opti o ON r.id_employee = o.id_employee
            WHERE DATE(r.time_in) = CURDATE()
            ORDER BY r.id DESC
        """)
        records = cursor.fetchall()
        # Format time_in and time_out for display
        for r in records:
            if r["time_in"]:
                r["time_in"] = r["time_in"].strftime("%I:%M %p")
            if r["time_out"]:
                r["time_out"] = r["time_out"].strftime("%I:%M %p")
            else:
                r["time_out"] = "-"
        return jsonify(records)
    except Exception as e:
        print(f"Error in salary_table_api: {e}")
        return jsonify([]), 500
    finally:
        cursor.close()
        conn.close()
# =====================================================
# EDIT EMPLOYEE ROUTES
# =====================================================
@app.route("/edit_employee/<int:emp_id>")
def edit_employee(emp_id):
    if "admin" not in session:
        return redirect(url_for("landing_page"))
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM opti WHERE id_employee=%s", (emp_id,))
    employee = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not employee:
        return redirect(url_for("admin_dashboard"))
    
    return render_template("edit_employee.html", 
                          employee=employee, 
                          admin_name=session.get("admin", "Admin"))

@app.route("/api/get_employee/<int:emp_id>")
def get_employee(emp_id):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM opti WHERE id_employee=%s", (emp_id,))
    employee = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    if employee:
        return jsonify({"status": "success", "employee": employee})
    else:
        return jsonify({"status": "error", "message": "Employee not found"}), 404

# =====================================================
# UPDATE EMPLOYEE ROUTE
# =====================================================
@app.route("/update_employee", methods=["POST"])
def update_employee():
    data = request.form
    emp_id = int(data.get("id_inp"))

    conn = get_connection()
    cursor = conn.cursor()

    # Check for duplicate name (if changed)
    if data.get("name_inp") != data.get("old_name"):
        cursor.execute("""
            SELECT id_employee FROM opti 
            WHERE name=%s AND id_employee != %s
        """, (data.get("name_inp"), emp_id))
        existing_name = cursor.fetchone()
        
        if existing_name:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "Employee with this name already exists!"})

    # Check for duplicate RFID (if changed)
    if data.get("rfid_inp") != data.get("old_rfid"):
        cursor.execute("""
            SELECT id_employee FROM opti 
            WHERE rfid=%s AND id_employee != %s
        """, (data.get("rfid_inp"), emp_id))
        existing_rfid = cursor.fetchone()
        
        if existing_rfid:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "Employee with this RFID already exists!"})

    # Check for duplicate email (if changed)
    if data.get("email_inp") != data.get("old_email"):
        cursor.execute("""
            SELECT id_employee FROM opti 
            WHERE email=%s AND id_employee != %s
        """, (data.get("email_inp"), emp_id))
        existing_email = cursor.fetchone()
        
        if existing_email:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "Employee with this email already exists!"})

    # Update employee data (EXCEPT password)
    cursor.execute("""
        UPDATE opti 
        SET name=%s, age=%s, sex=%s, email=%s, number=%s, rfid=%s
        WHERE id_employee=%s
    """, (
        data.get("name_inp"),
        data.get("age_inp"),
        data.get("sex_inp"),
        data.get("email_inp"),
        data.get("num_inp"),
        data.get("rfid_inp"),
        emp_id
    ))

    cursor.execute("SELECT * FROM opti WHERE id_employee=%s", (emp_id,))
    updated_emp = cursor.fetchone()

    cursor.close()
    conn.close()

    return jsonify(updated_emp)

# =====================================================
# REAL-TIME SALARY UPDATE THREAD
# =====================================================
def update_salary_background():
    while True:
        time.sleep(1)  # Wait 1 seconds 
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get all active records (time_out IS NULL)
        cursor.execute("""
            SELECT r.id, r.time_in, r.duration, r.salary, o.name
            FROM opti_rec r
            JOIN opti o ON r.id_employee = o.id_employee
            WHERE DATE(r.time_in) = CURDATE() AND r.time_out IS NULL
        """)
        active_records = cursor.fetchall()
        
        salary_rate = get_salary_per_minute()
        
        for record in active_records:
            # Calculate new duration
            now = datetime.now()
            new_duration = int((now - record["time_in"]).total_seconds() // 60)
            new_salary = new_duration * salary_rate
            
            # Update database
            cursor.execute("""
                UPDATE opti_rec 
                SET duration=%s, salary=%s 
                WHERE id=%s
            """, (new_duration, new_salary, record["id"]))
            
            # Emit Socket.IO update
            socketio.emit("salary_update", {
                "record_id": record["id"],
                "name": record["name"],
                "duration": new_duration,
                "salary": new_salary,
                "time_in": record["time_in"].strftime("%I:%M %p")
            })
        
        cursor.close()
        conn.close()

# Start background thread (IMMEDIATELY)
salary_thread = threading.Thread(target=update_salary_background, daemon=True)
salary_thread.start()



if __name__ == "__main__":
    socketio.run(app, port=5000, debug=True)