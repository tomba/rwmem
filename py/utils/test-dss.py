#!/usr/bin/env python3

import io
import time

import rwmem as rw
import rwmem.gen as gen

OVR_REGS = [
    ( 'ATTRIBUTES_0', 0x20, [
        ( 'CHANNELIN', 4, 1 ),
        ( 'ENABLE', 0, 0 ),
    ] ),
    ( 'ATTRIBUTES_1', 0x24, [
        ( 'CHANNELIN', 4, 1 ),
        ( 'ENABLE', 0, 0 ),
    ] ),
    ( 'ATTRIBUTES_2', 0x28, [
        ( 'CHANNELIN', 4, 1 ),
        ( 'ENABLE', 0, 0 ),
    ] ),
    ( 'ATTRIBUTES_3', 0x2c, [
        ( 'CHANNELIN', 4, 1 ),
        ( 'ENABLE', 0, 0 ),
    ] ),

    ( 'ATTRIBUTES2_0', 0x34, [
        ( 'POSY', 29, 16 ),
        ( 'POSX', 13, 0 ),
    ] ),
    ( 'ATTRIBUTES2_1', 0x38, [
        ( 'POSY', 29, 16 ),
        ( 'POSX', 13, 0 ),
    ] ),
    ( 'ATTRIBUTES2_2', 0x3c, [
        ( 'POSY', 29, 16 ),
        ( 'POSX', 13, 0 ),
    ] ),
    ( 'ATTRIBUTES2_3', 0x40, [
        ( 'POSY', 29, 16 ),
        ( 'POSX', 13, 0 ),
    ] ),

]

VP_REGS = [
    ( 'CONTROL', 0x4, [
        ( 'GOBIT', 5, 5 ),
        ( 'ENABLE', 0, 0 ),
    ] ),
]

plat = 'J7'

if plat == 'AM625':
    urf = gen.create_register_file(
        'DSS', [
            ( 'VP1', 0x3020a000, 0x1000, VP_REGS, rw.Endianness.Default, 4, rw.Endianness.Default, 4 ),
            ( 'VP2', 0x3020b000, 0x1000, VP_REGS, rw.Endianness.Default, 4, rw.Endianness.Default, 4 ),
            ( 'OVR2', 0x30208000, 0x1000, OVR_REGS, rw.Endianness.Default, 4, rw.Endianness.Default, 4 ),
            ( 'OVR1', 0x30207000, 0x1000, OVR_REGS, rw.Endianness.Default, 4, rw.Endianness.Default, 4 ),
        ]
    )
elif plat == 'J7':
    urf = gen.create_register_file(
        'DSS', [
            ( 'VP1', 0x04a80000, 0x10000, VP_REGS, rw.Endianness.Default, 4, rw.Endianness.Default, 4 ),
            ( 'VP2', 0x04aa0000, 0x10000, VP_REGS, rw.Endianness.Default, 4, rw.Endianness.Default, 4 ),
            ( 'VP3', 0x04ac0000, 0x10000, VP_REGS, rw.Endianness.Default, 4, rw.Endianness.Default, 4 ),
            ( 'VP4', 0x04ae0000, 0x10000, VP_REGS, rw.Endianness.Default, 4, rw.Endianness.Default, 4 ),

            ( 'OVR1', 0x04a70000, 0x1000, OVR_REGS, rw.Endianness.Default, 4, rw.Endianness.Default, 4 ),
            ( 'OVR2', 0x04a90000, 0x1000, OVR_REGS, rw.Endianness.Default, 4, rw.Endianness.Default, 4 ),
            ( 'OVR3', 0x04ab0000, 0x1000, OVR_REGS, rw.Endianness.Default, 4, rw.Endianness.Default, 4 ),
            ( 'OVR4', 0x04ad0000, 0x1000, OVR_REGS, rw.Endianness.Default, 4, rw.Endianness.Default, 4 ),
        ]
    )
else:
    raise RuntimeError()

#            <0x00 0x04a00000 0x00 0x10000>, /* common_m */
#            <0x00 0x04a10000 0x00 0x10000>, /* common_s0*/
#            <0x00 0x04b00000 0x00 0x10000>, /* common_s1*/
#            <0x00 0x04b10000 0x00 0x10000>, /* common_s2*/
#
#            <0x00 0x04a20000 0x00 0x10000>, /* vidl1 */
#            <0x00 0x04a30000 0x00 0x10000>, /* vidl2 */
#            <0x00 0x04a50000 0x00 0x10000>, /* vid1 */
#            <0x00 0x04a60000 0x00 0x10000>, /* vid2 */
#
#            <0x00 0x04a70000 0x00 0x10000>, /* ovr1 */
#            <0x00 0x04a90000 0x00 0x10000>, /* ovr2 */
#            <0x00 0x04ab0000 0x00 0x10000>, /* ovr3 */
#            <0x00 0x04ad0000 0x00 0x10000>, /* ovr4 */
#
#            <0x00 0x04a80000 0x00 0x10000>, /* vp1 */
#            <0x00 0x04aa0000 0x00 0x10000>, /* vp2 */
#            <0x00 0x04ac0000 0x00 0x10000>, /* vp3 */
#            <0x00 0x04ae0000 0x00 0x10000>, /* vp4 */
#            <0x00 0x04af0000 0x00 0x10000>; /* wb */



with io.BytesIO() as f:
    urf.pack_to(f)
    rf = rw.RegisterFile(f.getvalue())

def print_rf(rf: rw.RegisterFile):
    print('{}: blocks {}, regs {}, fields {}'.format(rf.name, rf.num_blocks, rf.num_regs, rf.num_fields))

    for rb in rf.values():
        print('{} {:#x} {:#x}'.format(rb.name, rb.offset, rb.size))
        for r in rb.values():
            print('  {} {:#x}'.format(r.name, r.offset))
            for f in r.values():
                print('    {} {}:{}'.format(f.name, f.low, f.high))

#print_rf(rf)

print('==')

mrf = rw.MappedRegisterFile(rf)

def pr_old():
    for vp_idx in range(1, 5):
        vp_name = f'VP{vp_idx}'
        if vp_name not in mrf:
            break
        vp = mrf[vp_name]

        print(f'{vp_name} enable={vp["CONTROL"]["ENABLE"]}')

        ovr_name = f'OVR{vp_idx}'
        if ovr_name not in mrf:
            break
        ovr = mrf[ovr_name]

        print(f'  {ovr_name}')

        for ovr_attr_idx in range(0, 4):
            ovr_attrs_name = f'ATTRIBUTES_{ovr_attr_idx}'
            reg = ovr[ovr_attrs_name]
            print(f'    {ovr_attrs_name} enable={reg["ENABLE"]} channelin={reg["CHANNELIN"]} posx={reg["POSX"]} posy={reg["POSY"]}')

print('==')

def pr():
    for rb in mrf.values():
        print(rb._regblock.name)

        for r in rb.values():
            print(f'  {r._reg.name}:', end='')

            for fname, fval in r.get_fields().items():
                field_info = r._reg[fname]

                print(f' {fname}=', end='')
                if field_info.high == field_info.low:
                    print(f'{fval}', end='')
                else:
                    print(f'{fval:#x}', end='')

            print()

pr()

mrf['OVR2']['ATTRIBUTES_0']['CHANNELIN']=0
time.sleep(1)
mrf['OVR2']['ATTRIBUTES_1']['CHANNELIN']=3
#mrf.VP2.CONTROL.GOBIT=1
