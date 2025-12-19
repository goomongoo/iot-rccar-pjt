# collect.py  (paho-mqtt v2 compatible)
import sys
import json
import time
import csv
import paho.mqtt.client as mqtt

BROKER = "192.168.0.75"
PORT = 1883
CMD_TOPIC = "mobility/control/drive"
TEL_TOPIC = "mobility/telemetry/parsed"

throttle = int(sys.argv[1])
steer = int(sys.argv[2])
duration = float(sys.argv[3])      # seconds
out_csv = sys.argv[4]

fields = [
    "ts_ms", "ax", "ay", "az",
    "gx", "gy", "gz",
    "dist_cm", "throttle", "steer"
]

rows = []

# v2 callback signature
def on_message(client, userdata, message):
    try:
        data = json.loads(message.payload.decode())
        rows.append({k: data.get(k, "") for k in fields})
    except Exception as e:
        print("[WARN] parse failed:", e)

client = mqtt.Client(
    client_id="rpi5-collector",
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2
)

client.on_message = on_message
client.connect(BROKER, PORT, 30)
client.subscribe(TEL_TOPIC, qos=1)
client.loop_start()

# send command
cmd = json.dumps({"throttle": throttle, "steer": steer})
client.publish(CMD_TOPIC, cmd, qos=1)

time.sleep(duration)

# stop
client.publish(CMD_TOPIC, json.dumps({"throttle": 0, "steer": 0}), qos=1)
time.sleep(0.2)

client.loop_stop()
client.disconnect()

# append CSV
write_header = False
try:
    with open(out_csv, "r"):
        pass
except FileNotFoundError:
    write_header = True

with open(out_csv, "a", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    if write_header:
        writer.writeheader()
    writer.writerows(rows)

print(f"[DONE] wrote {len(rows)} rows -> {out_csv}")

