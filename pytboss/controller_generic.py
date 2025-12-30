import logging
import asyncio
from .transport_generic import GenericBleTransport

_LOGGER = logging.getLogger(__name__)

class GenericGrill:
    def __init__(self, ble_device):
        self.transport = GenericBleTransport(ble_device)
        self.transport.subscribe(self._on_data)
        self._state = {}
        self._callback = None
        # NEW: Event to track if we have received data
        self._first_data_received = asyncio.Event()

    def register_callback(self, callback):
        self._callback = callback

    async def start(self):
        """Connect and wait for the first data packet."""
        await self.transport.connect()
        
        # NEW: Wait up to 15 seconds for the first packet
        _LOGGER.debug("Waiting for first data packet...")
        try:
            await asyncio.wait_for(self._first_data_received.wait(), timeout=40.0)
            _LOGGER.info("Initial data received!")
        except asyncio.TimeoutError:
            _LOGGER.warning("Connected, but no data received within timeout.")

    async def stop(self):
        await self.transport.disconnect()

    async def set_temp(self, temp_f: int):
        """Sets the target temperature using the Linear 5 formula."""
        cmd = None
        if temp_f >= 500:
            cmd = "fa09fe0501050000ff"
        elif temp_f >= 180:
            index = int((temp_f - 180) // 5)
            if index > 255: return
            cmd = f"fa09fe050103{index:02x}00ff"
        
        if cmd:
            _LOGGER.info(f"Setting temp to {temp_f}F (Hex Index: {int((temp_f - 180) // 5) if temp_f < 500 else 'High'})")
            await self.transport.send_command(cmd)

    async def _on_data(self, data):
        state = {}
        
        if len(data) >= 26 and data[0] == 0xFA and data[1] == 0x1A:
            curr_raw = (data[8] << 8) | data[9]
            
            # Map to Home Assistant Keys
            temp_f = int(curr_raw / 10.0)
            state['smokerActTemp'] = temp_f 
            state['p1Temp'] = temp_f
            
            set_c = (data[22] << 8) | data[23]
            state['grillSetTemp'] = int((set_c * 9/5) + 32)
            
            state['moduleIsOn'] = True
            
            self._state.update(state)
            
            # NEW: Signal that we have data
            if not self._first_data_received.is_set():
                self._first_data_received.set()
            
            if self._callback:
                if asyncio.iscoroutinefunction(self._callback):
                    await self._callback(self._state)
                else:
                    self._callback(self._state)

    def get_state(self):
        return self._state