from urllib.parse import urlparse

# Change this values
SERVER_URL = "http://192.168.1.244:8000"
SECRET_KEY = "He2as5SeLxCZmQJ1Pp8OmWFQQ9cEoNwF"
RECONNECT_DELAY = 1  # seconds

# Don't change
parsed_url = urlparse(SERVER_URL)
base_url = parsed_url.netloc
is_secure = parsed_url.scheme == "https"
ws_scheme = "wss" if is_secure else "ws"

API_URL = f"{SERVER_URL}/api/v1/device_manager"
WEBSOCKET_URL = f"{ws_scheme}://{base_url}/ws/device"


OUTPUT_DIR = "./output"
CREDENTIAL_FILE = "device_credentials.json"
