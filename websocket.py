import json

import websockets
import psutil
import asyncio
from time import time

from settings import WEBSOCKET_URL

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


async def listen_for_commands(device_id, device_key):
    uri = f"{WEBSOCKET_URL}/?id={device_id}&key={device_key}"

    async with websockets.connect(uri) as websocket:
        sender_task = asyncio.create_task(send_device_info(websocket))

        try:
            while True:
                message = json.loads(await websocket.recv())
                print(f"Received command: {message.get("command")}")
        finally:
            sender_task.cancel()
            await sender_task
