CREDENTIAL_FILE = "device_credentials.json"

BASE_URL = "http://192.168.3.129:8000"
API_URL = f"{BASE_URL}/api/v1/device_manager"
WEBSOCKET_URL = f"ws://{BASE_URL.replace("http://", '')}/ws/device"

SECRET_KEY = "123"
