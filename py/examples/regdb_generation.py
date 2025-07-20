#!/usr/bin/env python3
"""
Pyrwmem Example: Register Database Generation

This example shows how to create register database files using pyrwmem's
generation API. Register databases define the structure of hardware registers
for tools like rwmem.
"""

import rwmem as rw
import rwmem.gen as gen


def create_i2c_sensor_regdb():
    """Create a register database for an I2C temperature sensor."""

    # Define registers with fields
    lm75_registers = [
        ('TEMP', 0x00, [
            ('TEMPERATURE', 15, 4, 'Temperature data'),
        ]),

        ('CONFIG', 0x02, [
            ('SHUTDOWN', 0, 0, 'Shutdown mode'),
            ('COMP_INT', 1, 1, 'Comparator/interrupt mode'),
            ('ALERT_POL', 2, 2, 'Alert polarity'),
            ('FAULT_QUEUE', 4, 3, 'Fault queue'),
            ('RESOLUTION', 6, 5, 'ADC resolution'),
        ]),

        ('THYST', 0x04, [
            ('HYSTERESIS', 15, 4, 'Hysteresis temperature'),
        ]),

        ('TOS', 0x06, [
            ('OVERTEMP', 15, 4, 'Overtemperature shutdown'),
        ]),

        # 24-bit calibration register
        gen.UnpackedRegister(
            'CALIBRATION', 0x10, [
                gen.UnpackedField('CAL_OFFSET', 23, 12, 'Temperature offset calibration'),
                gen.UnpackedField('CAL_GAIN', 11, 0, 'Temperature gain calibration'),
            ],
            description='24-bit calibration register spanning 3 I2C registers',
            data_size=3,
            reset_value=0x800000
        ),
    ]

    # Define register block (16-bit registers by default)
    sensor_block = ('LM75_SENSOR', 0x48, 0x20, lm75_registers,
                    rw.Endianness.Big, 1, rw.Endianness.Big, 2,
                    'LM75 I2C temperature sensor')

    # Create register file
    regfile = gen.create_register_file(
        'LM75_REGDB', [sensor_block],
        description='LM75 temperature sensor register database'
    )

    return regfile


def main():
    """Generate and save a register database."""
    print('Creating I2C temperature sensor register database...')

    # Create the register database
    regfile = create_i2c_sensor_regdb()

    # Save to binary format
    output_file = '/tmp/lm75_sensor.regdb'
    with open(output_file, 'wb') as f:
        regfile.pack_to(f)

    print(f'Register database saved to: {output_file}')


if __name__ == '__main__':
    main()
