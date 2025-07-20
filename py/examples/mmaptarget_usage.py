#!/usr/bin/env python3
"""
Pyrwmem Example: MMapTarget Usage

This example demonstrates memory-mapped access to device registers using
pyrwmem's MMapTarget class. In real applications, this would typically access
hardware registers via /dev/mem, but this example uses a temporary file.
"""

import os
import tempfile
import rwmem as rw


def create_device_registers():
    """Create simulated device register data."""
    # Simulate a device register block (32 bytes, 8 registers)
    data = bytearray(32)

    # Device registers with realistic values (32-bit each)
    data[0:4] = [0x00, 0x12, 0x34, 0x56]    # DEVICE_ID register
    data[4:8] = [0x00, 0x00, 0x00, 0x01]    # STATUS register
    data[8:12] = [0x00, 0x00, 0x80, 0x00]   # CONTROL register
    data[12:16] = [0x12, 0x34, 0x56, 0x78]  # DATA register

    return data


def main():
    """Show typical device register access patterns."""
    # Note: In real usage, target would be /dev/mem with device base address

    # Create simulated device registers
    test_data = create_device_registers()
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(test_data)
        device_file = f.name

    try:
        # Map device registers (native endianness, 32-bit default)
        with rw.MMapTarget(device_file, 0, 32,
                          rw.Endianness.Default, 4,
                          rw.MapMode.ReadWrite) as device:

            print('Reading device registers:')
            device_id = device.read(0x00)
            status = device.read(0x04)
            control = device.read(0x08)
            data_reg = device.read(0x0c)

            print(f'  DEVICE_ID (0x00): 0x{device_id:08x}')
            print(f'  STATUS    (0x04): 0x{status:08x}')
            print(f'  CONTROL   (0x08): 0x{control:08x}')
            print(f'  DATA      (0x0c): 0x{data_reg:08x}')

            print('\nWriting to registers:')
            # Enable device (set bit 0 in CONTROL register)
            device.write(0x08, 0x00008001)    # No size parameter = use default
            print('  Set CONTROL to 0x00008001 (enabled)')

            # Write data register
            device.write(0x0c, 0xDEADBEEF)
            print('  Set DATA to 0xDEADBEEF')

            # Example of 16-bit access (less common but possible)
            status_low = device.read(0x04, 2)  # Read low 16 bits of STATUS
            print('\n16-bit access example:')
            print(f'  STATUS low 16 bits: 0x{status_low:04x}')

    finally:
        os.unlink(device_file)


if __name__ == '__main__':
    main()
