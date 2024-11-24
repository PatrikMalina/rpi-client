import asyncio
import json
import os
import uuid
from enum import Enum

import requests

from settings import BASE_URL, CREDENTIAL_FILE, SECRET_KEY
from websocket import listen_for_commands

ID, KEY = None, None


class ApiEndpoints(Enum):
    REGISTER_DEVICE = ("POST", f"{BASE_URL}/api/v1/device_manager/register-device/")

    def method(self):
        return self.value[0]

    def url(self):
        return self.value[1]


# Function to get the MAC address
def get_mac_address():
    mac = ':'.join(['{:02x}'.format((uuid.getnode() >> i) & 0xff) for i in range(0, 8 * 6, 8)][::-1])
    return mac


# Function to load credentials from file
def load_credentials():
    if os.path.exists(CREDENTIAL_FILE):
        with open(CREDENTIAL_FILE, 'r') as file:
            return json.load(file)
    return None


# Function to save credentials to file
def save_credentials(device_id, device_key):
    with open(CREDENTIAL_FILE, 'w') as file:
        json.dump({'id': device_id, 'key': device_key}, file)


def send_request(endpoint: ApiEndpoints, data=None, headers=None):
    method = endpoint.method()
    url = endpoint.url()

    try:
        if method == "POST":
            response = requests.post(url, data=json.dumps(data), headers=headers)
        elif method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "PUT":
            response = requests.put(url, data=json.dumps(data), headers=headers)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        # Attempt to parse JSON response
        try:
            return response.status_code, response.json()
        except json.JSONDecodeError:
            return response.status_code, response.text

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None, str(e)


def register_device():
    data = {
        "mac_address": get_mac_address(),
        "secret_key": SECRET_KEY
    }
    headers = {"Content-Type": "application/json"}

    status_code, response_data = send_request(ApiEndpoints.REGISTER_DEVICE, data=data, headers=headers)

    if status_code == 200:
        global ID, KEY
        ID = response_data['id']
        KEY = response_data['key']
        print(f"Device registered with ID: {ID} and Key: {KEY}")

        # Save credentials for future use
        save_credentials(ID, KEY)
    else:
        print("Failed to register device:", response_data)


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
