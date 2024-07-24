#!/usr/bin/env python3
"""
This module implements a Remote Two integration driver for Orange STB.

:copyright: (c) 2023 by Unfolded Circle ApS.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

from datetime import timedelta

__version__ = "1.0.0"

from enum import IntEnum

import ucapi
from ucapi.ui import Buttons, DeviceButtonMapping, UiPage


class States(IntEnum):
    """State of a connected device."""

    UNKNOWN = 0
    UNAVAILABLE = 1
    OFF = 2
    ON = 3
    PLAYING = 4
    PAUSED = 5
    STOPPED = 6


# Mapping of a device state to a media-player entity state
MEDIA_PLAYER_STATE_MAPPING: dict[States, ucapi.media_player.States] = {
    States.ON: ucapi.media_player.States.ON,
    States.OFF: ucapi.media_player.States.OFF,
    States.PAUSED: ucapi.media_player.States.PAUSED,
    States.STOPPED: ucapi.media_player.States.PAUSED,
    States.PLAYING: ucapi.media_player.States.PLAYING,
    States.UNAVAILABLE: ucapi.media_player.States.UNAVAILABLE,
    States.UNKNOWN: ucapi.media_player.States.UNKNOWN,
}

SCAN_INTERVAL = timedelta(seconds=10)
DEFAULT_NAME = "lgsoundbar"

LG_SIMPLE_COMMANDS = [
    "INPUT_NEXT",
    "MODE_NIGHT",
    "MODE_AUTO_VOLUME_CONTROL",
    "MODE_DYNAMIC_RANGE_COMPRESSION",
    "MODE_NEURALX",
    "MODE_TV_REMOTE",
]


LG_REMOTE_BUTTONS_MAPPING: [DeviceButtonMapping] = [
    # {"button": Buttons.BACK, "short_press": {"cmd_id": "RETURN"}},
    # {"button": Buttons.HOME, "short_press": {"cmd_id": "MENU"}},
    # {"button": Buttons.CHANNEL_DOWN, "short_press": {"cmd_id": "SKIPREV"}},
    # {"button": Buttons.CHANNEL_UP, "short_press": {"cmd_id": "SKIPFWD"}},
    # {"button": Buttons.DPAD_UP, "short_press": {"cmd_id": "UP"}},
    # {"button": Buttons.DPAD_DOWN, "short_press": {"cmd_id": "DOWN"}},
    # {"button": Buttons.DPAD_LEFT, "short_press": {"cmd_id": "LEFT"}},
    # {"button": Buttons.DPAD_RIGHT, "short_press": {"cmd_id": "RIGHT"}},
    # {"button": Buttons.DPAD_MIDDLE, "short_press": {"cmd_id": "SELECT"}},
    # {"button": Buttons.PLAY, "short_press": {"cmd_id": "PAUSE"}},
    # {"button": Buttons.PREV, "short_press": {"cmd_id": "REV"}},
    # {"button": Buttons.NEXT, "short_press": {"cmd_id": "CUE"}},
    {"button": Buttons.VOLUME_UP, "short_press": {"cmd_id": "volume_up"}},
    {"button": Buttons.VOLUME_DOWN, "short_press": {"cmd_id": "volume_down"}},
    {"button": Buttons.MUTE, "short_press": {"cmd_id": "mute"}},
    {"button": Buttons.POWER, "short_press": {"cmd_id": "toggle"}},
]

LG_REMOTE_UI_PAGES: [UiPage] = [
    {
        "page_id": "LG commands",
        "name": "LG commands",
        "grid": {"width": 4, "height": 6},
        "items": [
            {
                "command": {"cmd_id": "remote.send", "params": {"command": "toggle", "repeat": 1}},
                "icon": "uc:power-on",
                "location": {"x": 0, "y": 0},
                "size": {"height": 1, "width": 1},
                "type": "icon",
            },
            {
                "command": {"cmd_id": "remote.send", "params": {"command": "MODE_AUTO_VOLUME_CONTROL", "repeat": 1}},
                "icon": "uc:language",
                "location": {"x": 1, "y": 0},
                "size": {"height": 1, "width": 1},
                "type": "icon",
            },
            {
                "command": {"cmd_id": "remote.send", "params": {"command": "MODE_NIGHT", "repeat": 1}},
                "text": "Night mode",
                "location": {"x": 2, "y": 0},
                "size": {"height": 1, "width": 1},
                "type": "text",
            },
            {
                "command": {
                    "cmd_id": "remote.send",
                    "params": {"command": "MODE_DYNAMIC_RANGE_COMPRESSION", "repeat": 1},
                },
                "text": "DRC",
                "location": {"x": 3, "y": 0},
                "size": {"height": 1, "width": 1},
                "type": "text",
            },
            {
                "command": {"cmd_id": "remote.send", "params": {"command": "MODE_NEURALX", "repeat": 1}},
                "text": "Neural X",
                "location": {"x": 0, "y": 1},
                "size": {"height": 1, "width": 1},
                "type": "text",
            },
            {
                "command": {"cmd_id": "remote.send", "params": {"command": "MODE_AUTO_DISPLAY", "repeat": 1}},
                "text": "Auto Display",
                "location": {"x": 1, "y": 1},
                "size": {"height": 1, "width": 1},
                "type": "text",
            },
        ],
    }
]
