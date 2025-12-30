import logging
import asyncio
from .transport_generic import GenericBleTransport

_LOGGER = logging.getLogger(__name__)

class GenericGrill:
    def __init__(self, address: str):
        self.transport = GenericBleTransport(address)
        self.transport.subscribe(self._on_data)
        self._state = {}
        self._callback = None  # Add callback storage

    def register_callback(self, callback):
        """Registers a callback for state updates."""
        self._callback = callback

    async def start(self):
        await self.transport.connect()

    async def stop(self):
        await self.transport.disconnect()

    async def set_temp(self, temp_f: int):
        """Sets the target temperature using the Linear 5 formula."""
        cmd = None
        
        # 1. Handle "High" / 500F Mode
        # This uses a specific "Power Mode" command rather than a temp index
        if temp_f >= 500:
            _LOGGER.info("Setting max temp (High/500F)")
            cmd = "fa09fe0501050000ff"
            
        # 2. Handle Standard Temps (180F - 495F)
        # Formula: Index = (TargetTemp - 180) / 5
        elif temp_f >= 180:
            # Calculate the dial index
            index = int((temp_f - 180) // 5)
            
            # Safety check to ensure we don't overflow the byte
            if index > 255:
                _LOGGER.error(f"Calculated index {index} exceeds limit. Temp {temp_f}F too high.")
                return

            # Structure: FA 09 FE 05 01 03 [Index] [P-Set=00] FF
            # 350F example: (350-180)/5 = 34 (0x22) -> fa09fe0501032200ff
            cmd = f"fa09fe050103{index:02x}00ff"
            
        else:
            _LOGGER.warning(f"Temp {temp_f}F is below the minimum supported 180F.")
            return

        if cmd:
            _LOGGER.info(f"Setting temp to {temp_f}F (Hex Index: {int((temp_f - 180) // 5) if temp_f < 500 else 'High'})")
            await self.transport.send_command(cmd)

    async def _on_data(self, data):
        state = {}
        
        # Parse Status Packet (FA 1A...)
        if len(data) >= 26 and data[0] == 0xFA and data[1] == 0x1A:
            # Current Temp (Bytes 8-9)
            curr_raw = (data[8] << 8) | data[9]
            state['p1Temp'] = int(curr_raw / 10.0)  # Changed to p1Temp (CamelCase)
            state['smokerActTemp'] = state['p1Temp'] # Map to smokerActTemp as well
            
            # Set Temp (Bytes 22-23)
            set_c = (data[22] << 8) | data[23]
            state['grillSetTemp'] = int((set_c * 9/5) + 32) # Changed to grillSetTemp
            
            state['moduleIsOn'] = True # Changed to moduleIsOn
            
            self._state.update(state)
            
            # Fire the callback to notify api.py
            if self._callback:
                if asyncio.iscoroutinefunction(self._callback):
                    await self._callback(self._state)
                else:
                    self._callback(self._state)

    def get_state(self):
        return self._state