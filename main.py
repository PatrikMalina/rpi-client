import asyncio
import json
import os
import time

import psutil
import requests

from settings import API_URL, CREDENTIAL_FILE, SECRET_KEY, RECONNECT_DELAY
from websocket import listen_for_commands

ID, KEY = None, None


def get_mac_address():
    for iface, add in psutil.net_if_addrs().items():
        for addr in add:
            if addr.family == psutil.AF_LINK and addr.address != '00:00:00:00:00:00':
                return addr.address
    return None


def load_credentials():
    if os.path.exists(CREDENTIAL_FILE):
        with open(CREDENTIAL_FILE, 'r') as file:
            return json.load(file)
    return None


def save_credentials(device_id, device_key):
    with open(CREDENTIAL_FILE, 'w') as file:
        json.dump({'id': device_id, 'key': device_key}, file)


def register_device():
    global ID, KEY
    while ID is None and KEY is None:
        data = {
            "mac_address": get_mac_address(),
            "secret_key": SECRET_KEY
        }
        headers = {"Content-Type": "application/json"}

        try:
            response = requests.post(f"{API_URL}/register-device/", json=data, headers=headers)
            response_data = response.json()
            status_code = response.status_code

        except requests.RequestException as e:
            print("Network error during registration:", e)
            response_data = None
            status_code = None

        if status_code == 200:
            ID = response_data['id']
            KEY = response_data['key']
            print(f"Device registered with ID: {ID} and Key: {KEY}")

            # Save credentials for future use
            save_credentials(ID, KEY)
        else:
            print(f"Registration failed, retrying in {RECONNECT_DELAY} seconds...")
            time.sleep(RECONNECT_DELAY)


def main():
    global ID, KEY
    credentials = load_credentials()

    if not credentials:
        register_device()
    else:
        ID = credentials['id']
        KEY = credentials['key']

    if ID and KEY:
        asyncio.run(listen_for_commands(ID, KEY))


if __name__ == '__main__':
    main()
