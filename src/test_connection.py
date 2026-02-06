# pylint: skip-file
# flake8: noqa
import asyncio
import logging
import sys
from typing import Any

from rich import print_json

from client import Events, LGDevice
from config import ConfigDevice

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)


async def on_device_update(device_id: str, update: dict[str, Any] | None) -> None:
    print_json(data=update)


async def main():
    _LOG.debug("Start connection")
    client = LGDevice(
        device_config=ConfigDevice(
            id="deviceid", name="LG Soundbar", address="192.168.1.53", port=9741, volume_step=1.0, always_on=False
        )
    )
    client.events.on(Events.UPDATE, on_device_update)
    await client.connect()
    await asyncio.sleep(3)
    await client.select_source("HDMI")
    await asyncio.sleep(3)
    await client.volume_down()
    # _LOG.debug("INFO %s %s", client.volume, client.attributes)
    await asyncio.sleep(150)


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
