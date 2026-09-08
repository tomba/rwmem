"""Widgets for rwmem-tui: the register tree, the detail panel and the dialogs."""

from __future__ import annotations

from dataclasses import dataclass

from rich.console import Group, RenderableType
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Input, Label, Static, Tree
from textual.widgets.tree import TreeNode

from rwmem.gen import UnpackedField, UnpackedRegBlock

from .model import Model, field_value, format_value
from .session import RegRef

FIELD_STYLES = [
    'cyan',
    'magenta',
    'green',
    'yellow',
    'blue',
    'red',
    'bright_cyan',
    'bright_magenta',
]


@dataclass
class BlockNode:
    block: UnpackedRegBlock


@dataclass
class RegNode:
    ref: RegRef


@dataclass
class FieldNode:
    ref: RegRef
    field: UnpackedField


NodeData = BlockNode | RegNode | FieldNode | None


def bits_str(field: UnpackedField) -> str:
    if field.high == field.low:
        return str(field.low)
    return f'{field.high}:{field.low}'


class RegisterTree(Tree[NodeData]):
    """Blocks, registers and fields. Register and field labels carry the last value read."""

    def __init__(self, model: Model) -> None:
        super().__init__(model.regfile.name, id='reg-tree')
        self.model = model
        self._block_nodes: dict[str, TreeNode[NodeData]] = {}
        self._reg_nodes: dict[tuple[str, str], TreeNode[NodeData]] = {}

    def on_mount(self) -> None:
        self.build()

    def build(self) -> None:
        self.root.remove_children()
        self._block_nodes.clear()
        self._reg_nodes.clear()

        for block in self.model.regfile.blocks:
            bnode = self.root.add(self.block_label(block), data=BlockNode(block), expand=True)
            self._block_nodes[block.name] = bnode
            for reg in block.regs:
                ref = self.model.ref(block, reg)
                if reg.fields:
                    rnode = bnode.add(self.reg_label(ref), data=RegNode(ref), expand=False)
                    for field in reg.fields:
                        rnode.add_leaf(self.field_label(ref, field), data=FieldNode(ref, field))
                else:
                    rnode = bnode.add_leaf(self.reg_label(ref), data=RegNode(ref))
                self._reg_nodes[ref.key] = rnode

        self.root.expand()

    # --- labels ---------------------------------------------------------

    def block_label(self, block: UnpackedRegBlock) -> Text:
        base = self.model.bases[block.name]
        t = Text.assemble((block.name, 'bold'), (f'  {base:#x}', 'dim'))
        if base != block.offset:
            t.append(f'  (regdb {block.offset:#x})', 'dim italic')
        if self.model.watch_all or block.name in self.model.watched_blocks:
            t.append('  [poll]', 'yellow')
        return t

    def reg_label(self, ref: RegRef) -> Text:
        st = self.model.state(ref)
        t = Text.assemble((ref.reg.name, 'bold'), (f'  {ref.reg.offset:#06x}', 'dim'))
        if st.error:
            t.append('  ' + st.error, 'red')
        elif st.value is not None:
            style = 'bold yellow' if st.changed else 'green'
            t.append('  = ' + format_value(st.value, self.model.fmt, ref.bits), style)
        if ref.key in self.model.watched_regs:
            t.append('  [poll]', 'yellow')
        return t

    def field_label(self, ref: RegRef, field: UnpackedField) -> Text:
        st = self.model.state(ref)
        t = Text.assemble(field.name, (f'  [{bits_str(field)}]', 'dim'))
        if st.value is not None:
            style = 'bold yellow' if st.changed else 'green'
            width = field.high - field.low + 1
            t.append(
                '  = ' + format_value(field_value(st.value, field), self.model.fmt, width), style
            )
        return t

    # --- updates --------------------------------------------------------

    def refresh_reg(self, ref: RegRef) -> None:
        node = self._reg_nodes.get(ref.key)
        if node is None:
            return
        node.set_label(self.reg_label(ref))
        for child in node.children:
            if isinstance(child.data, FieldNode):
                child.set_label(self.field_label(ref, child.data.field))

    def refresh_block(self, block: UnpackedRegBlock) -> None:
        node = self._block_nodes.get(block.name)
        if node is not None:
            node.set_label(self.block_label(block))

    def refresh_all(self) -> None:
        for block in self.model.regfile.blocks:
            self.refresh_block(block)
        for ref in self.model.refs.values():
            self.refresh_reg(ref)


class DetailPanel(VerticalScroll):
    """Context-sensitive details for the selected tree node."""

    def __init__(self, model: Model, session_description: str) -> None:
        super().__init__(id='detail-panel')
        self.model = model
        self.session_description = session_description

    def compose(self) -> ComposeResult:
        yield Static(id='detail')

    def show(self, data: NodeData) -> None:
        if isinstance(data, RegNode):
            r = self.render_reg(data.ref, None)
        elif isinstance(data, FieldNode):
            r = self.render_reg(data.ref, data.field)
        elif isinstance(data, BlockNode):
            r = self.render_block(data.block)
        else:
            r = self.render_root()
        self.query_one('#detail', Static).update(r)

    def render_reg(self, ref: RegRef, selected: UnpackedField | None) -> RenderableType:
        st = self.model.state(ref)
        bits = ref.bits
        fields = ref.reg.fields
        style_of = {f.name: FIELD_STYLES[i % len(FIELD_STYLES)] for i, f in enumerate(fields)}

        head = Text.assemble(
            (f'{ref.block.name}.{ref.reg.name}', 'bold'),
            (f'   {ref.addr:#x}   {bits}-bit {ref.data_endianness.name.lower()}', 'dim'),
        )

        if st.error:
            value_line = Text(f'error: {st.error}', 'red')
        elif st.value is None:
            value_line = Text('not read (press r)', 'dim')
        else:
            v = st.value
            value_line = Text.assemble(
                ('value  ', 'dim'),
                (f'0x{v:0{(bits + 3) // 4}x}', 'bold green'),
                f'   {v}   ',
                (f'0b{v:0{bits}b}', 'dim'),
            )

        # Bit layout: a ruler of bit numbers and the bits coloured by field.
        owner: list[UnpackedField | None] = [None] * bits
        for f in fields:
            for b in range(f.low, f.high + 1):
                if b < bits:
                    owner[b] = f

        ruler = Text()
        bitline = Text()
        for b in range(bits - 1, -1, -1):
            if b % 4 == 3:
                ruler.append(f'{b:<4} ', 'dim')
            f = owner[b]
            style = style_of[f.name] if f else 'dim'
            if selected is not None:
                style = f'bold {style}' if f is selected else 'dim'
            ch = '.' if st.value is None else str((st.value >> b) & 1)
            bitline.append(ch, style)
            if b % 4 == 0 and b:
                bitline.append(' ')

        table = Table(box=None, pad_edge=False, show_header=True, header_style='dim')
        table.add_column('bits', justify='right')
        table.add_column('field')
        table.add_column('hex', justify='right')
        table.add_column('dec', justify='right')
        table.add_column('bin', justify='right')
        for f in fields:
            style = style_of[f.name]
            if selected is not None and f is selected:
                style = f'bold reverse {style}'
            width = f.high - f.low + 1
            if st.value is None:
                hx = dec = bn = '-'
            else:
                fv = field_value(st.value, f)
                hx = f'0x{fv:0{(width + 3) // 4}x}'
                dec = str(fv)
                bn = f'0b{fv:0{width}b}'
            table.add_row(bits_str(f), f.name, hx, dec, bn, style=style)

        parts: list[RenderableType] = [head, value_line, Text(), ruler, bitline, Text()]
        if fields:
            parts.append(table)
        else:
            parts.append(Text('no fields', 'dim'))
        desc = selected.description if selected is not None else ref.reg.description
        if desc:
            parts.extend([Text(), Text(desc)])
        return Group(*parts)

    def render_block(self, block: UnpackedRegBlock) -> RenderableType:
        refs = self.model.refs_in(block)
        read = sum(1 for r in refs if self.model.state(r).value is not None)
        errors = sum(1 for r in refs if self.model.state(r).error)

        base = self.model.bases[block.name]
        t = Text()
        t.append(block.name, 'bold')
        t.append('\n\n')
        t.append(f'address     {base:#x}\n')
        if base != block.offset:
            t.append(f'regdb       {block.offset:#x} (overridden)\n')
        t.append(f'size        {block.size:#x}\n')
        t.append(f'data        {block.data_size * 8}-bit {block.data_endianness.name.lower()}\n')
        t.append(f'address     {block.addr_size * 8}-bit {block.addr_endianness.name.lower()}\n')
        t.append(f'registers   {len(refs)}, {read} read, {errors} errors\n')
        if block.description:
            t.append('\n' + block.description)
        return t

    def render_root(self) -> RenderableType:
        rf = self.model.regfile
        nregs = sum(len(b.regs) for b in rf.blocks)
        nfields = sum(len(r.fields) for b in rf.blocks for r in b.regs)

        t = Text()
        t.append(rf.name, 'bold')
        t.append('\n\n')
        t.append(f'target      {self.session_description}\n')
        t.append(f'blocks      {len(rf.blocks)}\n')
        t.append(f'registers   {nregs}\n')
        t.append(f'fields      {nfields}\n')
        t.append('\n')
        t.append('keys\n', 'dim')
        for key, what in (
            ('r', 'read the selected register, block, or everything'),
            ('w', 'write the selected register or field'),
            ('p', 'toggle polling of the selected register, block, or everything'),
            ('P', 'set the poll interval'),
            ('f', 'cycle value format: hex, dec, bin'),
            ('q', 'quit'),
        ):
            t.append(f'  {key}  ', 'bold')
            t.append(what + '\n')
        return t


class ValueScreen(ModalScreen[int | None]):
    """Ask for an integer value; used for writes."""

    DEFAULT_CSS = """
    ValueScreen { align: center middle; }
    ValueScreen > Vertical {
        width: 64; height: auto; border: thick $accent; background: $surface; padding: 1 2;
    }
    ValueScreen Label { margin-bottom: 1; }
    ValueScreen #error { color: $error; margin-top: 1; margin-bottom: 0; }
    """
    BINDINGS = [('escape', 'cancel', 'Cancel')]

    def __init__(self, title: str, current: str, max_value: int) -> None:
        super().__init__()
        self.title_text = title
        self.current = current
        self.max_value = max_value

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self.title_text)
            yield Label(self.current)
            yield Input(placeholder='new value, e.g. 0x10 or 16', id='value')
            yield Label('', id='error')

    def on_input_submitted(self, event: Input.Submitted) -> None:
        try:
            value = int(event.value.strip(), 0)
        except ValueError:
            self.query_one('#error', Label).update('not a number')
            return
        if not 0 <= value <= self.max_value:
            self.query_one('#error', Label).update(f'value must be 0..{self.max_value:#x}')
            return
        self.dismiss(value)

    def action_cancel(self) -> None:
        self.dismiss(None)


class IntervalScreen(ModalScreen[float | None]):
    """Ask for the poll interval in seconds; 0 disables polling."""

    DEFAULT_CSS = """
    IntervalScreen { align: center middle; }
    IntervalScreen > Vertical {
        width: 48; height: auto; border: thick $accent; background: $surface; padding: 1 2;
    }
    IntervalScreen Label { margin-bottom: 1; }
    IntervalScreen #error { color: $error; margin-top: 1; margin-bottom: 0; }
    """
    BINDINGS = [('escape', 'cancel', 'Cancel')]

    def __init__(self, current: float) -> None:
        super().__init__()
        self.current = current

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f'Poll interval (seconds, 0 disables), now {self.current}')
            yield Input(value=str(self.current), id='value')
            yield Label('', id='error')

    def on_input_submitted(self, event: Input.Submitted) -> None:
        try:
            value = float(event.value.strip())
        except ValueError:
            self.query_one('#error', Label).update('not a number')
            return
        if value < 0:
            self.query_one('#error', Label).update('must be >= 0')
            return
        self.dismiss(value)

    def action_cancel(self) -> None:
        self.dismiss(None)
