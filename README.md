# LG Soundbars integration for Remote Two

Using [uc-integration-api](https://github.com/aitatoi/integration-python-library)

The driver lets add your LG Soundbars on the network to your Remote Two. A media player and a remote entity are exposed to the core.

Supported attributes:

- State (on, off, playing, paused, unknown)
- Source list and selection
- Sound mode list and selection
- Media position
- Media duration
- Media title and artist
- Media artwork

Supported commands for media player :

- Turn on
- Turn off
- Toggle on/off
- Volume control
- Volume up/down
- Mute
- Input source selection (from the list)
- Source field selection (from the list)
- Simple commands including toggles settings of : night mode, auto volume control, neural X, dynamic range compression

Supported commands for remote entity :
- Send command
- Send command sequence
- Predefined buttons mapping
- Predefined UI mapping


## Todo
- Add missing commands : I had to sniff the network requests between the mobile app and the soundbar to grab missing commands. However the mobile app is limited and does not reproduce the physical buttons of the remote. So I have no idea how to make play/pause, next/previous, and simulate the direction pad. Maybe this is not possible
- Optimize the requests : actually the requests are not in sync with responses. This is not a problem but it could be optimized to have real sync.


### Setup

- Requires Python 3.11
- Install required libraries:  
  (using a [virtual environment](https://docs.python.org/3/library/venv.html) is highly recommended)

```shell
pip3 install -r requirements.txt
```

For running a separate integration driver on your network for Remote Two, the configuration in file
[driver.json](driver.json) needs to be changed:

- Set `driver_id` to a unique value, `uc_lgsoundbar_driver` is already used for the embedded driver in the firmware.
- Change `name` to easily identify the driver for discovery & setup with Remote Two or the web-configurator.
- Optionally add a `"port": 8090` field for the WebSocket server listening port.
    - Default port: `9092`
    - Also overrideable with environment variable `UC_INTEGRATION_HTTP_PORT`

### Run

```shell
python3 intg-lgsoundbar/driver.py
```

See
available [environment variables](https://github.com/unfoldedcircle/integration-python-library#environment-variables)
in the Python integration library to control certain runtime features like listening interface and configuration
directory.

### Available commands for the remote entity

Available commands for remote entity :

| Command                        | Description               |
|--------------------------------|---------------------------|
| MODE_NIGHT                     | Night mode                |
| MODE_AUTO_VOLUME_CONTROL       | Auto volume control       |
| MODE_DYNAMIC_RANGE_COMPRESSION | Dynamic range compression |
| MODE_NEURALX                   | Neural X                  |
| MODE_TV_REMOTE                 | Control TV                |
| MODE_AUTO_DISPLAY              | Auto display              |
| on                             | Power On                  |
| off                            | Power Off                 |
| toggle                         | Power toggle              |
| volume_up                      | Volume Up                 |
| volume_down                    | Volume Down               |
| mute                           | Mute toggle               |


## Build self-contained binary for Remote Two

After some tests, turns out python stuff on embedded is a nightmare. So we're better off creating a single binary file
that has everything in it.

To do that, we need to compile it on the target architecture as `pyinstaller` does not support cross compilation.

### x86-64 Linux

On x86-64 Linux we need Qemu to emulate the aarch64 target platform:

```bash
sudo apt install qemu binfmt-support qemu-user-static
docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
```

Run pyinstaller:

```shell
docker run --rm --name builder \
    --platform=aarch64 \
    --user=$(id -u):$(id -g) \
    -v "$PWD":/workspace \
    docker.io/unfoldedcircle/r2-pyinstaller:3.11.6  \
    bash -c \
      "python -m pip install -r requirements.txt && \
      pyinstaller --clean --onefile --name intg-lgsoundbar intg-lgsoundbar/driver.py"
```

### aarch64 Linux / Mac

On an aarch64 host platform, the build image can be run directly (and much faster):

```shell
docker run --rm --name builder \
    --user=$(id -u):$(id -g) \
    -v "$PWD":/workspace \
    docker.io/unfoldedcircle/r2-pyinstaller:3.11.6  \
    bash -c \
      "python -m pip install -r requirements.txt && \
      pyinstaller --clean --onefile --name intg-lgsoundbar intg-lgsoundbar/driver.py"
```

## Versioning

We use [SemVer](http://semver.org/) for versioning. For the versions available, see the
[tags and releases in this repository](https://github.com/albaintor/integration-panasonicbluray/releases).

## Changelog

The major changes found in each new release are listed in the [changelog](CHANGELOG.md)
and under the GitHub [releases](https://github.com/albaintor/integration-panasonicbluray/releases).

## Contributions

Please read our [contribution guidelines](CONTRIBUTING.md) before opening a pull request.

## License

This project is licensed under the [**Mozilla Public License 2.0**](https://choosealicense.com/licenses/mpl-2.0/).
See the [LICENSE](LICENSE) file for details.
