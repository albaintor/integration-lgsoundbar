"""
Media-player entity functions.

:copyright: (c) 2023 by Unfolded Circle ApS.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""
import asyncio
import logging
from typing import Any

from client import LGDevice
from config import DeviceInstance, create_entity_id
from const import (
    LG_REMOTE_BUTTONS_MAPPING,
    LG_REMOTE_UI_PAGES,
    LG_SIMPLE_COMMANDS,
    States,
)
from ucapi import EntityTypes, Remote, StatusCodes
from ucapi.remote import Attributes, Commands, Features, Options
from ucapi.remote import States as RemoteStates

_LOG = logging.getLogger(__name__)

LG_REMOTE_STATE_MAPPING = {
    States.UNKNOWN: RemoteStates.UNKNOWN,
    States.UNAVAILABLE: RemoteStates.UNAVAILABLE,
    States.OFF: RemoteStates.OFF,
    States.ON: RemoteStates.ON,
    States.PLAYING: RemoteStates.ON,
    States.PAUSED: RemoteStates.ON,
    States.STOPPED: RemoteStates.ON,
}


class LGRemote(Remote):
    """Representation of a Kodi Media Player entity."""

    def __init__(self, config_device: DeviceInstance, device: LGDevice):
        """Initialize the class."""
        self._device = device
        _LOG.debug("LGSoundbar remote init")
        entity_id = create_entity_id(config_device.id, EntityTypes.REMOTE)
        features = [Features.SEND_CMD, Features.ON_OFF, Features.TOGGLE]
        attributes = {
            Attributes.STATE: LG_REMOTE_STATE_MAPPING.get(device.state),
        }
        super().__init__(
            entity_id,
            config_device.name,
            features,
            attributes,
            button_mapping=LG_REMOTE_BUTTONS_MAPPING,
            ui_pages=LG_REMOTE_UI_PAGES,
            simple_commands=LG_SIMPLE_COMMANDS,
        )

    def get_int_param(self, param: str, params: dict[str, Any], default: int):
        """Extract int parameter."""
        # TODO bug to be fixed on UC Core : some params are sent as (empty) strings by remote (hold == "")
        if params is None or param is None:
            return default
        value = params.get(param, default)
        if isinstance(value, str) and len(value) > 0:
            return int(float(value))
        return default

    async def command(self, cmd_id: str, params: dict[str, Any] | None = None) -> StatusCodes:
        """
        Media-player entity command handler.

        Called by the integration-API if a command is sent to a configured media-player entity.

        :param cmd_id: command
        :param params: optional command parameters
        :return: status code of the command request
        """
        _LOG.info("Got %s command request: %s %s", self.id, cmd_id, params)

        if self._device is None:
            _LOG.warning("No LG instance for entity: %s", self.id)
            return StatusCodes.SERVICE_UNAVAILABLE

        repeat = self.get_int_param("repeat", params, 1)
        res = StatusCodes.OK
        for _i in range(0, repeat):
            res = await self.handle_command(cmd_id, params)
        return res

    async def handle_command(self, cmd_id: str, params: dict[str, Any] | None = None) -> StatusCodes:
        """Handle command."""
        # pylint: disable=R0911
        # hold = self.get_int_param("hold", params, 0)
        delay = self.get_int_param("delay", params, 0)
        command = ""
        if params:
            command = params.get("command", "")

        if command in self.options[Options.SIMPLE_COMMANDS]:
            return await self._device.send_command(command)
        if Commands.ON in [command, cmd_id]:
            return await self._device.turn_on()
        if Commands.OFF in [command, cmd_id]:
            return await self._device.turn_off()
        if Commands.TOGGLE in [command, cmd_id]:
            return await self._device.toggle()
        if cmd_id == Commands.SEND_CMD:
            return await self._device.send_command(command)
        if cmd_id == Commands.SEND_CMD_SEQUENCE:
            commands = params.get("sequence", [])  # .split(",")
            res = StatusCodes.OK
            for command in commands:
                res = await self.handle_command(Commands.SEND_CMD, {"command": command, "params": params})
                if delay > 0:
                    await asyncio.sleep(delay)
        else:
            return StatusCodes.NOT_IMPLEMENTED
        if delay > 0 and cmd_id != Commands.SEND_CMD_SEQUENCE:
            await asyncio.sleep(delay)
        return res

    def _key_update_helper(self, key: str, value: str | None, attributes):
        # pylint: disable=R0801
        if value is None:
            return attributes

        if key in self.attributes:
            if self.attributes[key] != value:
                attributes[key] = value
        else:
            attributes[key] = value

        return attributes

    def filter_changed_attributes(self, update: dict[str, Any]) -> dict[str, Any]:
        """
        Filter the given attributes and return only the changed values.

        :param update: dictionary with attributes.
        :return: filtered entity attributes containing changed attributes only.
        """
        attributes = {}

        if Attributes.STATE in update:
            state = LG_REMOTE_STATE_MAPPING.get(update[Attributes.STATE])
            attributes = self._key_update_helper(Attributes.STATE, state, attributes)

        _LOG.debug("LGRemote update attributes %s -> %s", update, attributes)
        return attributes
