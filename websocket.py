import json
import subprocess

import websockets
import psutil
import asyncio
from time import time

from settings import WEBSOCKET_URL

DEVICE_ID = None
WEBSOCKET = None

IGNORE_COMMANDS = ["device_metrics", "status", "connected_devices", "script_log"]

previous_stats = {
    "bytes_sent": 0,
    "bytes_recv": 0,
    "timestamp": time(),
}

def calculate_network_usage():
    global previous_stats
    current_stats = psutil.net_io_counters()
    current_time = time()

    elapsed_time = current_time - previous_stats["timestamp"]
    if elapsed_time == 0:
        return {"bytes_sent_per_sec": 0, "bytes_recv_per_sec": 0}

    bytes_sent = (current_stats.bytes_sent - previous_stats["bytes_sent"]) / elapsed_time
    bytes_recv = (current_stats.bytes_recv - previous_stats["bytes_recv"]) / elapsed_time

    # Update previous stats
    previous_stats = {
        "bytes_sent": current_stats.bytes_sent,
        "bytes_recv": current_stats.bytes_recv,
        "timestamp": current_time,
    }

    return {
        "bytes_sent": round(bytes_sent, 2),
        "bytes_recv": round(bytes_recv, 2),
    }

async def get_device_metrics():
    disk_io = psutil.disk_io_counters()

    metrics = {
        "cpu_load": psutil.cpu_percent(),
        "memory_usage": psutil.virtual_memory().percent,
        "disk_read": round(disk_io.read_bytes / (1024 * 1024), 2),  # MB
        "disk_write": round(disk_io.write_bytes / (1024 * 1024), 2),
    }

    metrics.update(calculate_network_usage())

    return metrics

async def send_device_info(websocket):
    while True:
        device_metrics = await get_device_metrics()
        info_message = {"command": "device_info", "data": device_metrics}
        await websocket.send(json.dumps(info_message))
        await asyncio.sleep(1)


def save_script(data):
    try:
        with open('script.sh', "w") as file:
            file.write(data["content"])
        print(f"Script saved successfully!")
        return True
    except Exception as e:
        print(f"Failed to save the script: {e}")
        return False


async def run_script(websocket):

    message = {"type": "broadcast", "command": "script_log", "device_id": DEVICE_ID, "data": ''}

    try:
        script_path = "./script.sh"
        bash_path = "C:/Program Files/Git/bin/bash.exe"

        print("Starting the script...")

        # Start the subprocess
        process = await asyncio.create_subprocess_exec(
            bash_path, script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Read the script's output line by line asynchronously
        async for line in process.stdout:
            line_decoded = line.decode().strip()
            message["data"] = line_decoded
            await websocket.send(json.dumps(message))

        # Wait for the process to finish
        return_code = await process.wait()

        message["message"] = f"Script completed with return code {return_code}"
        await websocket.send(json.dumps(message))

        # Handle stderr if needed
        async for error in process.stderr:
            print(f"Error: {error.decode().strip()}")
            message["message"] = f"Error: {error.decode().strip()}"
            await websocket.send(json.dumps(message))

    except Exception as e:
        print(f"Failed to run script: {e}")
        message["message"] = f"Failed to execute script: {e}"

        await websocket.send(json.dumps(message))


def current_device_commands(websocket, message):
    if message.get("command") == "upload_to_client":
        save_script(message.get("data"))

    elif message.get("command") == "run_script":
        sender_task = asyncio.create_task(run_script(websocket))



async def listen_for_commands(device_id, device_key):
    uri = f"{WEBSOCKET_URL}/?id={device_id}&key={device_key}"

    global DEVICE_ID, WEBSOCKET
    DEVICE_ID = device_id

    async with websockets.connect(uri) as websocket:
        WEBSOCKET = websocket
        sender_task = asyncio.create_task(send_device_info(websocket))

        try:
            while True:
                message = json.loads(await websocket.recv())

                if message.get("device_id") == str(device_id):

                    current_device_commands(websocket, message)

                elif message.get("command") in IGNORE_COMMANDS:
                    continue

                else:
                    print(f"Received command: {message.get("command")}")
        finally:
            sender_task.cancel()
            await sender_task
