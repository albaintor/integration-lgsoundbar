"""
Setup flow for Panasonic Bluray integration.

:copyright: (c) 2025 by Albaintor
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import asyncio
import logging
from enum import IntEnum

from ucapi import (
    AbortDriverSetup,
    DriverSetupRequest,
    IntegrationSetupError,
    RequestUserInput,
    SetupAction,
    SetupComplete,
    SetupDriver,
    SetupError,
    UserDataResponse,
)
from ucapi.media_player import States

import config
from client import LGDevice
from config import ConfigDevice
from const import DEFAULT_PORT, DEFAULT_VOLUME_STEP

_LOG = logging.getLogger(__name__)


class SetupSteps(IntEnum):
    """Enumeration of setup steps to keep track of user data responses."""

    INIT = 0
    WORKFLOW_MODE = 1
    DEVICE_CONFIGURATION_MODE = 2
    DISCOVER = 3
    DEVICE_CHOICE = 4
    RECONFIGURE = 5
    BACKUP_RESTORE = 6


# pylint: disable=C0103
_setup_step = SetupSteps.INIT
_discovered_devices: list[LGDevice] = []
_cfg_add_device: bool = False
_reconfigured_device: ConfigDevice | None = None
_user_input_discovery = RequestUserInput(
    {"en": "Setup mode", "de": "Setup Modus", "fr": "Configuration"},
    [
        {
            "field": {"text": {"value": ""}},
            "id": "address",
            "label": {"en": "Endpoint", "de": "Adresse", "fr": "Adresse"},
        },
        {
            "field": {"text": {"value": str(DEFAULT_PORT)}},
            "id": "port",
            "label": {"en": "Port", "de": "Port", "fr": "Port"},
        },
        {
            "id": "volume_step",
            "label": {
                "en": "Volume step",
                "fr": "Pallier de volume",
            },
            "field": {
                "number": {
                    "value": DEFAULT_VOLUME_STEP,
                    "min": 0.5,
                    "max": 10,
                    "steps": 1,
                    "decimals": 1,
                    "unit": {"en": "dB"},
                }
            },
        },
        {
            "id": "info",
            "label": {"en": ""},
            "field": {
                "label": {
                    "value": {
                        "en": "You should set a static IP for your soundbar.",
                        "fr": "Vous devriez paraméter une adresse IP fixe pour votre barre de son.",
                    }
                }
            },
        },
    ],
)


# pylint: disable=R0911
async def driver_setup_handler(msg: SetupDriver) -> SetupAction:
    """
    Dispatch driver setup requests to corresponding handlers.

    Either start the setup process or handle the selected AVR device.

    :param msg: the setup driver request object, either DriverSetupRequest or UserDataResponse
    :return: the setup action on how to continue
    """
    global _setup_step
    global _cfg_add_device

    _LOG.debug("driver_setup_handler")

    if isinstance(msg, DriverSetupRequest):
        _setup_step = SetupSteps.INIT
        _cfg_add_device = False
        return await handle_driver_setup(msg)
    if isinstance(msg, UserDataResponse):
        _LOG.debug("Setup handler message : step %s, message : %s", _setup_step, msg)
        if _setup_step == SetupSteps.WORKFLOW_MODE:
            if msg.input_values.get("configuration_mode", "") == "normal":
                _setup_step = SetupSteps.DEVICE_CONFIGURATION_MODE
                _LOG.debug("Starting normal setup workflow")
                return _user_input_discovery
            _LOG.debug("User requested backup/restore of configuration")
            return await _handle_backup_restore_step()
        if _setup_step == SetupSteps.DEVICE_CONFIGURATION_MODE:
            if "action" in msg.input_values:
                _LOG.debug("Setup flow starts with existing configuration")
                return await handle_configuration_mode(msg)
            _LOG.debug("Setup flow configuration mode")
            return await _handle_discovery(msg)
        if _setup_step == SetupSteps.DISCOVER and "address" in msg.input_values:
            return await _handle_discovery(msg)
        if _setup_step == SetupSteps.DEVICE_CHOICE and "choice" in msg.input_values:
            return await handle_device_choice(msg)
        if _setup_step == SetupSteps.RECONFIGURE:
            return await _handle_device_reconfigure(msg)
        if _setup_step == SetupSteps.BACKUP_RESTORE:
            return await _handle_backup_restore(msg)
        _LOG.error("No or invalid user response was received: %s", msg)
    elif isinstance(msg, AbortDriverSetup):
        _LOG.info("Setup was aborted with code: %s", msg.error)
        _setup_step = SetupSteps.INIT

    # user confirmation not used in setup process
    # if isinstance(msg, UserConfirmationResponse):
    #     return handle_user_confirmation(msg)

    return SetupError()


async def handle_driver_setup(_msg: DriverSetupRequest) -> RequestUserInput | SetupError:
    """
    Start driver setup.

    Initiated by Remote Two to set up the driver.
    Ask user to enter ip-address for manual configuration, otherwise auto-discovery is used.

    :param _msg: not used, we don't have any input fields in the first setup screen.
    :return: the setup action on how to continue
    """
    global _setup_step

    # workaround for web-configurator not picking up first response
    await asyncio.sleep(1)

    reconfigure = _msg.reconfigure
    _LOG.debug("Handle driver setup, reconfigure=%s", reconfigure)
    if reconfigure:
        _setup_step = SetupSteps.DEVICE_CONFIGURATION_MODE

        # get all configured devices for the user to choose from
        dropdown_devices = []
        for device in config.devices.all():
            dropdown_devices.append({"id": device.id, "label": {"en": f"{device.name} ({device.id})"}})

        # TODO #12 externalize language texts
        # build user actions, based on available devices
        dropdown_actions = [
            {
                "id": "add",
                "label": {
                    "en": "Add a new device",
                    "de": "Neues Gerät hinzufügen",
                    "fr": "Ajouter un nouvel appareil",
                },
            },
        ]

        # add remove & reset actions if there's at least one configured device
        if dropdown_devices:
            dropdown_actions.append(
                {
                    "id": "configure",
                    "label": {
                        "en": "Configure selected device",
                        "fr": "Configurer l'appareil sélectionné",
                    },
                },
            )
            dropdown_actions.append(
                {
                    "id": "remove",
                    "label": {
                        "en": "Delete selected device",
                        "de": "Selektiertes Gerät löschen",
                        "fr": "Supprimer l'appareil sélectionné",
                    },
                },
            )
            dropdown_actions.append(
                {
                    "id": "reset",
                    "label": {
                        "en": "Reset configuration and reconfigure",
                        "de": "Konfiguration zurücksetzen und neu konfigurieren",
                        "fr": "Réinitialiser la configuration et reconfigurer",
                    },
                },
            )
        else:
            # dummy entry if no devices are available
            dropdown_devices.append({"id": "", "label": {"en": "---"}})

        dropdown_actions.append(
            {
                "id": "backup_restore",
                "label": {
                    "en": "Backup or restore devices configuration",
                    "fr": "Sauvegarder ou restaurer la configuration des appareils",
                },
            },
        )

        return RequestUserInput(
            {"en": "Configuration mode", "de": "Konfigurations-Modus"},
            [
                {
                    "field": {"dropdown": {"value": dropdown_devices[0]["id"], "items": dropdown_devices}},
                    "id": "choice",
                    "label": {
                        "en": "Configured devices",
                        "de": "Konfigurierte Geräte",
                        "fr": "Appareils configurés",
                    },
                },
                {
                    "field": {"dropdown": {"value": dropdown_actions[0]["id"], "items": dropdown_actions}},
                    "id": "action",
                    "label": {
                        "en": "Action",
                        "de": "Aktion",
                        "fr": "Appareils configurés",
                    },
                },
            ],
        )
    # Initial setup, make sure we have a clean configuration
    config.devices.clear()  # triggers device instance removal
    _setup_step = SetupSteps.WORKFLOW_MODE
    return RequestUserInput(
        {"en": "Configuration mode", "de": "Konfigurations-Modus"},
        [
            {
                "field": {
                    "dropdown": {
                        "value": "normal",
                        "items": [
                            {
                                "id": "normal",
                                "label": {
                                    "en": "Start the configuration of the integration",
                                    "fr": "Démarrer la configuration de l'intégration",
                                },
                            },
                            {
                                "id": "backup_restore",
                                "label": {
                                    "en": "Backup or restore devices configuration",
                                    "fr": "Sauvegarder ou restaurer la configuration des appareils",
                                },
                            },
                        ],
                    }
                },
                "id": "configuration_mode",
                "label": {
                    "en": "Configuration mode",
                    "fr": "Mode de configuration",
                },
            }
        ],
    )


async def handle_configuration_mode(msg: UserDataResponse) -> RequestUserInput | SetupComplete | SetupError:
    """
    Process user data response in a setup process.

    If ``address`` field is set by the user: try connecting to device and retrieve model information.
    Otherwise, start Android TV discovery and present the found devices to the user to choose from.

    :param msg: response data from the requested user data
    :return: the setup action on how to continue
    """
    global _setup_step
    global _cfg_add_device
    global _reconfigured_device

    action = msg.input_values["action"]

    _LOG.debug("Handle configuration mode")

    # workaround for web-configurator not picking up first response
    await asyncio.sleep(1)

    match action:
        case "add":
            _cfg_add_device = True
        case "remove":
            choice = msg.input_values["choice"]
            if not config.devices.remove(choice):
                _LOG.warning("Could not remove device from configuration: %s", choice)
                return SetupError(error_type=IntegrationSetupError.OTHER)
            config.devices.store()
            return SetupComplete()
        case "configure":
            # Reconfigure device if the identifier has changed
            choice = msg.input_values["choice"]
            selected_device = config.devices.get(choice)
            if not selected_device:
                _LOG.warning("Can not configure device from configuration: %s", choice)
                return SetupError(error_type=IntegrationSetupError.OTHER)

            _setup_step = SetupSteps.RECONFIGURE
            _reconfigured_device = selected_device

            return RequestUserInput(
                {
                    "en": "Configure your LG Soundbar",
                    "fr": "Configurez votre décodeur LG Soundbar",
                },
                [
                    {
                        "field": {"text": {"value": _reconfigured_device.address}},
                        "id": "address",
                        "label": {"en": "IP address", "de": "IP-Adresse", "fr": "Adresse IP"},
                    },
                    {
                        "id": "port",
                        "label": {
                            "en": "Port number",
                            "fr": "Numéro de port",
                        },
                        "field": {
                            "number": {
                                "value": _reconfigured_device.port,
                                "min": 1,
                                "max": 65535,
                                "steps": 1,
                                "decimals": 0,
                            }
                        },
                    },
                    {
                        "id": "volume_step",
                        "label": {
                            "en": "Volume step",
                            "fr": "Pallier de volume",
                        },
                        "field": {
                            "number": {
                                "value": _reconfigured_device.volume_step,
                                "min": 1,
                                "max": 10,
                                "steps": 1,
                                "decimals": 0,
                            }
                        },
                    },
                    {
                        "id": "always_on",
                        "label": {
                            "en": "Keep connection alive (faster initialization, but consumes more battery)",
                            "fr": "Conserver la connexion active (lancement plus rapide, mais consomme plus de "
                            "batterie)",
                        },
                        "field": {"checkbox": {"value": _reconfigured_device.always_on}},
                    },
                ],
            )
        case "reset":
            config.devices.clear()  # triggers device instance removal
        case "backup_restore":
            return await _handle_backup_restore_step()
        case _:
            _LOG.error("Invalid configuration action: %s", action)
            return SetupError(error_type=IntegrationSetupError.OTHER)

    _setup_step = SetupSteps.DISCOVER
    return _user_input_discovery


async def _handle_discovery(msg: UserDataResponse) -> RequestUserInput | SetupError:
    """
    Process user data response in a setup process.

    If ``address`` field is set by the user: try connecting to device and retrieve model information.
    Otherwise, start discovery and present the found devices to the user to choose from.

    :param msg: response data from the requested user data
    :return: the setup action on how to continue
    """
    # pylint: disable=W0718,R0911
    global _setup_step
    global _discovered_devices
    _discovered_devices = []

    dropdown_items = []
    _LOG.debug("Handle driver setup with discovery")

    address = msg.input_values["address"]
    port = msg.input_values["port"]
    volume_step = 1.0
    try:
        volume_step = float(msg.input_values.get("volume_step", 1))
        if volume_step < 0.1 or volume_step > 10:
            return SetupError(error_type=IntegrationSetupError.OTHER)
    except ValueError:
        return SetupError(error_type=IntegrationSetupError.OTHER)

    if address:
        _LOG.debug("Starting manual driver setup for %s", address)
        try:
            # simple connection check
            device = LGDevice(
                device_config=ConfigDevice(
                    id=address, address=address, port=int(port), volume_step=volume_step, name="LG", always_on=False
                )
            )
            await device.update(True)
            await asyncio.sleep(3)
            if device.state == States.UNKNOWN:
                _LOG.error("Cannot connect to manually entered address %s", address)
                return SetupError(error_type=IntegrationSetupError.CONNECTION_REFUSED)
            dropdown_items.append({"id": address, "label": {"en": f"{device.device_name}"}})
            _discovered_devices.append(device)
        except Exception as ex:
            _LOG.error("Cannot connect to manually entered address %s: %s", address, ex)
            return SetupError(error_type=IntegrationSetupError.CONNECTION_REFUSED)
    else:
        return SetupError(error_type=IntegrationSetupError.OTHER)

    if not dropdown_items:
        _LOG.warning("No device found")
        return SetupError(error_type=IntegrationSetupError.NOT_FOUND)

    _setup_step = SetupSteps.DEVICE_CHOICE
    return RequestUserInput(
        {
            "en": "Please choose your LG soundbar",
            "fr": "Sélectionnez votre barre de son LG",
        },
        [
            {
                "field": {"dropdown": {"value": dropdown_items[0]["id"], "items": dropdown_items}},
                "id": "choice",
                "label": {
                    "en": "Please choose your LG soundbar",
                    "fr": "Sélectionnez votre barre de son LG",
                },
            },
            {
                "id": "volume_step",
                "label": {
                    "en": "Volume step",
                    "fr": "Pallier de volume",
                },
                "field": {
                    "number": {
                        "value": DEFAULT_VOLUME_STEP,
                        "min": 1,
                        "max": 10,
                        "steps": 1,
                        "decimals": 0,
                    }
                },
            },
            {
                "id": "always_on",
                "label": {
                    "en": "Keep connection alive (faster initialization, but consumes more battery)",
                    "fr": "Conserver la connexion active (lancement plus rapide, mais consomme plus de batterie)",
                },
                "field": {"checkbox": {"value": False}},
            },
        ],
    )


async def handle_device_choice(msg: UserDataResponse) -> SetupComplete | SetupError:
    """
    Process user data response in a setup process.

    Driver setup callback to provide requested user data during the setup process.

    :param msg: response data from the requested user data
    :return: the setup action on how to continue: SetupComplete if a valid AVR device was chosen.
    """
    # pylint: disable=W0602
    global _discovered_devices
    host = msg.input_values["choice"]
    always_on = msg.input_values.get("always_on", "false") == "true"
    try:
        volume_step = float(msg.input_values.get("volume_step", 1.0))
        if volume_step < 0.1 or volume_step > 10:
            return SetupError(error_type=IntegrationSetupError.OTHER)
    except ValueError:
        return SetupError(error_type=IntegrationSetupError.OTHER)

    device: LGDevice | None = None
    if _discovered_devices:
        for _device in _discovered_devices:
            if _device.hostname == host:
                device = _device
                break

    _LOG.debug("Chosen LG device: %s %s", device.device_name, device.hostname)

    assert device
    if device.serial_number:
        unique_id = device.serial_number
    else:
        unique_id = device.hostname

    if unique_id is None:
        _LOG.error("Could not get identifier of host %s: required to create a unique device", host)
        return SetupError(error_type=IntegrationSetupError.OTHER)

    config.devices.add_or_update(
        ConfigDevice(
            id=unique_id,
            name=device.device_name,
            address=device.hostname,
            port=device.port,
            volume_step=device.volume_step,
            always_on=always_on,
        )
    )  # triggers Panasonic BR instance creation
    config.devices.store()

    # AVR device connection will be triggered with subscribe_entities request

    await asyncio.sleep(1)

    _LOG.info("Setup successfully completed for %s (%s)", device.hostname, unique_id)
    return SetupComplete()


async def _handle_backup_restore_step() -> RequestUserInput:
    global _setup_step

    _setup_step = SetupSteps.BACKUP_RESTORE
    current_config = config.devices.export()

    _LOG.debug("Handle backup/restore step")

    return RequestUserInput(
        {
            "en": "Backup or restore devices configuration (all existing devices will be removed)",
            "fr": "Sauvegarder ou restaurer la configuration des appareils (tous les appareils existants seront "
            "supprimés)",
        },
        [
            {
                "field": {
                    "textarea": {
                        "value": current_config,
                    }
                },
                "id": "config",
                "label": {
                    "en": "Devices configuration",
                    "fr": "Configuration des appareils",
                },
            },
        ],
    )


async def _handle_device_reconfigure(msg: UserDataResponse) -> SetupComplete | SetupError:
    """
    Process reconfiguration of a registered Android TV device.

    :param msg: response data from the requested user data
    :return: the setup action on how to continue: SetupComplete after updating configuration
    """
    # flake8: noqa:F824
    # pylint: disable=W0602
    global _reconfigured_device

    if _reconfigured_device is None:
        return SetupError()

    address = msg.input_values.get("address", "")
    try:
        port = int(msg.input_values.get("port", DEFAULT_PORT))
        volume_step = float(msg.input_values.get("volume_step", 1.0))
        if volume_step < 0.1 or volume_step > 10:
            return SetupError(error_type=IntegrationSetupError.OTHER)
    except ValueError:
        return SetupError(error_type=IntegrationSetupError.OTHER)

    always_on = msg.input_values.get("always_on", "false") == "true"

    _LOG.debug("User has changed configuration")
    _reconfigured_device.address = address
    _reconfigured_device.port = port
    _reconfigured_device.volume_step = volume_step
    _reconfigured_device.always_on = always_on

    config.devices.add_or_update(_reconfigured_device)  # triggers ATV instance update
    await asyncio.sleep(1)
    _LOG.info("Setup successfully completed for %s", _reconfigured_device.name)

    return SetupComplete()


async def _handle_backup_restore(msg: UserDataResponse) -> SetupComplete | SetupError:
    """
    Process import of configuration

    :param msg: response data from the requested user data
    :return: the setup action on how to continue: SetupComplete after updating configuration
    """
    # flake8: noqa:F824
    # pylint: disable=W0602
    global _reconfigured_device

    _LOG.debug("Handle backup/restore")
    updated_config = msg.input_values["config"]
    _LOG.info("Replacing configuration with : %s", updated_config)
    if not config.devices.import_config(updated_config):
        _LOG.error("Setup error : unable to import updated configuration %s", updated_config)
        return SetupError(error_type=IntegrationSetupError.OTHER)
    _LOG.debug("Configuration imported successfully")

    await asyncio.sleep(1)
    return SetupComplete()
