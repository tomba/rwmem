# Quick Start: Generating Register Databases with pyrwmem

This guide shows how to generate register database (regdb) files using the pyrwmem API. Register databases describe hardware register layouts for use with tools like `rwmem`.

## Example: Create a Register Database

```python
import rwmem as rw
import rwmem.gen as gen

def create_regdb():
    registers = [
        ('TEMP', 0x00, [
            ('TEMPERATURE', 15, 4, 'Temperature data'),
        ]),
        # ... more registers ...
    ]
    block = ('SENSOR', 0x48, 0x20, registers,
             rw.Endianness.Big, 1, rw.Endianness.Big, 2,
             'Sensor block')
    regfile = gen.create_register_file('SENSOR_REGDB', [block],
                                       description='Sensor register database')
    return regfile

# Save to file
regfile = create_regdb()
with open('/tmp/sensor.regdb', 'wb') as f:
    regfile.pack_to(f)
```

## API Overview
- **Register fields**: tuples `(name, high, low, description)` or `UnpackedField` objects
- **Registers**: tuples `(name, offset, fields)` or `UnpackedRegister` objects
- **Blocks**: tuples `(name, offset, size, registers, addr_endianness, addr_size, data_endianness, data_size, description)` or `UnpackedRegBlock` objects
- Use `gen.create_register_file(name, blocks, description)` to build the regdb
- Call `regfile.pack_to(file)` to write the binary regdb

See `py/examples/regdb_generation.py` for a full example.
