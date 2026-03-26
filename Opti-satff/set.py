from flask import Blueprint, request, jsonify
from datetime import datetime
from database import get_connection

set_bp = Blueprint('set', __name__)

def get_break():
    """Get break time settings"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT break_start, break_end, break_min FROM opti_settings WHERE id = 1")
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    if result:
        return (
            result["break_start"],
            result["break_end"],
            result["break_min"]
        )
    return (
        datetime.strptime("12:00:00", "%H:%M:%S").time(),
        datetime.strptime("13:00:00", "%H:%M:%S").time(),
        60
    )

def get_work_hours():
    """Get work hours settings"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT work_start_time, work_end_time FROM opti_settings WHERE id = 1")
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    if result:
        return (
            result["work_start_time"],
            result["work_end_time"]
        )
    return (
        datetime.strptime("05:00:00", "%H:%M:%S").time(),
        datetime.strptime("21:00:00", "%H:%M:%S").time()
    )

def calc_break(time_in, time_out, break_start, break_end):
    """Calculate break time"""
    if not time_in or not time_out:
        return 0
    time_in_time = time_in.time()
    time_out_time = time_out.time()
    if time_in_time < break_end and time_out_time > break_start:
        break_duration = (break_end - break_start).total_seconds() // 60
        return break_duration
    return 0

def calc_work_hours(time_in, time_out, work_start, work_end):
    """Calculate time within work hours"""
    if not time_in or not time_out:
        return 0
    time_in_time = time_in.time()
    time_out_time = time_out.time()
    
    # Calculate overlap with work hours
    if time_in_time < work_end and time_out_time > work_start:
        # Calculate work hours duration
        if time_in_time < work_start:
            time_in_time = work_start
        if time_out_time > work_end:
            time_out_time = work_end
        
        work_duration = (time_out_time - time_in_time).total_seconds() // 60
        return max(0, work_duration)
    return 0

# =====================================================
# BREAK TIME API
# =====================================================
@set_bp.route("/api/get_break")
def get_break_api():
    break_start, break_end, break_min = get_break()
    return jsonify({
        "break_start": break_start.strftime("%H:%M"),
        "break_end": break_end.strftime("%H:%M"),
        "break_min": break_min
    })

@set_bp.route("/api/update_break", methods=["POST"])
def update_break():
    data = request.json
    break_start = datetime.strptime(data.get("break_start", "12:00"), "%H:%M").time()
    break_end = datetime.strptime(data.get("break_end", "13:00"), "%H:%M").time()
    break_min = int(data.get("break_min", 60))
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE opti_settings 
        SET break_start=%s, break_end=%s, break_min=%s 
        WHERE id=1
    """, (break_start, break_end, break_min))
    cursor.close()
    conn.close()
    return jsonify({
        "status": "success",
        "break_start": break_start.strftime("%H:%M"),
        "break_end": break_end.strftime("%H:%M"),
        "break_min": break_min
    })

# =====================================================
# WORK HOURS API
# =====================================================
@set_bp.route("/api/get_work_hours")
def get_work_hours_api():
    work_start, work_end = get_work_hours()
    return jsonify({
        "work_start": work_start.strftime("%H:%M"),
        "work_end": work_end.strftime("%H:%M")
    })

@set_bp.route("/api/update_work_hours", methods=["POST"])
def update_work_hours():
    data = request.json
    work_start = datetime.strptime(data.get("work_start", "05:00"), "%H:%M").time()
    work_end = datetime.strptime(data.get("work_end", "21:00"), "%H:%M").time()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE opti_settings 
        SET work_start_time=%s, work_end_time=%s 
        WHERE id=1
    """, (work_start, work_end))
    cursor.close()
    conn.close()
    return jsonify({
        "status": "success",
        "work_start": work_start.strftime("%H:%M"),
        "work_end": work_end.strftime("%H:%M")
    })

# =====================================================
# MANUAL ATTENDANCE API
# =====================================================
@set_bp.route("/api/manual_attendance", methods=["POST"])
def manual_attendance():
    data = request.json
    emp_id = int(data.get("emp_id"))
    action = data.get("action")  # "time_in", "time_out", "stop"
    time_in = data.get("time_in")
    time_out = data.get("time_out")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    if action == "time_in":
        now = datetime.now()
        cursor.execute("""
            INSERT INTO opti_rec (id_employee, time_in, manual_entry)
            VALUES (%s, %s, 1)
        """, (emp_id, now))
        
        cursor.execute("""
            SELECT id FROM opti_rec 
            WHERE id_employee=%s AND time_in=%s
        """, (emp_id, now))
        new_record = cursor.fetchone()
        
        cursor.close()
        conn.close()
        return jsonify({"status": "success", "record_id": new_record["id"]})
    
    elif action == "time_out":
        now = datetime.now()
        cursor.execute("""
            UPDATE opti_rec
            SET time_out=%s, manual_entry=1
            WHERE id=%s
        """, (now, data.get("record_id")))
        
        cursor.close()
        conn.close()
        return jsonify({"status": "success"})
    
    elif action == "stop":
        now = datetime.now()
        cursor.execute("""
            UPDATE opti_rec
            SET time_out=%s, stopped_by_admin=1
            WHERE id=%s AND time_out IS NULL
        """, (now, data.get("record_id")))
        
        cursor.close()
        conn.close()
        return jsonify({"status": "success"})
    
    return jsonify({"status": "error", "message": "Invalid action"})