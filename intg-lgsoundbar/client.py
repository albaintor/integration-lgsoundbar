#!/usr/bin/env python
# coding: utf-8
import asyncio
from functools import wraps
from typing import Callable, Concatenate, Awaitable, Any, Coroutine, TypeVar, ParamSpec

from asyncio import Lock
import logging
from enum import IntEnum

import ucapi.media_player
from aiohttp import ClientSession, ClientError
from config import DeviceInstance
from pyee import AsyncIOEventEmitter
from ucapi.media_player import Attributes, Commands

from const import States
from lglib import temescal, functions, equalisers

_LOGGER = logging.getLogger(__name__)


class Events(IntEnum):
    """Internal driver events."""

    CONNECTED = 0
    ERROR = 1
    UPDATE = 2
    IP_ADDRESS_CHANGED = 3
    DISCONNECTED = 4


_LGDeviceT = TypeVar("_LGDeviceT", bound="LGDevice")
_P = ParamSpec("_P")


def cmd_wrapper(
        func: Callable[Concatenate[_LGDeviceT, _P], Awaitable[ucapi.StatusCodes | list]],
) -> Callable[Concatenate[_LGDeviceT, _P], Coroutine[Any, Any, ucapi.StatusCodes | list]]:
    """Catch command exceptions."""

    @wraps(func)
    async def wrapper(obj: _LGDeviceT, *args: _P.args, **kwargs: _P.kwargs) -> ucapi.StatusCodes:
        """Wrap all command methods."""
        try:
            await func(obj, *args, **kwargs)
            return ucapi.StatusCodes.OK
        except ClientError as exc:
            # If Kodi is off, we expect calls to fail.
            if obj.state == States.OFF:
                log_function = _LOGGER.debug
            else:
                log_function = _LOGGER.error
            log_function(
                "Error calling %s on entity %s: %r trying to reconnect and send the command next",
                func.__name__,
                obj.id,
                exc,
            )
            # Kodi not connected, launch a connect task but
            # don't wait more than 5 seconds, then process the command if connected
            # else returns error
            connect_task = obj.event_loop.create_task(obj.connect())
            await asyncio.sleep(0)
            try:
                async with asyncio.timeout(5):
                    await connect_task
            except asyncio.TimeoutError:
                log_function(
                    "Timeout for reconnect, command won't be sent"
                )
                pass
            else:
                if not obj._connect_error:
                    try:
                        await func(obj, *args, **kwargs)
                        return ucapi.StatusCodes.OK
                    except ClientError as exc:
                        log_function(
                            "Error calling %s on entity %s: %r trying to reconnect",
                            func.__name__,
                            obj.id,
                            exc,
                        )
            return ucapi.StatusCodes.BAD_REQUEST
        except Exception as ex:
            _LOGGER.error(
                "Unknown error %s",
                func.__name__)

    return wrapper


class LGDevice(object):
    def __init__(self, device_config: DeviceInstance, timeout=3, refresh_frequency=60):
        from datetime import timedelta
        self._id = device_config.id
        self._name = device_config.name
        self._hostname = device_config.address
        self._port = device_config.port
        self._timeout = timeout
        self.refresh_frequency = timedelta(seconds=refresh_frequency)
        self._state = States.UNKNOWN
        self._event_loop = asyncio.get_event_loop() or asyncio.get_running_loop()
        self.events = AsyncIOEventEmitter(self._event_loop)
        self._update_lock = Lock()
        self._session: ClientSession | None = None
        self._device = temescal(self._hostname, self._port, self.handle_event, _LOGGER)
        self._volume_step = device_config.volume_step
        self._volume = 0
        self._volume_min = 0
        self._volume_max = 0
        self._power_state = False
        self._function = -1
        self._functions = []
        self._equaliser = -1
        self._equalisers = []
        self._mute = False
        self._rear_volume = 0
        self._rear_volume_min = 0
        self._rear_volume_max = 0
        self._woofer_volume = 0
        self._woofer_volume_min = 0
        self._woofer_volume_max = 0
        self._bass = 0
        self._treble = 0
        self._media_artist = ""
        self._media_title = ""
        self._media_position = 0
        self._media_duration = 0
        self._media_artwork = ""
        self._device_name = "LG"
        self._night_mode = False
        self._auto_volume_control = False
        self._dynamic_range_reduction = False
        self._neural_x = False
        self._tv_remote = False
        self._auto_display = False

    def handle_event(self, response):
        """Handle responses from the speakers."""
        data = response.get("data") or {}
        update_data = {}
        if response["msg"] == "EQ_VIEW_INFO":
            if "i_bass" in data:
                self._bass = data["i_bass"]
            if "i_treble" in data:
                self._treble = data["i_treble"]
            if "ai_eq_list" in data:
                self._equalisers = data["ai_eq_list"]
            if "i_curr_eq" in data:
                self._equaliser = data["i_curr_eq"]
        if response["msg"] == "SPK_LIST_VIEW_INFO":
            current_volume = self.volume
            current_mute = self.muted
            current_state = self.state
            if "b_powerstatus" in data:
                self._power_state = data["b_powerstatus"]
            if "i_vol" in data:
                self._volume = data["i_vol"]
            if "i_vol_min" in data:
                self._volume_min = data["i_vol_min"]
            if "i_vol_max" in data:
                self._volume_max = data["i_vol_max"]
            if "b_mute" in data:
                self._mute = data["b_mute"]
            if "i_curr_func" in data:
                self._function = data["i_curr_func"]
            if current_state != self.state:
                update_data[Attributes.STATE] = self.state
            if current_volume != self.volume:
                update_data[Attributes.VOLUME] = self.volume
            if current_mute != self.muted:
                update_data[Attributes.MUTED] = self.muted
        elif response["msg"] == "FUNC_VIEW_INFO":
            current_source = self.source
            current_functions = self.source_list
            if "i_curr_func" in data:
                self._function = data["i_curr_func"]
            if "ai_func_list" in data:
                self._functions = data["ai_func_list"]
            if current_source != self.source:
                update_data[Attributes.SOURCE] = self.source
            if len(current_functions) != len(self.source_list):
                update_data[Attributes.SOURCE] = self.source_list
        elif response["msg"] == "SETTING_VIEW_INFO":
            current_sound_mode = self.sound_mode
            current_sound_modes = self.sound_mode_list
            if "i_rear_min" in data:
                self._rear_volume_min = data["i_rear_min"]
            if "i_rear_max" in data:
                self._rear_volume_max = data["i_rear_max"]
            if "i_rear_level" in data:
                self._rear_volume = data["i_rear_level"]
            if "i_woofer_min" in data:
                self._woofer_volume_min = data["i_woofer_min"]
            if "i_woofer_max" in data:
                self._woofer_volume_max = data["i_woofer_max"]
            if "i_woofer_level" in data:
                self._woofer_volume = data["i_woofer_level"]
            if "i_curr_eq" in data:
                self._equaliser = data["i_curr_eq"]
            if "s_user_name" in data:
                self._device_name = data["s_user_name"]
            if "b_night_mode" in data:
                self._night_mode = data["b_night_mode"]
            if "b_auto_vol" in data:
                self._auto_volume_control = data["b_auto_vol"]
            if "b_drc" in data:
                self._dynamic_range_reduction = data["b_drc"]
            if "b_neuralx" in data:
                self._neural_x = data["b_neuralx"]
            if "b_tv_remote" in data:
                self._tv_remote = data["b_tv_remote"]
            if "b_auto_display" in data:
                self._auto_display = data["b_auto_display"]
            if current_sound_mode != self.sound_mode:
                update_data[Attributes.SOUND_MODE] = self.sound_mode
            if len(current_sound_modes) != len(self.sound_mode_list):
                update_data[Attributes.SOUND_MODE_LIST] = self.sound_mode_list
        elif response["msg"] == "PLAY_INFO":
            current_title = self.media_title
            current_artist = self.media_artist
            current_position = self.media_position
            current_duration = self.media_duration
            current_artwork = self.media_image_url
            if "s_title" in data:
                self._media_title = data["s_title"]
            if "s_artist" in data:
                self._media_artist = data["s_artist"]
            if "i_position" in data:
                self._media_position = data["i_position"]
                if self._media_position == -1:
                    self._media_position = 0
            if "i_duration" in data:
                self._media_duration = data["i_duration"]
                if self._media_duration == -1:
                    self._media_duration = 0
            if "s_albumart" in data:
                self._media_artwork = data["s_albumart"]

            if current_title != self.media_title:
                update_data[Attributes.MEDIA_TITLE] = self.media_title
            if current_artist != self.media_artist:
                update_data[Attributes.MEDIA_ARTIST] = self.media_artist
            if current_position != self.media_position:
                update_data[Attributes.MEDIA_POSITION] = self.media_position
            if current_duration != self.media_duration:
                update_data[Attributes.MEDIA_DURATION] = self.media_duration
            if current_artwork != self.media_image_url:
                update_data[Attributes.MEDIA_IMAGE_URL] = self.media_image_url

        if update_data:
            self.events.emit(
                Events.UPDATE,
                self.id,
                update_data
            )

    async def connect(self):
        # if self._session:
        #     await self._session.close()
        #     self._session = None
        # session_timeout = aiohttp.ClientTimeout(total=None, sock_connect=self._timeout, sock_read=self._timeout)
        # self._session = aiohttp.ClientSession(timeout=session_timeout,
        #                                       raise_for_status=True)
        # self._device.connect()
        self.events.emit(Events.CONNECTED, self.id)

    async def disconnect(self):
        if self._session:
            await self._session.close()
            self._session = None

    async def update(self):
        """Trigger updates from the device."""
        if self._update_lock.locked():
            return

        await self._update_lock.acquire()
        # if self._session is None:
        #     await self.connect()
        self._device.get_eq()
        self._device.get_info()
        self._device.get_func()
        self._device.get_settings()
        self._device.get_play()
        self._update_lock.release()

    async def update_volume(self):
        """Trigger updates from the device."""
        if self._update_lock.locked():
            return

        await self._update_lock.acquire()
        self._device.get_info()
        self._update_lock.release()

    @property
    def id(self):
        return self._id

    @property
    def hostname(self):
        return self._hostname

    @property
    def port(self):
        return self._port

    @property
    def volume_step(self):
        return self._volume_step

    @property
    def state(self) -> States:
        if not self._power_state:
            self._state = States.OFF
        else:
            self._state = States.ON
        return self._state

    @property
    def name(self):
        return self._name

    @property
    def device_name(self):
        return self._device_name

    @property
    def volume(self):
        if self._volume_max - self._volume_min == 0:
            return 0
        return 100 * abs((self._volume - self._volume_min) / (self._volume_max - self._volume_min))

    @property
    def muted(self):
        return self._mute

    @property
    def source(self):
        """Return the current input source."""
        if self._function == -1 or self._function >= len(functions):
            return None
        return functions[self._function]

    @property
    def source_list(self):
        """List of available input sources."""
        return sorted(
            functions[function]
            for function in self._functions
            if function < len(functions)
        )

    @property
    def is_on(self):
        return self.state in [States.PAUSED, States.STOPPED, States.PLAYING, States.ON]

    @property
    def sound_mode(self):
        """Return the current sound mode."""
        if self._equaliser == -1 or self._equaliser >= len(equalisers):
            return None
        return equalisers[self._equaliser]

    @property
    def sound_mode_list(self):
        """Return the available sound modes."""
        return sorted(
            equalisers[equaliser]
            for equaliser in self._equalisers
            if equaliser < len(equalisers)
        )

    @property
    def media_artist(self):
        return self._media_artist

    @property
    def media_title(self):
        return self._media_title

    @property
    def media_image_url(self):
        return self._media_artwork

    @property
    def media_position(self):
        return self._media_position

    @property
    def media_duration(self):
        return self._media_duration

    @cmd_wrapper
    async def toggle(self):
        if self.state == States.OFF:
            self._device.power(False)
        else:
            self._device.power(True)

    @cmd_wrapper
    async def turn_on(self):
        self._device.power(True)

    @cmd_wrapper
    async def turn_off(self):
        self._device.power(False)

    @cmd_wrapper
    async def select_source(self, source: str):
        """Set volume level, range 0..100."""
        if source is None:
            return ucapi.StatusCodes.BAD_REQUEST
        self._device.set_func(functions.index(source))

    @cmd_wrapper
    async def select_sound_mode(self, sound_mode: str) -> None:
        """Set Sound Mode for Receiver.."""
        self._device.set_eq(equalisers.index(sound_mode))

    @cmd_wrapper
    async def set_volume_level(self, volume: float | None):
        """Set volume level, range 0..100."""
        if volume is None:
            return ucapi.StatusCodes.BAD_REQUEST
        target_volume = volume * (self._volume_max - self._volume_min) / 100 + self._volume_min
        self._device.set_volume(int(target_volume))
        self._volume = target_volume
        self.events.emit(Events.UPDATE, self.id, {Attributes.VOLUME: self.volume})
        await self.update_volume()

    @cmd_wrapper
    async def volume_up(self):
        """Send volume-up command to AVR."""
        volume = self._volume + self._volume_step * (self._volume_max - self._volume_min) / 100
        volume = min(volume, self._volume_max)
        self._device.set_volume(int(volume))
        self._volume = volume
        self.events.emit(Events.UPDATE, self.id, {Attributes.VOLUME: self.volume})
        await self.update_volume()

    @cmd_wrapper
    async def volume_down(self):
        """Send volume-down command to AVR."""
        volume = self._volume - self._volume_step * (self._volume_max - self._volume_min) / 100
        volume = max(volume, self._volume_min)
        self._device.set_volume(int(volume))
        self._volume = volume
        self.events.emit(Events.UPDATE, self.id, {Attributes.VOLUME: self.volume})
        await self.update_volume()

    @cmd_wrapper
    async def mute(self, muted: bool):
        """Send mute command to AVR."""
        _LOGGER.debug("Sending mute: %s", muted)
        self._device.set_mute(muted)
        self.events.emit(Events.UPDATE, self.id, {Attributes.MUTED: muted})
        await self.update_volume()

    @cmd_wrapper
    async def send_command(self, command):
        if command == "MODE_NIGHT":
            self._device.set_night_mode(not self._night_mode)
        elif command == "MODE_AUTO_VOLUME_CONTROL":
            self._device.set_avc(not self._auto_volume_control)
        elif command == "MODE_DYNAMIC_RANGE_COMPRESSION":
            self._device.set_drc(not self._dynamic_range_reduction)
        elif command == "MODE_NEURALX":
            self._device.set_neuralx(not self._neural_x)
        elif command == "MODE_TV_REMOTE":
            self._device.set_tv_remote(not self._tv_remote)
        elif command == "MODE_AUTO_DISPLAY":
            self._device.set_auto_display(not self._auto_display)
        elif command == Commands.ON:
            self._device.power(True)
        elif command == Commands.OFF:
            self._device.power(False)
        elif command == Commands.TOGGLE:
            if self.state == States.OFF:
                self._device.power(False)
            else:
                self._device.power(True)
        elif command == Commands.VOLUME_UP:
            await self.volume_up()
            return
        elif command == Commands.VOLUME_DOWN:
            await self.volume_down()
            return
        elif command == Commands.MUTE:
            await self.mute()
            return
        await self.update()
