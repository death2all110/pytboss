import logging
import asyncio
from .transport_generic import GenericBleTransport

_LOGGER = logging.getLogger(__name__)

# --- THE MAPPING TASK ---
# We know 4=340, 5=350. 
# You need to fill in the rest by testing!
TEMP_INDEX_MAP = {
    # TempF: Index (Hex)
    # SMOKE: 0x01, # Guess?
    # 200:   0x02, # Guess?
    # 225:   0x03, # Guess?
    340:     0x04, # CONFIRMED
    350:     0x05, # CONFIRMED
    # 400:   0x06, # Guess?
    # 450:   0x07, # Guess?
    500:     0xFF, # Special case handled in logic below
}

class GenericGrill:
    def __init__(self, address: str):
        self.transport = GenericBleTransport(address)
        self.transport.subscribe(self._on_data)
        self._state = {}

    async def start(self):
        await self.transport.connect()

    async def stop(self):
        await self.transport.disconnect()

    async def set_temp(self, temp_f: int):
        cmd = None
        
        # 1. Handle "High" / 500F Mode
        if temp_f >= 500:
            # Power Mode 5 (High) identified in logs
            cmd = "fa09fe0501050000ff"
            
        # 2. Handle Standard Temps via Index
        elif temp_f in TEMP_INDEX_MAP:
            index = TEMP_INDEX_MAP[temp_f]
            # Structure: FA 09 FE 05 01 03 [Index] [P-Set=00] FF
            cmd = f"fa09fe050103{index:02x}00ff"
            
        else:
            _LOGGER.warning(f"Temp {temp_f}F not in lookup table. Using default index 01.")
            cmd = "fa09fe0501030100ff"

        if cmd:
            _LOGGER.info(f"Setting temp to {temp_f}F (Cmd: {cmd})")
            await self.transport.send_command(cmd)

    async def _on_data(self, data):
        state = {}
        
        # Parse Status Packet (FA 1A...)
        if len(data) >= 26 and data[0] == 0xFA and data[1] == 0x1A:
            # Current Temp (Bytes 8-9, F*10)
            curr_raw = (data[8] << 8) | data[9]
            state['p1_temp'] = int(curr_raw / 10.0)
            
            # Set Temp (Bytes 22-23, Celsius Integer)
            set_c = (data[22] << 8) | data[23]
            state['set_temp'] = int((set_c * 9/5) + 32)
            
            # Basic Status (Grill is On)
            state['module_is_on'] = True
            
            # Update internal state
            self._state.update(state)
            
            # Print for debugging
            # print(f"Grill Status: {state}")

    def get_state(self):
        return self._state