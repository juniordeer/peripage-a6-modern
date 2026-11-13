# PeriPage A6 F622: Printing Without PyBluez

Python 3.10+ client for the PeriPage A6 F622 using Linux Bluetooth Classic SPP/RFCOMM, channel 1. No PyBluez required: Bluetooth access uses Python's standard-library sockets. This is not a BLE workflow; Bleak is not a suitable replacement.

Supports raster images, SVG, QR codes, brightness/contrast adjustment and optional paper feed.

## Installation (Linux)

```bash
git clone https://github.com/juniordeer/peripage-a6-modern.git
cd peripage-a6-modern
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

Requires Linux with BlueZ, a Bluetooth Classic adapter, and Python with `socket.AF_BLUETOOTH` and `socket.BTPROTO_RFCOMM`. Pair the powered-on printer using your system Bluetooth tools (for example `bluetoothctl`) and find its MAC address. Pairing and scanning are not performed by this script. System-specific Bluetooth permissions may be needed. Windows and macOS are not supported by this implementation.

Pillow is required for raster images; `qrcode` is needed only for QR codes, and CairoSVG only for SVG output.

## Usage

Replace the example MAC address with your printer's address:

```bash
python3 peripage_print.py AA:BB:CC:DD:EE:FF --imagefile image.jpg
python3 peripage_print.py AA:BB:CC:DD:EE:FF --svg graphic.svg
python3 peripage_print.py AA:BB:CC:DD:EE:FF --qrcode "https://example.org"
python3 peripage_print.py AA:BB:CC:DD:EE:FF -b 1.2 -c 0.8 -i image.png
python3 peripage_print.py AA:BB:CC:DD:EE:FF -nf -i long-image.png
python3 peripage_print.py --help
```

At most one print mode may be specified. Without a mode, the program queries device information and resets the printer. Images are scaled to 384 pixels wide and converted to monochrome. Maximum scaled height: 65535 pixels. `-nf` suppresses the subsequent paper feed.

## Protocol and testing limitations

Protocol bytes and sequence are based on [eliasweingaertner/peripage-A6-bluetooth](https://github.com/eliasweingaertner/peripage-A6-bluetooth), which analyzed communication with the manufacturer's app. This is a proprietary protocol, not guaranteed generic ESC/POS compatibility. Data is sent in 122-byte chunks with a 20 ms delay.

Syntax, CLI help and offline image/protocol behavior were tested. **No physical printer test has been performed.** Print quality and compatibility with other PeriPage models are unverified.

## License and attribution

MIT license; see `LICENSE`. Original project copyright (c) 2021 Elias Weingärtner. This client reimplements Bluetooth access while retaining the original protocol bytes and sequence. Retain the copyright and permission notice when redistributing. Not affiliated with the manufacturer.
