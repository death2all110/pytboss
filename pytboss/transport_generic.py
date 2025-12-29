import logging
from bleak import BleakClient

_LOGGER = logging.getLogger(__name__)

class GenericBleTransport:
    """Transport for generic (Taylor/Smarter Grill) controllers."""
    
    # UUIDs identified from your logs
    UUID_WRITE  = "0000abf1-0000-1000-8000-00805f9b34fb"
    UUID_NOTIFY = "0000abf2-0000-1000-8000-00805f9b34fb"

    def __init__(self, address: str):
        self._address = address
        self._client = None
        self._callback = None

    async def connect(self):
        _LOGGER.debug(f"Connecting to {self._address}...")
        self._client = BleakClient(self._address)
        await self._client.connect()
        await self._client.start_notify(self.UUID_NOTIFY, self._on_data)
        _LOGGER.info("Connected to Generic Grill")

    async def disconnect(self):
        if self._client:
            await self._client.disconnect()
            self._client = None

    def subscribe(self, callback):
        self._callback = callback

    async def _on_data(self, sender, data):
        if self._callback:
            await self._callback(data)

    async def send_command(self, hex_cmd: str):
        if not self._client or not self._client.is_connected:
            _LOGGER.error("Not connected, cannot send command")
            return
        
        # Convert hex string to bytes
        data = bytes.fromhex(hex_cmd)
        _LOGGER.debug(f"Sending: {data.hex()}")
        await self._client.write_gatt_char(self.UUID_WRITE, data)