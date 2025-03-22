"""
LG soundbar library handling of the integration driver.

:copyright: (c) 2023 by Unfolded Circle ApS.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""
import asyncio
import json
import logging
import struct
from asyncio import Server, BaseTransport, Task, Transport
from typing import Callable, Any, Awaitable

from Crypto.Cipher import AES

_LOG = logging.getLogger(__name__)

equalisers = ["Standard", "Bass", "Flat", "Boost", "Treble and Bass", "User",
              "Music", "Cinema", "Night", "News", "Voice", "ia_sound",
              "Adaptive Sound Control", "Movie", "Bass Blast", "Dolby Atmos",
              "DTS Virtual X", "Bass Boost Plus", "DTS X", "AI Sound Pro",
              "Clear Voice", "Sports", "Game"]

STANDARD = 0
BASS = 1
FLAT = 2
BOOST = 3
TREBLE_BASS = 4
USER_EQ = 5
MUSIC = 6
CINEMA = 7
NIGHT = 8
NEWS = 9
VOICE = 10
IA_SOUND = 11
ASC = 12
MOVIE = 13
BASS_BLAST = 14
DOLBY_ATMOS = 15
DTS_VIRTUAL_X = 16
BASS_BOOST_PLUS = 17
DTS_X = 18
AI_SOUND_PRO = 19
CLEAR_VOICE = 20
SPORTS = 21
GAME = 22

functions = ["Wi-Fi", "Bluetooth", "Portable", "Aux", "Optical", "CP", "HDMI",
             "ARC", "Spotify", "Optical2", "HDMI2", "HDMI3", "LG TV", "Mic",
             "Chromecast", "Optical/HDMI ARC", "LG Optical", "FM", "USB", "USB2",
             "E-ARC"]

functions_map = {
    "Optical": "Optical/HDMI ARC",
    "ARC": "Optical/HDMI ARC",
}

WIFI = 0
BLUETOOTH = 1
PORTABLE = 2
AUX = 3
OPTICAL = 4
CP = 5
HDMI = 6
ARC = 7
SPOTIFY = 8
OPTICAL_2 = 9
HDMI_2 = 10
HDMI_3 = 11
LG_TV = 12
MIC = 13
C4A = 14
OPTICAL_HDMIARC = 15
LG_OPTICAL = 16
FM = 17
USB = 18
USB_2 = 19
E_ARC = 20

stream_types = ["Unknown0", "Google Cast", "Unknown2", "Airplay", "Spotify Connect"]

GOOGLE_CAST = 1
SPOTIFY_CONNECT = 4

play_control_states = ["Playing", "Stopped/Paused"]

PLAYING = 0
PAUSED = 1


class Temescal(asyncio.Protocol):
    """LG library."""

    def __init__(self, address, port=9741, callback:Callable[[Any], None]|None = None, logger=None):
        """Initialize a LG soundbar device."""
        self.iv = b"'%^Ur7gy$~t+f)%@"
        self.key = b"T^&*J%^7tr~4^%^&I(o%^!jIJ__+a0 k"
        self.address = address
        self.port = port
        self.callback = callback
        self.logger = logger
        self._transport: Transport | None = None
        self._loop = asyncio.get_event_loop()
        self._connected = False

    def connection_made(self, transport: BaseTransport):
        # peername = transport.get_extra_info('peername')
        # print('Connection from {}'.format(peername))
        self._transport = transport
        self._connected = True

    def data_received(self, data: bytes):
        if len(data) == 0:
            self._transport.close()
            self._transport = None
            self.connect()
            return

        if data[0] == 0x10:
            data = data[1:]
            length = struct.unpack(">I", data[0:4])[0]
            data = data[4:]
            data = data[:length]
            if len(data) % 16 != 0:
                return
            response = self.decrypt_packet(data)
            if response is not None:
                # Better to create a task ?
                #self.callback(json.loads(response))
                asyncio.create_task(self.handle_response(response))

    async def handle_response(self, response):
        self.callback(json.loads(response))

    async def _connection_task(self):
        self._transport, protocol = await self._loop.create_connection(
            lambda: self,
            host=self.address, port=self.port)

    async def connect(self):
        """Connect to the device."""
        if self._transport:
            return
        try:
            await asyncio.wait_for(self._connection_task(), timeout=5)
            _LOG.debug("Server connected %s", self.connected)
        except Exception as ex:
            _LOG.error("Unable to connect %s", ex)

        # self._transport, protocol = await self._loop.create_connection(
        #     lambda: self,
        #     host=self.address, port=self.port)

    def disconnect(self):
        """Disconnect from the device."""
        if self._transport:
            self._transport.close()
            self._transport = None
            self._connected = False

    def reconnect(self):
        """Reconnect."""
        self.disconnect()
        self.connect()

    @property
    def connected(self) -> bool:
        return self._connected

    def encrypt_packet(self, data):
        """Encrypt packet to send to the device."""
        padlen = 16 - (len(data) % 16)
        for _i in range(padlen):
            data = data + chr(padlen)
        data = data.encode("utf-8")
        cipher = AES.new(self.key, AES.MODE_CBC, self.iv)

        encrypted = cipher.encrypt(data)
        length = len(encrypted)
        prelude = bytearray([0x10, 0x00, 0x00, 0x00, length])
        return prelude + encrypted

    def decrypt_packet(self, data):
        """Decrypt received packet."""
        cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
        decrypt = cipher.decrypt(data)
        padding = decrypt[-1:]
        decrypt = decrypt[: -ord(padding)]
        return str(decrypt, "utf-8")

    def send_packet(self, data):
        """Send a packet."""
        # pylint: disable=W0718
        if self._transport is None:
            _LOG.debug("Cannot send any packet, no connection active")
            return
        packet = self.encrypt_packet(json.dumps(data))
        try:
            self._transport.write(packet)
        except Exception as ex:
            _LOG.error("Error sending packet %s", ex)
            try:
                self._loop.run_until_complete(self.connect)
                self._transport.write(packet)
            except Exception:
                _LOG.error("Error sending packet #2 %s", ex)
                pass

    def power(self, value: bool):
        """Power command."""
        data = {"cmd": "set", "data": {"b_powerkey": value}, "msg": "SPK_LIST_VIEW_INFO"}
        self.send_packet(data)

    def get_eq(self):
        """Get equalizer settings."""
        data = {"cmd": "get", "msg": "EQ_VIEW_INFO"}
        self.send_packet(data)

    def set_eq(self, eq):
        """Set equalizer settings."""
        data = {"cmd": "set", "data": {"i_curr_eq": eq}, "msg": "EQ_VIEW_INFO"}
        self.send_packet(data)

    def get_info(self):
        """Get information."""
        data = {"cmd": "get", "msg": "SPK_LIST_VIEW_INFO"}
        self.send_packet(data)

    def get_play(self):
        """Get play state."""
        data = {"cmd": "get", "msg": "PLAY_INFO"}
        self.send_packet(data)

    def get_func(self):
        """Get functions information."""
        data = {"cmd": "get", "msg": "FUNC_VIEW_INFO"}
        self.send_packet(data)

    def get_settings(self):
        """Get settings information."""
        data = {"cmd": "get", "msg": "SETTING_VIEW_INFO"}
        self.send_packet(data)

    def get_product_info(self):
        """Get product information."""
        data = {"cmd": "get", "msg": "PRODUCT_INFO"}
        self.send_packet(data)

    def get_c4a_info(self):
        """Get C4A_SETTING_INFO."""
        data = {"cmd": "get", "msg": "C4A_SETTING_INFO"}
        self.send_packet(data)

    def get_radio_info(self):
        """Get radio information."""
        data = {"cmd": "get", "msg": "RADIO_VIEW_INFO"}
        self.send_packet(data)

    def get_ap_info(self):
        """Get app information."""
        data = {"cmd": "get", "msg": "SHARE_AP_INFO"}
        self.send_packet(data)

    def get_update_info(self):
        """Get update information."""
        data = {"cmd": "get", "msg": "UPDATE_VIEW_INFO"}
        self.send_packet(data)

    def get_build_info(self):
        """Get build information."""
        data = {"cmd": "get", "msg": "BUILD_INFO_DEV"}
        self.send_packet(data)

    def get_option_info(self):
        """Get options information."""
        data = {"cmd": "get", "msg": "OPTION_INFO_DEV"}
        self.send_packet(data)

    def get_mac_info(self):
        """Get mac information."""
        data = {"cmd": "get", "msg": "MAC_INFO_DEV"}
        self.send_packet(data)

    def get_mem_mon_info(self):
        """Get memory monitoring information."""
        data = {"cmd": "get", "msg": "MEM_MON_DEV"}
        self.send_packet(data)

    def get_test_info(self):
        """Get test information."""
        data = {"cmd": "get", "msg": "TEST_DEV"}
        self.send_packet(data)

    def test_tone(self):
        """Get test tone."""
        data = {"cmd": "set", "msg": "TEST_TONE_REQ"}
        self.send_packet(data)

    def set_night_mode(self, enable):
        """Set night mode."""
        data = {"cmd": "set", "data": {"b_night_mode": enable}, "msg": "SETTING_VIEW_INFO"}
        self.send_packet(data)

    def set_avc(self, enable):
        """Set AVC mode."""
        data = {"cmd": "set", "data": {"b_auto_vol": enable}, "msg": "SETTING_VIEW_INFO"}
        self.send_packet(data)

    def set_drc(self, enable):
        """Set dynamic range compression."""
        data = {"cmd": "set", "data": {"b_drc": enable}, "msg": "SETTING_VIEW_INFO"}
        self.send_packet(data)

    def set_neuralx(self, enable):
        """Set Neural X."""
        data = {"cmd": "set", "data": {"b_neuralx": enable}, "msg": "SETTING_VIEW_INFO"}
        self.send_packet(data)

    def set_av_sync(self, value):
        """Set AV sync."""
        data = {"cmd": "set", "data": {"i_av_sync": value}, "msg": "SETTING_VIEW_INFO"}
        self.send_packet(data)

    def set_woofer_level(self, value):
        """Set subwoofer level."""
        data = {"cmd": "set", "data": {"i_woofer_level": value}, "msg": "SETTING_VIEW_INFO"}
        self.send_packet(data)

    def set_rear_control(self, enable):
        """Set rear control."""
        data = {"cmd": "set", "data": {"b_rear": enable}, "msg": "SETTING_VIEW_INFO"}
        self.send_packet(data)

    def set_rear_level(self, value):
        """Set rear level."""
        data = {"cmd": "set", "data": {"i_rear_level": value}, "msg": "SETTING_VIEW_INFO"}
        self.send_packet(data)

    def set_top_level(self, value):
        """Set top level."""
        data = {"cmd": "set", "data": {"i_top_level": value}, "msg": "SETTING_VIEW_INFO"}
        self.send_packet(data)

    def set_center_level(self, value):
        """Set center level."""
        data = {"cmd": "set", "data": {"i_center_level": value}, "msg": "SETTING_VIEW_INFO"}
        self.send_packet(data)

    def set_tv_remote(self, enable):
        """Enable TV remote."""
        data = {"cmd": "set", "data": {"b_tv_remote": enable}, "msg": "SETTING_VIEW_INFO"}
        self.send_packet(data)

    def set_auto_power(self, enable):
        """Set auto power."""
        data = {"cmd": "set", "data": {"b_auto_power": enable}, "msg": "SETTING_VIEW_INFO"}
        self.send_packet(data)

    def set_auto_display(self, enable):
        """Set auto display."""
        data = {"cmd": "set", "data": {"b_auto_display": enable}, "msg": "SETTING_VIEW_INFO"}
        self.send_packet(data)

    def set_bt_standby(self, enable):
        """Set Bluetooth standby."""
        data = {"cmd": "set", "data": {"b_bt_standby": enable}, "msg": "SETTING_VIEW_INFO"}
        self.send_packet(data)

    def set_bt_restrict(self, enable):
        """Set Bluetooth restriction."""
        data = {"cmd": "set", "data": {"b_conn_bt_limit": enable}, "msg": "SETTING_VIEW_INFO"}
        self.send_packet(data)

    def set_sleep_time(self, value):
        """Set sleep time."""
        data = {"cmd": "set", "data": {"i_sleep_time": value}, "msg": "SETTING_VIEW_INFO"}
        self.send_packet(data)

    def set_func(self, value):
        """Set source."""
        data = {"cmd": "set", "data": {"i_curr_func": value}, "msg": "FUNC_VIEW_INFO"}
        self.send_packet(data)

    def set_volume(self, value):
        """Set volume."""
        data = {"cmd": "set", "data": {"i_vol": value}, "msg": "SPK_LIST_VIEW_INFO"}
        self.send_packet(data)

    def set_mute(self, enable):
        """Set mute."""
        data = {"cmd": "set", "data": {"b_mute": enable}, "msg": "SPK_LIST_VIEW_INFO"}
        self.send_packet(data)

    def set_name(self, name):
        """Set device name."""
        data = {"cmd": "set", "data": {"s_user_name": name}, "msg": "SETTING_VIEW_INFO"}
        self.send_packet(data)

    def send_command(self, msg, data):
        """Send a command."""
        if data:
            payload = {"cmd": "set", "data": data, "msg": msg}
        else:
            payload = {"cmd": "set", "msg": msg}
        self.send_packet(payload)

    def set_factory(self):
        """Set to factory."""
        data = {"cmd": "set", "msg": "FACTORY_SET_REQ"}
        self.send_packet(data)
