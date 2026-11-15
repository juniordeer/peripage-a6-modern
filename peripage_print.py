#!/usr/bin/env python3
"""Print images on the PeriPage A6 F622 over Bluetooth Classic RFCOMM."""
from __future__ import annotations
import argparse
import io
import re
import socket
import sys
import time
from typing import Callable
try:
    from PIL import Image, ImageEnhance, ImageOps
except ImportError as exc:
    raise SystemExit("Missing dependency Pillow. Install with: python3 -m pip install -r requirements.txt") from exc
PRINTER_WIDTH = 384
RASTER_WIDTH_BYTES = PRINTER_WIDTH // 8
RFCOMM_CHANNEL = 1
CHUNK_SIZE = 122

def bluetooth_socket() -> socket.socket:
    """Create a Linux Bluetooth Classic RFCOMM socket."""
    if not hasattr(socket, "AF_BLUETOOTH") or not hasattr(socket, "BTPROTO_RFCOMM"):
        raise OSError("This Python/operating system installation does not provide an RFCOMM Bluetooth socket.")
    return socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)

class PeriPage:
    """RFCOMM protocol wrapper; command bytes match the upstream script."""
    def __init__(self, sock: socket.socket):
        self.sock = sock
    def request(self, command: bytes) -> bytes:
        self.sock.sendall(command)
        return self.sock.recv(1024)
    def device_name(self) -> bytes:
        return self.request(bytes.fromhex("10ff3011"))
    def firmware_info(self) -> bytes:
        return self.request(bytes.fromhex("10ff20f1"))
    def serial_number(self) -> bytes:
        return self.request(bytes.fromhex("10ff20f2"))
    def reset(self) -> bytes:
        answer = self.request(bytes.fromhex("10ff50f1"))
        self.sock.sendall(bytes.fromhex("000000000000000000000000"))
        return answer
    def begin_print(self) -> None:
        self.sock.sendall(bytes.fromhex("10fffe01"))
    def finish_print(self) -> None:
        self.sock.sendall(bytes.fromhex("1b4a4010fffe45"))

def load_image(path: str, svg: bool = False) -> Image.Image:
    if not svg:
        with Image.open(path) as source:
            source.load()
            return source.copy()
    try:
        import cairosvg
    except ImportError as exc:
        raise RuntimeError("SVG printing requires CairoSVG; see requirements.txt.") from exc
    png_data = cairosvg.svg2png(url=path, background_color="#FFFFFF", output_width=PRINTER_WIDTH)
    with Image.open(io.BytesIO(png_data)) as source:
        source.load()
        return source.copy()

def qr_image(content: str) -> Image.Image:
    try:
        import qrcode
    except ImportError as exc:
        raise RuntimeError("QR-code printing requires qrcode; see requirements.txt.") from exc
    return qrcode.make(content)

def prepare_image(image: Image.Image, brightness: float | None = None,
                  contrast: float | None = None) -> Image.Image:
    """Apply grayscale adjustments, invert and scale to 384 dots."""
    image = image.convert("L")
    if brightness is not None:
        image = ImageEnhance.Brightness(image).enhance(brightness)
    if contrast is not None:
        image = ImageEnhance.Contrast(image).enhance(contrast)
    image = ImageOps.invert(image)
    width, height = image.size
    if width <= 0 or height <= 0:
        raise ValueError("The input image has invalid dimensions.")
    out_height = int(height * PRINTER_WIDTH / width)
    if out_height < 1:
        raise ValueError("The image is too short to produce a print row after scaling.")
    if out_height > 65535:
        raise ValueError(f"Scaled image height ({out_height}) exceeds the protocol limit of 65535.")
    resampling = getattr(Image, "Resampling", Image).LANCZOS
    image = image.resize((PRINTER_WIDTH, out_height), resampling)
    return image.convert("1")

def print_image(printer: PeriPage, image: Image.Image, *, brightness: float | None = None,
                contrast: float | None = None, nofeed: bool = False,
                delay: float = 0.02, progress: Callable[[str], None] = print) -> None:
    image = prepare_image(image, brightness, contrast)
    width, height = image.size
    raster = image.tobytes()
    printer.begin_print()
    # ESC/POS raster command takes width in bytes per row, not printer dots.
    printer.sock.sendall(bytes.fromhex("000000000000000000000000"))
    printer.sock.sendall(bytes.fromhex("1d763000") + RASTER_WIDTH_BYTES.to_bytes(2, "little") + height.to_bytes(2, "little"))
    total = (len(raster) + CHUNK_SIZE - 1) // CHUNK_SIZE
    progress(f"Print image: {width} × {height} pixels; {total} data chunks.")
    for offset in range(0, len(raster), CHUNK_SIZE):
        printer.sock.sendall(raster[offset:offset + CHUNK_SIZE])
        if delay:
            time.sleep(delay)
    if not nofeed:
        progress("Advancing paper for cutting …")
        for _ in range(34):
            printer.sock.sendall(bytes(121))
            if delay:
                time.sleep(delay)
    printer.finish_print()
    progress("Print data sent successfully.")

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Print images, SVGs, or QR codes on a PeriPage A6 F622 (Bluetooth Classic/RFCOMM).")
    parser.add_argument("BTMAC", help="Bluetooth MAC address, e.g. B5:5B:13:08:F6:22")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("-i", "--imagefile", metavar="FILE", help="Raster image (e.g. JPG, PNG, TIFF)")
    mode.add_argument("-s", "--svg", metavar="FILE", help="Print an SVG file")
    mode.add_argument("-qr", "--qrcode", metavar="TEXT", help="Generate and print a QR code from this text")
    parser.add_argument("-b", "--brightness", type=float, help="Brightness factor (1.0 = unchanged)")
    parser.add_argument("-c", "--contrast", type=float, help="Contrast factor (1.0 = unchanged)")
    parser.add_argument("-nf", "--nofeed", action="store_true", help="Do not advance additional paper")
    parser.add_argument("--timeout", type=float, default=8.0, help="RFCOMM response timeout in seconds (default: 8)")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"(?i)[0-9a-f]{2}(:[0-9a-f]{2}){5}", args.BTMAC):
        parser.error("BTMAC must be a MAC address in the format AA:BB:CC:DD:EE:FF.")
    if args.timeout <= 0:
        parser.error("--timeout must be greater than 0.")
    if args.brightness is not None and args.brightness < 0:
        parser.error("--brightness cannot be negative.")
    if args.contrast is not None and args.contrast < 0:
        parser.error("--contrast cannot be negative.")
    return args

def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        with bluetooth_socket() as sock:
            sock.settimeout(args.timeout)
            print(f"Connecting to {args.BTMAC}, RFCOMM channel {RFCOMM_CHANNEL} …")
            sock.connect((args.BTMAC, RFCOMM_CHANNEL))
            printer = PeriPage(sock)
            print("Device name:", printer.device_name())
            print("Firmware/device info:", printer.firmware_info())
            print("Serial number:", printer.serial_number())
            print("Resetting printer …")
            printer.reset()
            if args.imagefile:
                image = load_image(args.imagefile)
            elif args.svg:
                image = load_image(args.svg, svg=True)
            elif args.qrcode:
                image = qr_image(args.qrcode)
            else:
                print("Device query/reset completed (no print mode specified).")
                return 0
            print_image(printer, image, brightness=args.brightness, contrast=args.contrast, nofeed=args.nofeed)
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        if isinstance(exc, (ConnectionError, TimeoutError)):
            print("Check the Bluetooth connection: power on and pair the printer, then verify its MAC address.", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())