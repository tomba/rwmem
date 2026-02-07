"""Right-pane detail/display widgets for rwmem-tui."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static

from rwmem.gen import UnpackedField, UnpackedRegBlock, UnpackedRegister
from rwmem.helpers import get_field_value

from .state import AppState, BlockState
from .types import FIELD_COLORS, ValueFormat, format_value


class BitDiagram(Static):
    """Renders a bit diagram for a register value."""

    def __init__(self, **kwargs) -> None:
        super().__init__('', **kwargs)
        self._block: UnpackedRegBlock | None = None
        self._reg: UnpackedRegister | None = None
        self._value: int | None = None
        self._error: str | None = None
        self._highlight_field: UnpackedField | None = None

    def set_register(
        self,
        block: UnpackedRegBlock,
        reg: UnpackedRegister,
        value: int | None,
        error: str | None,
        highlight_field: UnpackedField | None = None,
    ) -> None:
        self._block = block
        self._reg = reg
        self._value = value
        self._error = error
        self._highlight_field = highlight_field
        self._refresh_content()

    def clear_display(self) -> None:
        self._block = None
        self._reg = None
        self._value = None
        self._error = None
        self._highlight_field = None
        self.update('')

    def _refresh_content(self) -> None:
        if self._reg is None or self._block is None:
            self.update('')
            return

        reg = self._reg
        block = self._block
        data_size = reg.get_effective_data_size(block.data_size)
        total_bits = data_size * 8
        value = self._value
        hl = self._highlight_field

        # Build field map: bit_index -> (field, color_index)
        field_map: dict[int, tuple[UnpackedField, int]] = {}
        for i, field in enumerate(reg.fields):
            color_idx = i % len(FIELD_COLORS)
            for bit in range(field.low, field.high + 1):
                field_map[bit] = (field, color_idx)

        lines = []
        # Header
        abs_addr = block.offset + reg.offset
        lines.append(
            f'[bold]{reg.name}[/bold] @ 0x{abs_addr:X}  '
            f'({data_size} byte{"s" if data_size > 1 else ""})'
        )

        if self._error:
            lines.append(f'[red]Read error: {self._error}[/red]')
        elif value is None:
            lines.append('[dim]No value read yet[/dim]')

        lines.append('')

        # Render 16 bits per row, MSB first
        bits_per_row = 16
        for row_start_bit in range(total_bits - 1, -1, -bits_per_row):
            row_end_bit = max(row_start_bit - bits_per_row + 1, 0)

            # Bit number header
            hdr = ''
            for bit in range(row_start_bit, row_end_bit - 1, -1):
                hdr += f'{bit:>4}'
            lines.append(f'[dim]{hdr}[/dim]')

            # Bit values
            vals = ''
            for bit in range(row_start_bit, row_end_bit - 1, -1):
                if value is not None:
                    bv = (value >> bit) & 1
                else:
                    bv = '-'
                if bit in field_map:
                    fld, cidx = field_map[bit]
                    if hl is not None and fld is not hl:
                        # Dim non-highlighted fields
                        vals += f'[dim]{bv:>4}[/dim]'
                    else:
                        color = FIELD_COLORS[cidx]
                        vals += f'[{color}]{bv:>4}[/{color}]'
                else:
                    vals += f'[dim]{bv:>4}[/dim]'
            lines.append(vals)

            # Field name labels
            labels = ''
            bit = row_start_bit
            while bit >= row_end_bit:
                if bit in field_map:
                    field, cidx = field_map[bit]
                    # Find span of this field in this row
                    span_high = bit
                    span_low = bit
                    while (
                        span_low - 1 >= row_end_bit
                        and (span_low - 1) in field_map
                        and field_map[span_low - 1][0] is field
                    ):
                        span_low -= 1
                    span_width = span_high - span_low + 1
                    char_width = span_width * 4
                    name = field.name
                    if len(name) > char_width:
                        name = name[: char_width - 1] + '~'
                    if hl is not None and field is not hl:
                        labels += f'[dim]{name:^{char_width}}[/dim]'
                    else:
                        color = FIELD_COLORS[cidx]
                        labels += f'[{color}]{name:^{char_width}}[/{color}]'
                    bit = span_low - 1
                else:
                    labels += '    '
                    bit -= 1
            lines.append(labels)
            lines.append('')

        self.update('\n'.join(lines))


class FieldTable(Static):
    """Renders the field table for a register."""

    def __init__(self) -> None:
        super().__init__('', id='field-table')
        self._block: UnpackedRegBlock | None = None
        self._reg: UnpackedRegister | None = None
        self._value: int | None = None
        self._fmt: ValueFormat = ValueFormat.HEX

    def set_register(
        self, block: UnpackedRegBlock, reg: UnpackedRegister, value: int | None, fmt: ValueFormat
    ) -> None:
        self._block = block
        self._reg = reg
        self._value = value
        self._fmt = fmt
        self._refresh_content()

    def clear_display(self) -> None:
        self._block = None
        self._reg = None
        self._value = None
        self.update('')

    def _refresh_content(self) -> None:
        if self._reg is None or self._block is None:
            self.update('')
            return

        reg = self._reg

        if not reg.fields:
            self.update('[dim]No fields defined[/dim]')
            return

        # Compute column widths
        name_w = max(len('Name'), *(len(f.name) for f in reg.fields))
        bits_w = max(len('Bits'), *(len(f'{f.high}:{f.low}') for f in reg.fields))

        # Build header
        hdr = f'{"Name":<{name_w}}  {"Bits":>{bits_w}}  Value'
        lines = [f'[bold]{hdr}[/bold]', '─' * len(hdr)]

        # Sort fields by high bit descending
        sorted_fields = sorted(reg.fields, key=lambda f: f.high, reverse=True)

        for field in sorted_fields:
            bits_str = f'{field.high}:{field.low}'
            if self._value is not None:
                fv = get_field_value(self._value, field.high, field.low)
                field_bits = field.high - field.low + 1
                val_str = format_value(fv, self._fmt, field_bits)
            else:
                val_str = '-'
            color = FIELD_COLORS[reg.fields.index(field) % len(FIELD_COLORS)]
            lines.append(
                f'[{color}]{field.name:<{name_w}}[/{color}]  {bits_str:>{bits_w}}  {val_str}'
            )

        self.update('\n'.join(lines))


class FieldDetailWidget(Static):
    """Detail view for a selected field: highlighted bit diagram + multi-format value."""

    def __init__(self) -> None:
        super().__init__('', id='field-detail')

    def set_field(
        self,
        block: UnpackedRegBlock,
        reg: UnpackedRegister,
        field: UnpackedField,
        value: int | None,
        error: str | None,
    ) -> None:
        lines: list[str] = []

        data_size = reg.get_effective_data_size(block.data_size)
        total_bits = data_size * 8

        # Header
        abs_addr = block.offset + reg.offset
        lines.append(
            f'[bold]{field.name}[/bold] [{field.high}:{field.low}]  in {reg.name} @ 0x{abs_addr:X}'
        )

        if error:
            lines.append(f'[red]Read error: {error}[/red]')
        elif value is None:
            lines.append('[dim]No value read yet[/dim]')

        lines.append('')

        # Build field map for the whole register
        field_map: dict[int, tuple[UnpackedField, int]] = {}
        for i, f in enumerate(reg.fields):
            cidx = i % len(FIELD_COLORS)
            for bit in range(f.low, f.high + 1):
                field_map[bit] = (f, cidx)

        # Bit diagram with highlight
        bits_per_row = 16
        for row_start_bit in range(total_bits - 1, -1, -bits_per_row):
            row_end_bit = max(row_start_bit - bits_per_row + 1, 0)

            hdr = ''
            for bit in range(row_start_bit, row_end_bit - 1, -1):
                hdr += f'{bit:>4}'
            lines.append(f'[dim]{hdr}[/dim]')

            vals = ''
            for bit in range(row_start_bit, row_end_bit - 1, -1):
                if value is not None:
                    bv = (value >> bit) & 1
                else:
                    bv = '-'
                if bit in field_map:
                    fld, cidx = field_map[bit]
                    if fld is field:
                        color = FIELD_COLORS[cidx]
                        vals += f'[{color}]{bv:>4}[/{color}]'
                    else:
                        vals += f'[dim]{bv:>4}[/dim]'
                else:
                    vals += f'[dim]{bv:>4}[/dim]'
            lines.append(vals)

            labels = ''
            bit = row_start_bit
            while bit >= row_end_bit:
                if bit in field_map:
                    fld, cidx = field_map[bit]
                    span_high = bit
                    span_low = bit
                    while (
                        span_low - 1 >= row_end_bit
                        and (span_low - 1) in field_map
                        and field_map[span_low - 1][0] is fld
                    ):
                        span_low -= 1
                    span_width = span_high - span_low + 1
                    char_width = span_width * 4
                    name = fld.name
                    if len(name) > char_width:
                        name = name[: char_width - 1] + '~'
                    if fld is field:
                        color = FIELD_COLORS[cidx]
                        labels += f'[{color}]{name:^{char_width}}[/{color}]'
                    else:
                        labels += f'[dim]{name:^{char_width}}[/dim]'
                    bit = span_low - 1
                else:
                    labels += '    '
                    bit -= 1
            lines.append(labels)
            lines.append('')

        # Multi-format value display
        lines.append('─' * 40)
        if value is not None:
            fv = get_field_value(value, field.high, field.low)
            field_bits = field.high - field.low + 1
            lines.append(f'Hex: {format_value(fv, ValueFormat.HEX, field_bits)}')
            lines.append(f'Dec: {format_value(fv, ValueFormat.DEC, field_bits)}')
            lines.append(f'Bin: {format_value(fv, ValueFormat.BIN, field_bits)}')
        else:
            lines.append('[dim]No value read yet[/dim]')

        if field.description:
            lines.append('')
            lines.append(f'[dim]{field.description}[/dim]')

        self.update('\n'.join(lines))

    def clear_display(self) -> None:
        self.update('')


class BlockDetailWidget(Static):
    """Detail view for a selected block: metadata + live state."""

    def __init__(self) -> None:
        super().__init__('', id='block-detail')

    def set_block(self, block: UnpackedRegBlock, bstate: BlockState | None) -> None:
        lines: list[str] = []

        lines.append(f'[bold]{block.name}[/bold]')
        lines.append('')

        # Metadata
        lines.append('[bold]Metadata[/bold]')
        lines.append(f'  Offset:          0x{block.offset:X}')
        lines.append(f'  Size:            {block.size} bytes')
        lines.append(f'  Data size:       {block.data_size} bytes')
        lines.append(f'  Data endianness: {block.data_endianness.name}')
        lines.append(f'  Addr size:       {block.addr_size} bytes')
        lines.append(f'  Addr endianness: {block.addr_endianness.name}')
        if block.description:
            lines.append(f'  Description:     {block.description}')

        lines.append('')

        # Live state
        lines.append('[bold]Live State[/bold]')
        if bstate:
            total_regs = len(block.regs)
            read_count = sum(1 for r in block.regs if bstate.reg_values.get(r.name) is not None)
            err_count = sum(1 for r in block.regs if bstate.reg_errors.get(r.name) is not None)
            watch_count = sum(1 for r in block.regs if bstate.is_reg_watched(r.name))
            lines.append(f'  {read_count}/{total_regs} registers read')
            lines.append(f'  {err_count} errors')
            lines.append(f'  {watch_count} registers polling')
            if bstate.error:
                lines.append(f'  [red]Block error: {bstate.error}[/red]')
        else:
            lines.append('  [dim]No state available[/dim]')

        self.update('\n'.join(lines))

    def clear_display(self) -> None:
        self.update('')


class RootDetailWidget(Static):
    """Detail view for root node: target info + block summary."""

    def __init__(self) -> None:
        super().__init__('', id='root-detail')

    def set_root(
        self,
        state: AppState,
        target_mode: str,
        mmap_file: str | None,
        i2c_bus: int | None,
        i2c_addr: int | None,
    ) -> None:
        lines: list[str] = []

        # Target info
        lines.append('[bold]Target[/bold]')
        if target_mode == 'mmap':
            lines.append('  Type: mmap')
            lines.append(f'  File: {mmap_file}')
        elif target_mode == 'i2c':
            lines.append('  Type: i2c')
            lines.append(f'  Bus:  {i2c_bus}')
            if i2c_addr is not None:
                lines.append(f'  Addr: 0x{i2c_addr:02X}')
        lines.append(f'  Poll interval: {state.poll_interval}s')
        lines.append(f'  Regdb: {state.regdb_path or "<unsaved>"}')

        lines.append('')

        # Totals
        total_blocks = 0
        total_regs = 0
        total_fields = 0
        if state.regfile:
            total_blocks = len(state.regfile.blocks)
            for block in state.regfile.blocks:
                total_regs += len(block.regs)
                for reg in block.regs:
                    total_fields += len(reg.fields)

        lines.append('[bold]Totals[/bold]')
        lines.append(f'  Blocks:    {total_blocks}')
        lines.append(f'  Registers: {total_regs}')
        lines.append(f'  Fields:    {total_fields}')

        # Block summary table
        if state.regfile and state.regfile.blocks:
            lines.append('')
            lines.append('[bold]Blocks[/bold]')

            name_w = max(len('Name'), *(len(b.name) for b in state.regfile.blocks))
            hdr = f'  {"Name":<{name_w}}  {"Offset":>10}  {"Size":>8}  {"Regs":>4}  Status'
            lines.append(f'[bold]{hdr}[/bold]')
            lines.append('  ' + '─' * (len(hdr) - 2))

            for block in state.regfile.blocks:
                bstate = state.block_states.get(block.name)
                read_count = 0
                if bstate:
                    read_count = sum(
                        1 for r in block.regs if bstate.reg_values.get(r.name) is not None
                    )
                status = f'{read_count}/{len(block.regs)} read'
                if bstate and bstate.error:
                    status = '[red]ERR[/red]'
                lines.append(
                    f'  {block.name:<{name_w}}  0x{block.offset:>8X}  '
                    f'{block.size:>8}  {len(block.regs):>4}  {status}'
                )

        self.update('\n'.join(lines))

    def clear_display(self) -> None:
        self.update('')


class DetailPanel(VerticalScroll):
    """Right pane: switches between register, field, block, and root detail views."""

    def compose(self) -> ComposeResult:
        yield BitDiagram(id='bit-diagram')
        yield FieldTable()
        yield FieldDetailWidget()
        yield BlockDetailWidget()
        yield RootDetailWidget()

    def on_mount(self) -> None:
        self.query_one(FieldDetailWidget).display = False
        self.query_one(BlockDetailWidget).display = False
        self.query_one(RootDetailWidget).display = False

    def _show_only(self, widget_type: type) -> None:
        """Show only the specified widget type, hide all others."""
        views: list[type] = [
            BitDiagram,
            FieldTable,
            FieldDetailWidget,
            BlockDetailWidget,
            RootDetailWidget,
        ]
        for vt in views:
            self.query_one(vt).display = vt == widget_type
        # BitDiagram and FieldTable are shown together for register view
        if widget_type == BitDiagram:
            self.query_one(FieldTable).display = True

    def set_register(
        self,
        block: UnpackedRegBlock,
        reg: UnpackedRegister,
        value: int | None,
        error: str | None,
        fmt: ValueFormat,
    ) -> None:
        self._show_only(BitDiagram)
        self.query_one(BitDiagram).set_register(block, reg, value, error)
        self.query_one(FieldTable).set_register(block, reg, value, fmt)

    def set_field(
        self,
        block: UnpackedRegBlock,
        reg: UnpackedRegister,
        field: UnpackedField,
        value: int | None,
        error: str | None,
    ) -> None:
        self._show_only(FieldDetailWidget)
        self.query_one(FieldDetailWidget).set_field(block, reg, field, value, error)

    def set_block(self, block: UnpackedRegBlock, bstate: BlockState | None) -> None:
        self._show_only(BlockDetailWidget)
        self.query_one(BlockDetailWidget).set_block(block, bstate)

    def set_root(
        self,
        state: AppState,
        target_mode: str,
        mmap_file: str | None,
        i2c_bus: int | None,
        i2c_addr: int | None,
    ) -> None:
        self._show_only(RootDetailWidget)
        self.query_one(RootDetailWidget).set_root(state, target_mode, mmap_file, i2c_bus, i2c_addr)

    def clear_display(self) -> None:
        self.query_one(BitDiagram).clear_display()
        self.query_one(FieldTable).clear_display()
        self.query_one(FieldDetailWidget).clear_display()
        self.query_one(BlockDetailWidget).clear_display()
        self.query_one(RootDetailWidget).clear_display()
        # Show register view widgets by default (empty)
        self._show_only(BitDiagram)
