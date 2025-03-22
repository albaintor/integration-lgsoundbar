import asyncio
import logging
import sys
from client import LGDevice
from config import DeviceInstance

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)



async def main():
    _LOG.debug("Start connection")
    client = LGDevice(device_config=
                      DeviceInstance(id="deviceid", name="LG Soundbar", address="192.168.1.16",
                                     port=9741, volume_step=1.0, always_on=False))
    await client.connect()
    await client.select_source("HDMI")
    _LOG.debug("INFO %s %s", client.volume, client.attributes)

if __name__ == "__main__":
    _LOG = logging.getLogger(__name__)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logging.basicConfig(handlers=[ch])
    logging.getLogger("client").setLevel(logging.DEBUG)
    logging.getLogger("lglib").setLevel(logging.DEBUG)
    logging.getLogger("test_connection").setLevel(logging.DEBUG)
    _LOOP.run_until_complete(main())
    _LOOP.run_forever()
