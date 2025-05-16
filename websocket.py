import asyncio
import base64
import os
from datetime import datetime
import json
from enum import Enum
from pathlib import Path
from time import time

import psutil
import websockets

from settings import WEBSOCKET_URL, RECONNECT_DELAY, OUTPUT_DIR

SCRIPT_PATH = "./script.sh"
FULL_OUTPUT = ''
script_task = None

previous_stats = {
    "timestamp": time(),
    "bytes_sent": psutil.net_io_counters().bytes_sent,
    "bytes_recv": psutil.net_io_counters().bytes_recv,
    "disk_read": psutil.disk_io_counters().read_bytes,
    "disk_write": psutil.disk_io_counters().write_bytes,
}


class DeviceCommands(str, Enum):
    CONFIG_STATUS = 'config_status'
    METRICS = 'metrics'
    START_LAB = 'start_lab'
    STOP_LAB = 'stop_lab'
    SCRIPT_LOG = 'script_log'
    FILE_UPLOAD = 'file_upload'


def get_timestamp():
    return datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")


def calculate_network_usage(elapsed_time):
    current = psutil.net_io_counters()
    sent_rate = (current.bytes_sent - previous_stats["bytes_sent"]) / elapsed_time
    recv_rate = (current.bytes_recv - previous_stats["bytes_recv"]) / elapsed_time

    return {
        "bytes_sent": round(sent_rate / 1024, 2),  # KB/s
        "bytes_recv": round(recv_rate / 1024, 2),  # KB/s
    }


def calculate_disk_usage(elapsed_time):
    current = psutil.disk_io_counters()
    read_rate = (current.read_bytes - previous_stats["disk_read"]) / elapsed_time
    write_rate = (current.write_bytes - previous_stats["disk_write"]) / elapsed_time

    return {
        "disk_read": round(read_rate / (1024 * 1024), 2),  # MB/s
        "disk_write": round(write_rate / (1024 * 1024), 2),  # MB/s
    }


async def get_device_metrics():
    global previous_stats

    current_time = time()
    elapsed = current_time - previous_stats["timestamp"]

    if elapsed == 0:
        elapsed = 1  # avoid division by zero

    metrics = {
        "cpu_load": psutil.cpu_percent(interval=None),
        "memory_usage": psutil.virtual_memory().percent,
    }

    metrics.update(calculate_disk_usage(elapsed))
    metrics.update(calculate_network_usage(elapsed))

    current = psutil.net_io_counters()
    current_disk = psutil.disk_io_counters()

    previous_stats.update({
        "bytes_sent": current.bytes_sent,
        "bytes_recv": current.bytes_recv,
        "disk_read": current_disk.read_bytes,
        "disk_write": current_disk.write_bytes,
    })

    return metrics


async def send_device_metrics(websocket):
    while True:
        try:
            device_metrics = await get_device_metrics()
            info_message = {"command": DeviceCommands.METRICS, "data": device_metrics}

            await websocket.send(json.dumps(info_message))
            await asyncio.sleep(1)

        except:
            return


def save_script(data):
    try:
        with open('script.sh', "w") as file:
            file.write(data)

    except:
        return


async def run_script(websocket):
    message = {"command": DeviceCommands.SCRIPT_LOG, "data": ''}
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    global FULL_OUTPUT
    FULL_OUTPUT = ''

    try:
        bash_path = "/bin/bash"

        # Start the subprocess
        process = await asyncio.create_subprocess_exec(
            "sudo", bash_path, SCRIPT_PATH,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Read the script's output line
        async for line in process.stdout:
            text = f"{get_timestamp()} {line.decode().strip()}"
            message["data"] = text
            FULL_OUTPUT += f"{text}\n"
            await websocket.send(json.dumps(message))

        return_code = await process.wait()

        text = f"{get_timestamp()} Script completed with return code {return_code}"
        FULL_OUTPUT += f"{text}\n"
        message["data"] = text
        await websocket.send(json.dumps(message))

        # Handle stderr if needed
        async for error in process.stderr:
            print(f"Error: {error.decode().strip()}")
            error = f"{get_timestamp()} Error: {error.decode().strip()}"
            message["data"] = error
            FULL_OUTPUT += f"{error}\n"
            await websocket.send(json.dumps(message))

    except Exception as e:
        print(f"Failed to run script: {e}")
        return


async def start_lab(websocket, data):
    lab_id = data["lab_id"]
    script_data = data["script_data"]

    if script_data is not None:
        save_script(script_data)
        global script_task
        script_task = asyncio.create_task(run_script(websocket))

    message = {
        "command": DeviceCommands.CONFIG_STATUS,
        "data": {
            "success": True,
            "lab_id": lab_id,
        }
    }

    await websocket.send(json.dumps(message))


async def stop_lab(websocket, data):
    lab_id = data["lab_id"]

    global script_task
    if script_task is not None:
        script_task.cancel()
        script_task = None

    for file_path in Path(OUTPUT_DIR).glob("*"):
        if file_path.is_file():
            try:
                with open(file_path, "rb") as f:
                    raw_bytes = f.read()

                encoded = base64.b64encode(raw_bytes).decode("utf-8")

                message = {
                    "command": DeviceCommands.FILE_UPLOAD,
                    "data": {
                        "filename": file_path.name,
                        "content": encoded,
                        "lab_id": lab_id,
                    }
                }

                await websocket.send(json.dumps(message))

                file_path.unlink()

            except:
                return

    message = {
        "command": DeviceCommands.CONFIG_STATUS,
        "data": {
            "success": True,
            "lab_id": lab_id,
        }
    }

    await websocket.send(json.dumps(message))


async def listen_for_commands(device_id, device_key):
    uri = f"{WEBSOCKET_URL}/?id={device_id}&key={device_key}"

    global script_task

    metrics_task = None
    start_task = None

    while True:
        try:
            print(f"Trying to connect to {WEBSOCKET_URL}")

            async with websockets.connect(uri) as websocket:
                print(f"Connected to {WEBSOCKET_URL}")

                metrics_task = asyncio.create_task(send_device_metrics(websocket))

                while True:
                    message = json.loads(await websocket.recv())
                    command = message.get("command")
                    data = message.get("data")

                    if command == DeviceCommands.START_LAB:
                        start_task = asyncio.create_task(start_lab(websocket, data))

                    elif command == DeviceCommands.STOP_LAB:
                        asyncio.create_task(stop_lab(websocket, data))

                    elif command == DeviceCommands.SCRIPT_LOG:
                        message = {"command": DeviceCommands.SCRIPT_LOG, "data": {"full": True, "text": FULL_OUTPUT}}
                        await websocket.send(json.dumps(message))

                    else:
                        print(f"Received command: {command}")

        except:
            print(f"Retrying in {RECONNECT_DELAY} seconds...")
            await asyncio.sleep(RECONNECT_DELAY)

        finally:
            if metrics_task:
                metrics_task.cancel()
                await metrics_task
                metrics_task = None

            if script_task:
                script_task.cancel()
                await script_task
                script_task = None

            if start_task:
                start_task.cancel()
                await start_task
                start_task = None
