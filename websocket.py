import json

import websockets

from settings import WEBSOCKET_URL


async def listen_for_commands(device_id, device_key):
    uri = f"{WEBSOCKET_URL}/?id={device_id}&key={device_key}"

    async with websockets.connect(uri) as websocket:
        while True:
            command = await websocket.recv()
            print(f"Received command: {command}")
            # Process the command and possibly respond back
            response = {"status": "executed", "command": command}
            await websocket.send(json.dumps(response))
