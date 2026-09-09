#!/usr/bin/env python3

"""Generate an rwmem register database for the Sony IMX219 image sensor.

The register list is collected by hand from the Linux imx219 driver
(drivers/media/i2c/imx219.c). The driver is the only source used, so the
database has just the registers the driver touches, and fields only where the
driver shows how a register is laid out. Value meanings the driver knows are
given in the descriptions.

The sensor sits on I2C, usually at address 0x10, with 16-bit big-endian
register addresses and 8-bit registers. The 16-bit quantities are big-endian
byte pairs at consecutive addresses, the CCI_REG16() registers in the driver.

Usage:
    gen-imx219.py [output.regdb]

    rwmem i2c <bus>:0x10 -r imx219.regdb IMX219.CHIP_ID
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'py'))

from rwmem.enums import Endianness
from rwmem.gen import UnpackedField, UnpackedRegBlock, UnpackedRegFile, UnpackedRegister

DEFAULT_OUTPUT = os.path.normpath(os.path.join(os.path.dirname(__file__), 'imx219.regdb'))

# Registers the driver names: (name, address, size in bytes, description, fields)
# fields: (name, high bit, low bit, description)
REGS = [
    # Chip ID
    ('CHIP_ID', 0x0000, 2, 'Chip ID, reads 0x0219', []),
    # Mode and interface setup
    ('MODE_SELECT', 0x0100, 1, '0: software standby, 1: streaming', []),
    ('CSI_LANE_MODE', 0x0114, 1, 'CSI-2 lane count: 1: 2 lanes, 3: 4 lanes', []),
    ('DPHY_CTRL', 0x0128, 1, 'D-PHY timing: 0: automatic, 1: manual', []),
    (
        'EXCK_FREQ',
        0x012A,
        2,
        'External clock frequency in MHz, 8.8 fixed point',
        [
            ('INT', 15, 8, 'Integer part, MHz'),
            ('FRAC', 7, 0, 'Fractional part, 1/256 MHz'),
        ],
    ),
    # Gain and exposure
    ('ANALOG_GAIN', 0x0157, 1, 'Analog gain, 0-232', []),
    (
        'DIGITAL_GAIN',
        0x0158,
        2,
        'Digital gain, 0x0100-0x0fff',
        [
            ('GAIN', 11, 0, 'Gain in 1/256 steps, 0x100 = 1x'),
        ],
    ),
    ('EXPOSURE', 0x015A, 2, 'Coarse integration time in lines, 4 to FRM_LENGTH_A - 4', []),
    # Frame bank A: timing, cropping and output size
    (
        'FRM_LENGTH_A',
        0x0160,
        2,
        'Frame length in lines (height + vertical blanking), 0xfffe max',
        [],
    ),
    (
        'LINE_LENGTH_A',
        0x0162,
        2,
        'Line length in pixels (width + horizontal blanking), 0x0d78-0x7ff0; 0x0de8 min when binned',
        [],
    ),
    ('X_ADD_STA_A', 0x0164, 2, 'Crop start X, relative to the 3280x2464 active area', []),
    ('X_ADD_END_A', 0x0166, 2, 'Crop end X, inclusive', []),
    ('Y_ADD_STA_A', 0x0168, 2, 'Crop start Y, relative to the 3280x2464 active area', []),
    ('Y_ADD_END_A', 0x016A, 2, 'Crop end Y, inclusive', []),
    ('X_OUTPUT_SIZE', 0x016C, 2, 'Output image width in pixels', []),
    ('Y_OUTPUT_SIZE', 0x016E, 2, 'Output image height in pixels', []),
    ('X_ODD_INC_A', 0x0170, 1, 'X odd pixel increment (subsampling); the driver writes 1', []),
    ('Y_ODD_INC_A', 0x0171, 1, 'Y odd pixel increment (subsampling); the driver writes 1', []),
    (
        'ORIENTATION',
        0x0172,
        1,
        'Image flip; flipping changes the Bayer order',
        [
            ('HFLIP', 0, 0, 'Horizontal flip'),
            ('VFLIP', 1, 1, 'Vertical flip'),
        ],
    ),
    ('BINNING_MODE_H', 0x0174, 1, 'Horizontal binning: 0: none, 1: x2, 3: x2 analog', []),
    ('BINNING_MODE_V', 0x0175, 1, 'Vertical binning: 0: none, 1: x2, 3: x2 analog', []),
    (
        'CSI_DATA_FORMAT_A',
        0x018C,
        2,
        'CSI-2 data format; the driver writes the bits per pixel (8 or 10) to both bytes',
        [
            ('PIXEL_BPP', 15, 8, 'Bits per pixel of the pixel data'),
            ('OUTPUT_BPP', 7, 0, 'Bits per pixel on the CSI-2 bus'),
        ],
    ),
    # PLL
    ('VTPXCK_DIV', 0x0301, 1, 'Video timing pixel clock divider; the driver writes 5', []),
    ('VTSYCK_DIV', 0x0303, 1, 'Video timing system clock divider; the driver writes 1', []),
    ('PREPLLCK_VT_DIV', 0x0304, 1, 'Video timing pre-PLL clock divider; 3: automatic', []),
    ('PREPLLCK_OP_DIV', 0x0305, 1, 'Output pre-PLL clock divider; 3: automatic', []),
    (
        'PLL_VT_MPY',
        0x0306,
        2,
        'Video timing PLL multiplier; the driver writes 57 (2 lanes) or 88 (4 lanes)',
        [],
    ),
    (
        'OPPXCK_DIV',
        0x0309,
        1,
        'Output pixel clock divider; set to the bits per pixel (8 or 10)',
        [],
    ),
    ('OPSYCK_DIV', 0x030B, 1, 'Output system clock divider; the driver writes 1', []),
    (
        'PLL_OP_MPY',
        0x030C,
        2,
        'Output PLL multiplier; the driver writes 114 (2 lanes) or 91 (4 lanes)',
        [],
    ),
    # Test pattern
    (
        'TEST_PATTERN',
        0x0600,
        2,
        (
            'Test pattern: 0: disabled, 1: solid color, 2: color bars, 3: grey color bars, 4: PN9, '
            '5: 16 split color bars, 6: 16 split inverted color bars, 7: column counter, '
            '8: inverted column counter, 9: PN31'
        ),
        [],
    ),
    ('TESTP_RED', 0x0602, 2, 'Solid color test pattern, red', [('RED', 9, 0, '0-0x3ff')]),
    (
        'TESTP_GREENR',
        0x0604,
        2,
        'Solid color test pattern, green (red row)',
        [('GREENR', 9, 0, '0-0x3ff')],
    ),
    ('TESTP_BLUE', 0x0606, 2, 'Solid color test pattern, blue', [('BLUE', 9, 0, '0-0x3ff')]),
    (
        'TESTP_GREENB',
        0x0608,
        2,
        'Solid color test pattern, green (blue row)',
        [('GREENB', 9, 0, '0-0x3ff')],
    ),
    ('TP_WINDOW_WIDTH', 0x0624, 2, 'Test pattern window width; set to the output width', []),
    ('TP_WINDOW_HEIGHT', 0x0626, 2, 'Test pattern window height; set to the output height', []),
]

# The driver knows the value of only one register: the chip ID it checks at probe.
RESET_VALUES = {
    'CHIP_ID': 0x0219,
}

# Registers the driver writes without naming them. All are 8-bit and get a
# name from their address, e.g. REG_30EB.
#
# The driver unlocks access to the 0x3000-0x5fff range at init with this
# sequence: 0x30eb = 0x05, 0x0c; 0x300a = 0xff; 0x300b = 0xff;
# 0x30eb = 0x05, 0x09. (address, description)
UNLOCK_REGS = [
    (0x300A, 'Register access unlock; the driver writes 0xff'),
    (0x300B, 'Register access unlock; the driver writes 0xff'),
    (0x30EB, 'Register access unlock; the driver writes 0x05, 0x0c, then 0x05, 0x09'),
]

# Registers the driver calls undocumented and writes once at init:
# (address, value the driver writes)
UNDOCUMENTED_REGS = [
    (0x455E, 0x00),
    (0x471E, 0x4B),
    (0x4767, 0x0F),
    (0x4750, 0x14),
    (0x4540, 0x00),
    (0x47B4, 0x14),
    (0x4713, 0x30),
    (0x478B, 0x10),
    (0x478F, 0x10),
    (0x4793, 0x10),
    (0x4797, 0x0E),
    (0x479B, 0x0E),
]


def build_regfile() -> UnpackedRegFile:
    regs = []

    for name, addr, size, desc, fields in REGS:
        regs.append(
            UnpackedRegister(
                name,
                addr,
                [UnpackedField(*f) for f in fields],
                description=desc,
                reset_value=RESET_VALUES.get(name, 0),
                data_size=size,
            )
        )

    for addr, desc in UNLOCK_REGS:
        regs.append(UnpackedRegister(f'REG_{addr:04X}', addr, description=desc))

    for addr, val in UNDOCUMENTED_REGS:
        regs.append(
            UnpackedRegister(
                f'REG_{addr:04X}',
                addr,
                description=f'Undocumented; the driver writes {val:#04x}',
            )
        )

    regs.sort(key=lambda r: r.offset)

    block = UnpackedRegBlock(
        'IMX219',
        0,
        0x10000,
        regs,
        addr_endianness=Endianness.Big,
        addr_size=2,
        data_endianness=Endianness.Big,
        data_size=1,
        description='Sony IMX219 image sensor',
    )

    return UnpackedRegFile(
        'IMX219', [block], 'Sony IMX219 image sensor, from the Linux imx219 driver'
    )


def main():
    parser = argparse.ArgumentParser(description='Generate the IMX219 register database')
    parser.add_argument(
        'output',
        nargs='?',
        default=DEFAULT_OUTPUT,
        help='output regdb file (default: imx219.regdb next to this script)',
    )
    args = parser.parse_args()

    regfile = build_regfile()

    with open(args.output, 'wb') as f:
        regfile.pack_to(f)

    nregs = sum(len(b.regs) for b in regfile.blocks)
    nfields = sum(len(r.fields) for b in regfile.blocks for r in b.regs)
    print(f'Wrote {args.output}: {nregs} registers, {nfields} fields')


if __name__ == '__main__':
    main()
