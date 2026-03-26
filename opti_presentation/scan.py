import serial
import requests
import time

ser = serial.Serial('COM3', 9600, timeout=1)

print("="*50)
print("RFID Scanner Started")
print("Waiting for scans...")
print("="*50)

last_uid = None
last_scan_time = 0
SCAN_DELAY = 3

def get_lcd_message(data):
    status = data.get("status", "")
    name   = data.get("name", "")[:14]
    if status == "time_in":
        return "Welcome!", name
    elif status == "time_out":
        return "See you tommorow", name
    elif status == "too_soon":
        return f"Wait {data.get('remaining','?')} min(s)", "Too Soon!"
    elif status == "not_found":
        return "Access Denied", "Unknown Card"
    elif status == "already_done":
        return "Already Done", "See you tmrw!"
    else:
        return "Unknown", "Try again"

while True:
    try:
        line = ser.readline().decode(errors='ignore').strip()

        if line.startswith("RFID Tag UID:"):
            uid = line.replace("RFID Tag UID:", "").strip().replace(" ", "").upper()

            current_time = time.time()
            if uid == last_uid and (current_time - last_scan_time) < SCAN_DELAY:
                continue
            last_uid = uid
            last_scan_time = current_time

            print("\n" + "="*50)
            print(f"SCAN DETECTED! UID: {uid}")
            print(f"Time: {time.strftime('%Y-%m-%d %I:%M:%S %p')}")
            print("="*50)

            try:
                response = requests.post(
                    "http://127.0.0.1:5000/scan",
                    json={"uid": uid},
                    timeout=3
                )

                # If server returns error, retry once
                if response.status_code == 500:
                    print("Server error 500, retrying once...")
                    time.sleep(0.5)
                    response = requests.post(
                        "http://127.0.0.1:5000/scan",
                        json={"uid": uid},
                        timeout=3
                    )

                data = response.json()
                print("Server Response:", data)

                line1, line2 = get_lcd_message(data)
                ser.write(f"{line1}|{line2}\n".encode("utf-8"))
                print(f"LCD: {line1} | {line2}")

            except requests.exceptions.RequestException as err:
                print("Connection Error:", err)
                ser.write(b"Server Error|Check backend\n")
            except Exception as err:
                print("Other Error:", err)
                ser.write(b"Server Error|Check backend\n")

            print("-"*50)

    except Exception as e:
        print("Error:", e)
        time.sleep(1)