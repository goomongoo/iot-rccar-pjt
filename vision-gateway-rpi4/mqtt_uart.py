import sys
import time
import json
import serial
import paho.mqtt.client as mqtt

BROKER_ADDRESS = "192.168.0.75"
PORT = 1883

TOPIC_SUB = "mobility/control/drive"
TOPIC_PUB = "mobility/telemetry/parsed"
TOPIC_ALERT = "mobility/alert/event"

SERIAL_PORT = '/dev/serial0'
BAUD_RATE = 115200

ser = None
client = None

def make_control_packet(throttle, steer):
    return f"$CMD,{throttle},{steer}\n"

def parse_telemetry(line):
    try:
        # line format: $TEL,AX,AY,AZ,GX,GY,GZ,DIST,THRO,STEER
        parts = line.split(',')
        if len(parts) != 10: return None

        payload = {
            "ts_ms": int(time.time() * 1000),
            "ax": int(parts[1]),
            "ay": int(parts[2]),
            "az": int(parts[3]),
            "gx": int(parts[4]),
            "gy": int(parts[5]),
            "gz": int(parts[6]),
            "dist_cm": int(parts[7]),
            "throttle": int(parts[8]),
            "steer": int(parts[9].strip())
        }
        return json.dumps(payload)
    except Exception as e:
        print(f"[Parse Error] {e}")
        return None

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print(f"Connected to Broker. Subscribing to {TOPIC_SUB}")
        client.subscribe(TOPIC_SUB)
    else:
        print(f"Connection Failed: {reason_code}")

def on_message(client, userdata, msg):
    try:
        payload_str = msg.payload.decode('utf-8')
        data = json.loads(payload_str)
        throttle = int(data.get("throttle", 0))
        steer = int(data.get("steer", 0))

        packet = make_control_packet(throttle, steer)
        if ser and ser.is_open:
            ser.write(packet.encode())
            print(f"[CMD TX] {packet.strip()}")
    except Exception as e:
        print(f"[CMD Error] {e}")

def init_serial():
    global ser
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
        ser.flush()
        print(f"Serial Opened: {SERIAL_PORT}")
    except Exception as e:
        print(f"Serial Error: {e}")
        sys.exit(1)

def main():
    global client
    init_serial()
    
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        client.connect(BROKER_ADDRESS, PORT)
        client.loop_start()
    except Exception as e:
        print(f"MQTT Error: {e}")
        sys.exit(1)

    print("=== Bridge Running (UART <-> MQTT) ===")

    try:
        while True:
            if ser.in_waiting > 0:
                try:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    
                    if line.startswith("$TEL"):
                        json_payload = parse_telemetry(line)
                        if json_payload:
                            client.publish(TOPIC_PUB, json_payload)
                            # print(f"[TEL Pub] {json_payload}")
                            
                    elif line.startswith("$STS"):
                        print(f"[STS RX] {line}")
                        
                        parts = line.split(',')
                        if len(parts) >= 2:
                            event_type = parts[1]
                            
                            alert_payload = {
                                "type": "ALERT",
                                "event": event_type,
                                "ts_ms": int(time.time() * 1000)
                            }
                            
                            client.publish(TOPIC_ALERT, json.dumps(alert_payload))
                            print(f"[ALERT Pub] {alert_payload}")
                        
                except Exception as e:
                    print(f"UART Read Error: {e}")

            time.sleep(0.001)

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        client.loop_stop()
        client.disconnect()
        if ser: ser.close()

if __name__ == '__main__':
    main()