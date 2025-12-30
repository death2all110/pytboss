import logging
from bleak import BleakClient
import bleak_retry_connector
from bleak_retry_connector import BleakClientWithServiceCache

_LOGGER = logging.getLogger(__name__)

class GenericBleTransport:
    """Transport for generic (Taylor/Smarter Grill) controllers."""
    
    UUID_WRITE  = "0000abf1-0000-1000-8000-00805f9b34fb"
    UUID_NOTIFY = "0000abf2-0000-1000-8000-00805f9b34fb"

    def __init__(self, address: str):
        self._address = address
        self._client = None
        self._callback = None

    async def connect(self):
        _LOGGER.debug(f"Connecting to {self._address}...")
        
        # Use the retry connector to avoid warnings and improve stability
        self._client = await bleak_retry_connector.establish_connection(
            client_class=BleakClientWithServiceCache,
            device=self._address, # It can accept an address string
            name=self._address,
            disconnected_callback=self._on_disconnected,
        )
        
        await self._client.start_notify(self.UUID_NOTIFY, self._on_data)
        _LOGGER.info("Connected to Generic Grill")

    async def disconnect(self):
        if self._client:
            await self._client.disconnect()
            self._client = None

    def _on_disconnected(self, client):
        _LOGGER.debug("Generic Grill Disconnected")

    def subscribe(self, callback):
        self._callback = callback

    async def _on_data(self, sender, data):
        if self._callback:
            await self._callback(data)

    async def send_command(self, hex_cmd: str):
        if not self._client or not self._client.is_connected:
            _LOGGER.error("Not connected, cannot send command")
            return
        
        data = bytes.fromhex(hex_cmd)
        _LOGGER.debug(f"Sending: {data.hex()}")
        await self._client.write_gatt_char(self.UUID_WRITE, data)