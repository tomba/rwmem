#!/usr/bin/env python3

import argparse
import rwmem as rw
import tabulate
tabulate.PRESERVE_WHITESPACE = True

parser = argparse.ArgumentParser()
parser.add_argument('regfile')
parser.add_argument('--no-regs', action='store_true')
parser.add_argument('--no-fields', action='store_true')
args = parser.parse_args()

rf = rw.RegisterFile(args.regfile)
print('RegisterFile {}: blocks {}, regs {}, fields {}'.format(rf.name, rf.num_blocks, rf.num_regs, rf.num_fields))
print()

table = []

rf:rw.RegisterFile

for name,rb in rf.items():
    name:str
    rb:rw.RegisterBlock

    table.append(( name, hex(rb.offset), hex(rb.size),
                  f'{rb.data_size}/{rb.data_endianness.name}',
                  f'{rb.addr_size}/{rb.addr_endianness.name}',
                  ))

    if not args.no_regs:
        for reg_name, r in rb.items():
            table.append(( '    ' + r.name, hex(r.offset), hex(rb.data_size) ))

            if not args.no_fields:
                for field_name, f in r.items():
                    table.append(( '        ' + f.name, f'{f.high}:{f.low}', f.high - f.low + 1 ))


print(tabulate.tabulate(table, ['Name', 'Offset', 'Size', 'Data', 'Addr'], colalign=('left', 'right', 'right')))
