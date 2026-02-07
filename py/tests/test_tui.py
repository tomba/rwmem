"""Tests for rwmem-tui."""

from __future__ import annotations

import os
import tempfile
import unittest

import pytest

from rwmem.enums import Endianness
from rwmem.gen import UnpackedField, UnpackedRegBlock, UnpackedRegFile, UnpackedRegister


def _create_test_regdb_path() -> str:
    """Create a temporary .regdb file and return its path."""
    field1 = UnpackedField('ENABLE', 0, 0)
    field2 = UnpackedField('MODE', 3, 1)
    reg1 = UnpackedRegister('STATUS', 0x00, fields=[field1, field2])
    reg2 = UnpackedRegister('CONFIG', 0x04, fields=[])
    block = UnpackedRegBlock(
        name='BLOCK_A',
        offset=0x0,
        size=0x100,
        regs=[reg1, reg2],
        addr_endianness=Endianness.Little,
        addr_size=1,
        data_endianness=Endianness.Little,
        data_size=4,
    )
    regfile = UnpackedRegFile(name='TEST_TUI', blocks=[block])
    fd, path = tempfile.mkstemp(suffix='.regdb')
    with os.fdopen(fd, 'wb') as f:
        regfile.pack_to(f)
    return path


class CliTests(unittest.TestCase):
    def test_parse_args_mmap(self):
        from rwmem.tui.cli import parse_args

        args = parse_args(['mmap'])
        self.assertEqual(args.mode, 'mmap')
        self.assertEqual(args.file, '/dev/mem')
        self.assertIsNone(args.regdb)

    def test_parse_args_mmap_with_file(self):
        from rwmem.tui.cli import parse_args

        args = parse_args(['mmap', '/dev/zero'])
        self.assertEqual(args.file, '/dev/zero')

    def test_parse_args_mmap_with_regdb(self):
        from rwmem.tui.cli import parse_args

        args = parse_args(['-r', 'test.regdb', 'mmap'])
        self.assertEqual(args.regdb, 'test.regdb')

    def test_parse_args_i2c(self):
        from rwmem.tui.cli import parse_args

        args = parse_args(['i2c', '1:0x48'])
        self.assertEqual(args.mode, 'i2c')
        self.assertEqual(args.bus_addr, '1:0x48')

    def test_parse_i2c_bus_addr(self):
        from rwmem.tui.cli import parse_i2c_bus_addr

        bus, addr = parse_i2c_bus_addr('1:0x48')
        self.assertEqual(bus, 1)
        self.assertEqual(addr, 0x48)

    def test_parse_i2c_bus_addr_decimal(self):
        from rwmem.tui.cli import parse_i2c_bus_addr

        bus, addr = parse_i2c_bus_addr('2:72')
        self.assertEqual(bus, 2)
        self.assertEqual(addr, 72)


class AppStateTests(unittest.TestCase):
    def test_format_value_hex(self):
        from rwmem.tui.types import ValueFormat, format_value

        self.assertEqual(format_value(0xFF, ValueFormat.HEX, 8), '0xFF')
        self.assertEqual(format_value(0x1234, ValueFormat.HEX, 16), '0x1234')
        self.assertEqual(format_value(0, ValueFormat.HEX, 32), '0x00000000')

    def test_format_value_dec(self):
        from rwmem.tui.types import ValueFormat, format_value

        self.assertEqual(format_value(255, ValueFormat.DEC, 8), '255')
        self.assertEqual(format_value(0, ValueFormat.DEC, 32), '0')

    def test_format_value_bin(self):
        from rwmem.tui.types import ValueFormat, format_value

        self.assertEqual(format_value(5, ValueFormat.BIN, 8), '0b00000101')
        self.assertEqual(format_value(0, ValueFormat.BIN, 4), '0b0000')


@pytest.mark.asyncio
async def test_app_starts_without_regdb():
    from rwmem.tui.app import RwmemTuiApp

    app = RwmemTuiApp(target_mode='mmap', mmap_file='/dev/zero')
    async with app.run_test() as _pilot:
        tree = app.query_one('#reg-tree')
        assert tree is not None


@pytest.mark.asyncio
async def test_app_starts_with_regdb():
    from rwmem.tui.app import RwmemTuiApp

    path = _create_test_regdb_path()
    try:
        app = RwmemTuiApp(target_mode='mmap', mmap_file='/dev/zero', regdb_path=path)
        async with app.run_test() as _pilot:
            tree = app.query_one('#reg-tree')
            assert tree is not None
            assert app.state.regfile is not None
            assert len(app.state.regfile.blocks) == 1
            assert app.state.regfile.blocks[0].name == 'BLOCK_A'
    finally:
        os.unlink(path)


@pytest.mark.asyncio
async def test_format_cycling():
    from rwmem.tui.app import RwmemTuiApp, ValueFormat

    app = RwmemTuiApp(target_mode='mmap', mmap_file='/dev/zero')
    async with app.run_test() as pilot:
        assert app.state.value_format == ValueFormat.HEX
        await pilot.press('f')
        assert app.state.value_format == ValueFormat.DEC
        await pilot.press('f')
        assert app.state.value_format == ValueFormat.BIN
        await pilot.press('f')
        assert app.state.value_format == ValueFormat.HEX


if __name__ == '__main__':
    unittest.main()
