import pymysql
from datetime import datetime

def get_connection():
    return pymysql.connect(
        host="localhost",
        user="root",
        password="Myservermybestfriend09941991294",
        database="opti_test",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )

def get_break():
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

def calc_break(time_in, time_out, break_start, break_end):
    if not time_in or not time_out:
        return 0
    time_in_time = time_in.time()
    time_out_time = time_out.time()
    if time_in_time < break_end and time_out_time > break_start:
        break_duration = (break_end - break_start).total_seconds() // 60
        return break_duration
    return 0