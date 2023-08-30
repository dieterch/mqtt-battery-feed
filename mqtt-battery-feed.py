#!/usr/bin/env python

import datetime
from collections import deque
import json
import logging
import paho.mqtt.client as mqtt
import random
import requests
import threading
import time

logging.basicConfig(level=logging.WARNING)

VRM_Interval = 30
AVG_Interval = 5
current = 0.014
DATAIP = '192.168.12.20'
ErrValue = -1.0
SOCMode = 2

logging.info(f"Start, VRM_Interval={VRM_Interval}sec, AVG_Interval={AVG_Interval}sec, current estimation={current}A, DATAIP={DATAIP}")

def SOC(mode,x):
    def func(x, a, b, c):
        if x is not None:
            return a + (b * x) + (c * (x**2))
        else:
            return 0.0
    fitpar = {
        # 0. Resting, No discharge or charging
        0: [-159.95112679,  -35.66088984,    4.3840393 ],
        # 1. Discharging only
        1: [-7.99285673e+02,  7.14285645e+01,  2.90284783e-07],
        # 2. Charging 100% more than disccharge
        # 2: [-2065.96791137,   266.26220213,    -7.78670988],
        2: [1319.88515558, -286.95495698,   14.80478566],
	# 3. Charging, no discharge
        3: [-1271.8876316 ,   129.48610013,    -2.17261896]
    }
    val = func(x,*fitpar[mode])
    val = 10.0 if val < 10.0 else 100.0 if val > 100.0 else val
    return val

class DataAverage:

    def __init__(self, interval=1, max_retries=3):
        self.voltage_buffer = deque(maxlen=6)
        self.temperature_buffer = deque(maxlen=6)
        self.stop_signal = threading.Event()
        self.interval = interval
        self.max_retries = max_retries
        self.current_voltage_avg = None
        self.current_temperature_avg = None

    def fetch_data(self):
        retries = 0
        while retries < self.max_retries:
            #url = f"http://{DATAIP}/adc/0"
            url = f"http://{DATAIP}/status"
            try:
                response = requests.get(url, timeout=5)  # 5 seconds timeout for the request

                if response.status_code == 200:
                    data = response.json()
                    voltage = data.get('adcs',None)[0]['voltage']
                    temperature = data.get('ext_temperature',None)['0']['tC']
                    return voltage, temperature
                    #return data.get('voltage', None)
                else:
                    logging.warning(f"Failed to fetch data. HTTP Status Code: {response.status_code}")
                    retries += 1
            except requests.RequestException as e:
                #logging.warning(f"Error fetching data from {DATAIP}, Connection failed. retry {retries}")
                retries += 1
            time.sleep(1)  # wait for 1 second before retrying

        logging.warning(f"Max retries reached. Unable to fetch data from {DATAIP}.")
        return None, None

    def moving_average(self):
        while not self.stop_signal.is_set():
            # voltage
            voltage, temperature = self.fetch_data()
            if voltage is None:
                logging.info(f'Voltage is None! => setting voltage to {ErrValue}')
                self.voltage_buffer.clear()
                voltage = ErrValue

            if voltage is not None:
                self.voltage_buffer.append(voltage)

            if len(self.voltage_buffer) > 0:
                self.current_voltage_avg = sum(self.voltage_buffer) / len(self.voltage_buffer)

            # temperature
            if temperature is None:
                logging.info('Temperature is None! => setting temperature to {ErrValue}')
                self.temperature_buffer.clear()
                temperature = ErrValue

            if temperature is not None:
                self.temperature_buffer.append(temperature)

            if len(self.temperature_buffer) > 0:
                self.current_temperature_avg = sum(self.temperature_buffer) / len(self.temperature_buffer)

            time.sleep(self.interval)

    def start(self):
        thread = threading.Thread(target=self.moving_average)
        thread.start()

    def stop(self):
        self.stop_signal.set()

    def get_voltage_average(self):
        return self.current_voltage_avg

    def get_temperature_average(self):
        return self.current_temperature_avg


# Initialize the class with a 5-second interval
data_avg = DataAverage(interval=AVG_Interval)
# Start the voltage fetch and averaging in background ...
data_avg.start()

broker_address="venus.local"
client = mqtt.Client("P1") #create new instance

voltage = 0.0
try:
    while(True):
        time.sleep(VRM_Interval)
        try:
            voltage = data_avg.get_voltage_average()
            temperature = data_avg.get_temperature_average()
        except Exception as e:
            logging.warning(str(e))
            client = mqtt.Client("P1") #create new instance if connection fails ...
            time.sleep(5) # wait
        client.connect(broker_address)
        soc = SOC(SOCMode,voltage)
        voltage = voltage or ErrValue
        temperature = temperature or ErrValue
        power = current * voltage
        data = {
            "Dc": {
                "Power": power,
                "Voltage": voltage,
                "Temperature": temperature
            },
            "InstalledCapacity": 95.0,
            "Soc": soc
        }
        logging.info(f"datetime: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}, Current: {current:0.3f}A, Power: {power:.3f}W, Voltage: {voltage:.2f}V, Temperature: {temperature:.1f}°C, SOC: {soc:3.0f}%")
        client.publish("enphase/battery",json.dumps(data)) #push to local mqtt


except KeyboardInterrupt:
    # Stop fetching and averaging when user interrupts (e.g., Ctrl+C)
    logging.info('Quitting.')
    data_avg.stop()
