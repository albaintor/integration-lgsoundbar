"""
Media-player entity functions.

:copyright: (c) 2023 by Unfolded Circle ApS.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import logging
from typing import Any

import client
from client import LGDevice
from config import DeviceInstance, create_entity_id
from const import LG_SIMPLE_COMMANDS, MEDIA_PLAYER_STATE_MAPPING
from ucapi import EntityTypes, MediaPlayer, StatusCodes
from ucapi.media_player import (
    Attributes,
    Commands,
    DeviceClasses,
    Features,
    MediaType,
    Options,
    States,
)

_LOG = logging.getLogger(__name__)


class LGMediaPlayer(MediaPlayer):
    """Representation of a Sony Media Player entity."""

    def __init__(self, config_device: DeviceInstance, device: LGDevice):
        """Initialize the class."""
        self._device = device
        _LOG.debug("LGSoundbar media player init")
        entity_id = create_entity_id(config_device.id, EntityTypes.MEDIA_PLAYER)
        # TODO add additional buttons if possible
        features = [
            Features.ON_OFF,
            Features.TOGGLE,
            Features.VOLUME,
            Features.VOLUME_UP_DOWN,
            Features.MUTE,
            Features.UNMUTE,
            Features.MUTE_TOGGLE,
            Features.MEDIA_TYPE,
            Features.SELECT_SOURCE,
            Features.SELECT_SOUND_MODE,
            # Features.PLAY_PAUSE,
            # Features.DPAD,
            # Features.SETTINGS,
            # Features.STOP,
            # Features.EJECT,
            # Features.FAST_FORWARD,
            # Features.REWIND,
            # Features.MENU,
            # Features.CONTEXT_MENU,
            # Features.NUMPAD,
            # Features.CHANNEL_SWITCHER,
            Features.MEDIA_POSITION,
            Features.MEDIA_DURATION,
            Features.MEDIA_IMAGE_URL
            # Features.INFO,
            # Features.AUDIO_TRACK,
            # Features.SUBTITLE,
            # Features.COLOR_BUTTONS,
            # Features.HOME,
            # Features.PREVIOUS,
            # Features.NEXT
        ]
        attributes = {
            Attributes.STATE: state_from_device(device.state),
            Attributes.VOLUME: device.volume,
            Attributes.MUTED: device.muted,
            Attributes.SOURCE: device.source if device.source else "",
            Attributes.SOURCE_LIST: device.source_list if device.source_list else [],
            Attributes.SOUND_MODE: device.sound_mode,
            Attributes.SOUND_MODE_LIST: device.sound_mode_list,
            Attributes.MEDIA_TYPE: MediaType.VIDEO,  # TODO to improve based on PLAY_INFO.i_stream_type
            Attributes.MEDIA_IMAGE_URL: device.media_image_url,
            Attributes.MEDIA_POSITION: device.media_position,
            Attributes.MEDIA_DURATION: device.media_duration,
            Attributes.MEDIA_TITLE: device.media_title,
            Attributes.MEDIA_ARTIST: device.media_artist,
        }

        options = {Options.SIMPLE_COMMANDS: LG_SIMPLE_COMMANDS}
        super().__init__(
            entity_id, config_device.name, features, attributes, device_class=DeviceClasses.SPEAKER, options=options
        )

    async def command(self, cmd_id: str, params: dict[str, Any] | None = None) -> StatusCodes:
        """
        Media-player entity command handler.

        Called by the integration-API if a command is sent to a configured media-player entity.

        :param cmd_id: command
        :param params: optional command parameters
        :return: status code of the command request
        """
        # pylint: disable=R0911
        _LOG.info("Got %s command request: %s %s", self.id, cmd_id, params)

        if self._device is None:
            _LOG.warning("No device instance for entity: %s", self.id)
            return StatusCodes.SERVICE_UNAVAILABLE
        if cmd_id == Commands.ON:
            return await self._device.turn_on()
        if cmd_id == Commands.OFF:
            return await self._device.turn_off()
        if cmd_id == Commands.TOGGLE:
            return await self._device.toggle()
        if cmd_id == Commands.VOLUME:
            return await self._device.set_volume_level(params.get("volume"))
        if cmd_id == Commands.VOLUME_UP:
            return await self._device.volume_up()
        if cmd_id == Commands.VOLUME_DOWN:
            return await self._device.volume_down()
        if cmd_id == Commands.MUTE_TOGGLE:
            return await self._device.mute_toggle()
        if cmd_id == Commands.MUTE:
            return await self._device.mute(True)
        if cmd_id == Commands.UNMUTE:
            return await self._device.mute(False)
        if cmd_id == Commands.SELECT_SOURCE:
            return await self._device.select_source(params.get("source"))
        if cmd_id == Commands.SELECT_SOUND_MODE:
            return await self._device.select_sound_mode(params.get("mode"))
        if cmd_id in self.options[Options.SIMPLE_COMMANDS]:
            return await self._device.send_command(cmd_id)
        return StatusCodes.NOT_IMPLEMENTED

    def filter_changed_attributes(self, update: dict[str, Any]) -> dict[str, Any]:
        """
        Filter the given attributes and return only the changed values.

        :param update: dictionary with attributes.
        :return: filtered entity attributes containing changed attributes only.
        """
        attributes = {}

        if Attributes.STATE in update:
            state = update[Attributes.STATE]
            attributes = self._key_update_helper(Attributes.STATE, state, attributes)

        for attr in [
            Attributes.VOLUME,
            Attributes.MUTED,
            Attributes.SOURCE,
            Attributes.SOURCE_LIST,
            Attributes.SOUND_MODE,
            Attributes.SOUND_MODE_LIST,
            Attributes.MEDIA_TYPE,
            Attributes.MEDIA_IMAGE_URL,
            Attributes.MEDIA_POSITION,
            Attributes.MEDIA_DURATION,
            Attributes.MEDIA_TITLE,
            Attributes.MEDIA_ARTIST,
        ]:
            if attr in update:
                attributes = self._key_update_helper(attr, update[attr], attributes)

        if Attributes.SOURCE_LIST in update:
            if Attributes.SOURCE_LIST in self.attributes:
                if update[Attributes.SOURCE_LIST] != self.attributes[Attributes.SOURCE_LIST]:
                    attributes[Attributes.SOURCE_LIST] = update[Attributes.SOURCE_LIST]

        if Features.SELECT_SOUND_MODE in self.features:
            if Attributes.SOUND_MODE in update:
                attributes = self._key_update_helper(Attributes.SOUND_MODE, update[Attributes.SOUND_MODE], attributes)
            if Attributes.SOUND_MODE_LIST in update:
                if Attributes.SOUND_MODE_LIST in self.attributes:
                    if update[Attributes.SOUND_MODE_LIST] != self.attributes[Attributes.SOUND_MODE_LIST]:
                        attributes[Attributes.SOUND_MODE_LIST] = update[Attributes.SOUND_MODE_LIST]

        if Attributes.STATE in attributes:
            if attributes[Attributes.STATE] == States.OFF:
                attributes[Attributes.MEDIA_IMAGE_URL] = ""
                attributes[Attributes.MEDIA_ALBUM] = ""
                attributes[Attributes.MEDIA_ARTIST] = ""
                attributes[Attributes.MEDIA_TITLE] = ""
                attributes[Attributes.MEDIA_TYPE] = ""
                attributes[Attributes.SOURCE] = ""

        _LOG.debug("MediaPlayer update attributes %s -> %s", update, attributes)
        return attributes

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


def state_from_device(client_state: client.States) -> States:
    """
    Convert Device state to UC API media-player state.

    :param client_state: Orange STB  state
    :return: UC API media_player state
    """
    if client_state in MEDIA_PLAYER_STATE_MAPPING:
        return MEDIA_PLAYER_STATE_MAPPING[client_state]
    return States.UNKNOWN
