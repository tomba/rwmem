#!/usr/bin/env python3

import argparse
import rwmem as rw
import rwmem.helpers as rwh
import tabulate
tabulate.PRESERVE_WHITESPACE = True


def format_endianness_brief(endianness):
    """Format endianness for brief display"""
    if endianness == rw.Endianness.Little:
        return 'le'
    elif endianness == rw.Endianness.Big:
        return 'be'
    elif endianness == rw.Endianness.LittleSwapped:
        return 'les'
    elif endianness == rw.Endianness.BigSwapped:
        return 'bes'
    else:
        return endianness.name

parser = argparse.ArgumentParser()
parser.add_argument('regfile')
parser.add_argument('--no-regs', '-R', action='store_true', help='Skip register display')
parser.add_argument('--no-fields', '-F', action='store_true', help='Skip field display')
parser.add_argument('--descriptions', '-d', action='store_true', help='Show descriptions')
args = parser.parse_args()

rf = rw.RegisterFile(args.regfile)
print('RegisterFile {}: blocks {}, regs {}, fields {}'.format(rf.name, rf.num_blocks, rf.num_regs, rf.num_fields))
print()

table = []

rf:rw.RegisterFile

for name,rb in rf.items():
    name:str
    rb:rw.RegisterBlock

    # Block row
    block_desc = rb.description if args.descriptions and rb.description else ''

    if args.descriptions:
        table.append(( name, hex(rb.offset), hex(rb.size),
                      f'{rb.data_size * 8}/{format_endianness_brief(rb.data_endianness)}',
                      f'{rb.addr_size * 8}/{format_endianness_brief(rb.addr_endianness)}',
                      '', '', block_desc ))
    else:
        table.append(( name, hex(rb.offset), hex(rb.size),
                      f'{rb.data_size * 8}/{format_endianness_brief(rb.data_endianness)}',
                      f'{rb.addr_size * 8}/{format_endianness_brief(rb.addr_endianness)}',
                      '', '' ))

    if not args.no_regs:
        for reg_name, r in rb.items():
            # Show register with its effective size/endianness and other v3 features
            reg_name_display = '    ' + r.name
            reg_desc = r.description if args.descriptions and r.description else ''

            # Build size/endianness info - show if different from block defaults
            reg_data_info = ''
            reg_addr_info = ''

            if (r.effective_data_size != rb.data_size or
                r.effective_data_endianness != rb.data_endianness):
                reg_data_info = f'{r.effective_data_size * 8}/{format_endianness_brief(r.effective_data_endianness)}'

            if (r.effective_addr_size != rb.addr_size or
                r.effective_addr_endianness != rb.addr_endianness):
                reg_addr_info = f'{r.effective_addr_size * 8}/{format_endianness_brief(r.effective_addr_endianness)}'

            # Build reset column
            reset_col = hex(r.reset_value) if r.reset_value != 0 else ''

            if args.descriptions:
                table.append(( reg_name_display, hex(r.offset), hex(r.effective_data_size * 8),
                              reg_data_info, reg_addr_info, reset_col, reg_desc ))
            else:
                table.append(( reg_name_display, hex(r.offset), hex(r.effective_data_size * 8),
                              reg_data_info, reg_addr_info, reset_col ))

            if not args.no_fields:
                for field_name, f in r.items():
                    field_name_display = '        ' + f.name
                    field_desc = f.description if args.descriptions and f.description else ''

                    # Extract field reset value from register reset_value if register has one
                    field_reset_col = ''
                    if r.reset_value != 0:
                        field_value = rwh.get_field_value(r.reset_value, f.high, f.low)
                        field_reset_col = hex(field_value)

                    if args.descriptions:
                        table.append(( field_name_display, f'{f.high}:{f.low}',
                                      f.high - f.low + 1, '', '', field_reset_col, field_desc ))
                    else:
                        table.append(( field_name_display, f'{f.high}:{f.low}',
                                      f.high - f.low + 1, '', '', field_reset_col ))


if args.descriptions:
    print(tabulate.tabulate(table, ['Name', 'Offset', 'Size', 'Data', 'Addr', 'Reset', 'Description'],
                          colalign=('left', 'right', 'right', 'left', 'left', 'right', 'left')))
else:
    print(tabulate.tabulate(table, ['Name', 'Offset', 'Size', 'Data', 'Addr', 'Reset'],
                          colalign=('left', 'right', 'right', 'left', 'left', 'right')))
