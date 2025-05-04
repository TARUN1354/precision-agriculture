import streamlit as st
import serial
import time
import numpy as np
import random
import requests
from Adafruit_IO import Client
import serial.tools.list_ports
import json

# === Setup ===
st.set_page_config(layout="wide", page_title="Precision Agriculture")
st.title("🌱 Precision Agriculture Dashboard")

# === Adafruit IO Setup ===
ADAFRUIT_IO_USERNAME = "Tarun8482"
ADAFRUIT_IO_KEY = "aio_CWiw25QXaUpUHmmMiUvcR7ZRRfaP"
aio = Client(ADAFRUIT_IO_USERNAME, ADAFRUIT_IO_KEY)
soil_feed = aio.feeds('soil')
temp_feed = aio.feeds('temp')
light_feed = aio.feeds('light')

# === Fast2SMS Setup ===
PHONE = "9003786050"
SMS_API = "q2PBctlpr7xyXkRVoGQzfKbwh5ia9nLEgI8dNUHeSum3OJ6WDCpaldkP8BvMFtrbKZR5DW6S1403CJOT"
sms_sent = {"soil": False, "temperature": False, "humidity": False, "light": False}
danger_limits = {
    "soil": (30, 80),
    "temperature": (15, 40),
    "humidity": (30, 80),
    "light": (300, 900)
}

# === Q-learning Agent ===
class QLearningAgent:
    def __init__(self, name, state_size, action_size):
        self.name = name
        self.q_table = {}
        self.state_size = state_size
        self.action_size = action_size
        self.alpha = 0.1
        self.gamma = 0.9
        self.epsilon = 1.0
        self.epsilon_decay = 0.995
        self.epsilon_min = 0.01

    def get_state_key(self, state):
        return tuple(np.round(state, 2))

    def act(self, state):
        key = self.get_state_key(state)
        if key not in self.q_table:
            self.q_table[key] = np.zeros(self.action_size)
        if random.random() < self.epsilon:
            return random.choice(range(self.action_size))
        return np.argmax(self.q_table[key])

    def learn(self, state, action, reward, next_state):
        key = self.get_state_key(state)
        next_key = self.get_state_key(next_state)
        if key not in self.q_table:
            self.q_table[key] = np.zeros(self.action_size)
        if next_key not in self.q_table:
            self.q_table[next_key] = np.zeros(self.action_size)
        target = reward + self.gamma * np.max(self.q_table[next_key])
        self.q_table[key][action] += self.alpha * (target - self.q_table[key][action])
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay

sensor_types = ["soil", "temperature", "humidity", "light"]
actions = [0, 1, 2]
action_labels = ["Wait", "Actuate", "Alert"]
agents = {sensor: QLearningAgent(sensor, 1, len(actions)) for sensor in sensor_types}
alert_counts = {sensor: 0 for sensor in sensor_types}

def calculate_reward(sensor, value, action):
    low, high = danger_limits[sensor]
    if low <= value <= high:
        return 10 if action == 0 else 5
    else:
        return -5 if action == 0 else 0

def send_sms(message):
    url = "https://www.fast2sms.com/dev/bulkV2"
    headers = {
        'authorization': SMS_API,
        'Content-Type': "application/x-www-form-urlencoded"
    }
    payload = {
        'sender_id': 'FSTSMS',
        'message': message,
        'language': 'english',
        'route': 'q',
        'numbers': PHONE
    }
    try:
        res = requests.post(url, headers=headers, data=payload)
        st.success("📩 SMS sent!")
    except:
        st.warning("❌ SMS failed")

# === Auto Detect Serial Port ===
def get_serial_port():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if "USB" in port.description or "CP210" in port.description:
            return port.device
    return None

port = get_serial_port()
if port is None:
    st.error("⚠️ ESP32 not detected. Connect and restart.")
    st.stop()

ser = serial.Serial(port, 9600, timeout=1)
time.sleep(2)

# === Dashboard Layout ===
col1, col2 = st.columns(2)
with col1:
    soil_val = st.metric("🌿 Soil Moisture (%)", "0.00")
    temp_val = st.metric("🌡️ Temperature (°C)", "0.00")
with col2:
    humid_val = st.metric("💧 Humidity (%)", "0.00")
    light_val = st.metric("💡 Light Level", "0.00")

st.subheader("📉 Real-Time Sensor Trends")
chart = st.line_chart()

st.subheader("🔔 Alert Count Summary")
alert_box = st.json(alert_counts)

# === Stream Data Loop ===
while True:
    try:
       line = ser.readline().decode(errors='ignore').strip()
       if line and ',' in line:
            parts = line.split(',')
            if len(parts) == 4:
                soil = float(parts[0].replace("V", ""))
                temp = float(parts[1])
                humid = float(parts[2])
                light = float(parts[3])

                # Update metrics
                col1.metric("🌿 Soil Moisture (%)", f"{soil:.2f}")
                col1.metric("🌡️ Temperature (°C)", f"{temp:.2f}")
                col2.metric("💧 Humidity (%)", f"{humid:.2f}")
                col2.metric("💡 Light Level", f"{light:.2f}")

                # Update Adafruit IO
                aio.send(soil_feed.key, soil)
                aio.send(temp_feed.key, temp)
                aio.send(light_feed.key, light)

                # Update Chart
                chart.add_rows({"Soil": [soil], "Temp": [temp], "Humidity": [humid], "Light": [light]})

                # Process Q-learning and SMS
                values = {
                    "soil": soil,
                    "temperature": temp,
                    "humidity": humid,
                    "light": light
                }

                for sensor, value in values.items():
                    agent = agents[sensor]
                    state = np.array([value])
                    action = agent.act(state)
                    reward = calculate_reward(sensor, value, action)
                    agent.learn(state, action, reward, state)

                    if action == 2:
                        alert_counts[sensor] += 1

                    low, high = danger_limits[sensor]
                    if (value < low or value > high) and not sms_sent[sensor]:
                        send_sms(f"🚨 {sensor.upper()} ALERT: {value:.2f} out of range [{low}-{high}]")
                        sms_sent[sensor] = True
                    if low <= value <= high:
                        sms_sent[sensor] = False

                alert_box.json(alert_counts)

            time.sleep(2)

    except Exception as e:
        st.error(f"Reading error: {e}")
        time.sleep(3)