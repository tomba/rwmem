"""rwmem-tui: Interactive register browser and editor."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.timer import Timer
from textual.widgets import Footer, Header

from rwmem.convert import registerfile_to_unpacked
from rwmem.enums import MapMode
from rwmem.gen import (
    UnpackedField,
    UnpackedRegBlock,
    UnpackedRegFile,
    UnpackedRegister,
)
from rwmem.i2ctarget import I2CTarget
from rwmem.mmaptarget import MMapTarget
from rwmem.registerfile import RegisterFile

from .detail import DetailPanel
from .dialogs import (
    AddBlockDialog,
    AddFieldDialog,
    AddRegisterDialog,
    ConfirmDialog,
    PollIntervalDialog,
    SaveDialog,
    WriteValueDialog,
)
from .state import AppState, BlockState
from .tree import RegisterTree
from .types import ValueFormat


class RwmemTuiApp(App):
    """Interactive register browser and editor."""

    CSS = """
    #main-container {
        height: 1fr;
    }
    #reg-tree {
        width: 1fr;
        min-width: 30;
        max-width: 50%;
        border-right: solid $accent;
    }
    #detail-panel {
        width: 2fr;
    }
    #bit-diagram {
        padding: 1;
    }
    #field-table {
        padding: 1;
    }
    #field-detail {
        padding: 1;
    }
    #block-detail {
        padding: 1;
    }
    #root-detail {
        padding: 1;
    }
    """

    BINDINGS = [
        Binding('r', 'read', 'Read', show=True),
        Binding('w', 'write', 'Write', show=True),
        Binding('ctrl+a', 'add', 'Add', show=True),
        Binding('ctrl+d', 'delete', 'Delete', show=True),
        Binding('ctrl+s', 'save', 'Save', show=True),
        Binding('p', 'poll', 'Poll', show=True),
        Binding('P', 'poll_interval', 'Poll Interval', show=True),
        Binding('f', 'format', 'Format', show=True),
        Binding('v', 'toggle_values', 'Values', show=True),
        Binding('q', 'quit', 'Quit', show=True),
    ]

    TITLE = 'rwmem-tui'

    def __init__(
        self,
        target_mode: str,
        mmap_file: str | None = None,
        i2c_bus: int | None = None,
        i2c_addr: int | None = None,
        regdb_path: str | None = None,
    ) -> None:
        super().__init__()
        self.target_mode = target_mode
        self.mmap_file = mmap_file
        self.i2c_bus = i2c_bus
        self.i2c_addr = i2c_addr

        self.state = AppState(target_mode)
        self.state.regdb_path = regdb_path

        if target_mode == 'mmap':
            self.state.target_str = f'mmap:{mmap_file}'
        elif target_mode == 'i2c':
            self.state.target_str = f'i2c:{i2c_bus}:0x{i2c_addr:02X}'

        self._selected_block: UnpackedRegBlock | None = None
        self._selected_reg: UnpackedRegister | None = None
        self._selected_field: UnpackedField | None = None
        self._poll_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id='main-container'):
            yield RegisterTree()
            yield DetailPanel(id='detail-panel')
        yield Footer()

    def on_mount(self) -> None:
        self._update_subtitle()

        if self.state.regdb_path:
            self._load_regdb(self.state.regdb_path)
        else:
            self.state.regfile = UnpackedRegFile(name='untitled', blocks=[])

        self._rebuild_tree()

    def _update_subtitle(self) -> None:
        regdb_str = self.state.regdb_path or '<unsaved>'
        self.sub_title = f'{self.state.target_str}  |  regdb: {regdb_str}'

    def _load_regdb(self, path: str) -> None:
        try:
            with RegisterFile(path) as rf:
                self.state.regfile = registerfile_to_unpacked(rf)
            self.state.regdb_path = path
            self._init_block_states()
            self._map_all_blocks()
        except Exception as e:
            self.notify(f'Failed to load regdb: {e}', severity='error')
            self.state.regfile = UnpackedRegFile(name='untitled', blocks=[])

    def _init_block_states(self) -> None:
        self.state.block_states.clear()
        if self.state.regfile:
            for block in self.state.regfile.blocks:
                self.state.block_states[block.name] = BlockState(block)

    def _map_all_blocks(self) -> None:
        if not self.state.regfile:
            return
        for block in self.state.regfile.blocks:
            self._map_block(block)

    def _map_block(self, block: UnpackedRegBlock) -> None:
        bstate = self.state.block_states.get(block.name)
        if not bstate:
            return

        if block.size <= 0:
            bstate.error = 'Block size must be positive'
            return

        try:
            if self.target_mode == 'mmap':
                assert self.mmap_file is not None
                bstate.target = MMapTarget(
                    file=self.mmap_file,
                    offset=block.offset,
                    length=block.size,
                    data_endianness=block.data_endianness,
                    data_size=block.data_size,
                    mode=MapMode.ReadWrite,
                )
            elif self.target_mode == 'i2c':
                assert self.i2c_bus is not None
                assert self.i2c_addr is not None
                bstate.target = I2CTarget(
                    i2c_adapter_nr=self.i2c_bus,
                    i2c_dev_addr=self.i2c_addr,
                    offset=block.offset,
                    length=block.size,
                    addr_endianness=block.addr_endianness,
                    addr_size=block.addr_size,
                    data_endianness=block.data_endianness,
                    data_size=block.data_size,
                    mode=MapMode.ReadWrite,
                )
            bstate.error = None
        except Exception as e:
            bstate.error = str(e)

    def _rebuild_tree(self) -> None:
        tree = self.query_one(RegisterTree)
        tree.rebuild(self.state)

    def _refresh_detail(self) -> None:
        panel = self.query_one(DetailPanel)
        if self._selected_field and self._selected_reg and self._selected_block:
            block = self._selected_block
            reg = self._selected_reg
            bstate = self.state.block_states.get(block.name)
            value = bstate.reg_values.get(reg.name) if bstate else None
            error = bstate.reg_errors.get(reg.name) if bstate else None
            panel.set_field(block, reg, self._selected_field, value, error)
        elif self._selected_reg and self._selected_block:
            block = self._selected_block
            reg = self._selected_reg
            bstate = self.state.block_states.get(block.name)
            value = bstate.reg_values.get(reg.name) if bstate else None
            error = bstate.reg_errors.get(reg.name) if bstate else None
            panel.set_register(block, reg, value, error, self.state.value_format)
        elif self._selected_block:
            bstate = self.state.block_states.get(self._selected_block.name)
            panel.set_block(self._selected_block, bstate)
        else:
            panel.set_root(
                self.state, self.target_mode, self.mmap_file, self.i2c_bus, self.i2c_addr
            )

    def _read_register(self, block: UnpackedRegBlock, reg: UnpackedRegister) -> None:
        bstate = self.state.block_states.get(block.name)
        if not bstate or not bstate.target:
            if bstate:
                bstate.reg_errors[reg.name] = bstate.error or 'No target mapped'
            return

        abs_addr = block.offset + reg.offset
        data_size = reg.get_effective_data_size(block.data_size)
        data_endianness = reg.get_effective_data_endianness(block.data_endianness)

        try:
            value = bstate.target.read(
                abs_addr,
                data_size=data_size,
                data_endianness=data_endianness,
            )
            bstate.reg_values[reg.name] = value
            bstate.reg_errors[reg.name] = None
        except Exception as e:
            bstate.reg_errors[reg.name] = str(e)

    def _write_register(self, block: UnpackedRegBlock, reg: UnpackedRegister, value: int) -> None:
        bstate = self.state.block_states.get(block.name)
        if not bstate or not bstate.target:
            self.notify('No target mapped for this block', severity='error')
            return

        abs_addr = block.offset + reg.offset
        data_size = reg.get_effective_data_size(block.data_size)
        data_endianness = reg.get_effective_data_endianness(block.data_endianness)

        try:
            bstate.target.write(
                abs_addr,
                value,
                data_size=data_size,
                data_endianness=data_endianness,
            )
            bstate.reg_values[reg.name] = value
            bstate.reg_errors[reg.name] = None
        except Exception as e:
            bstate.reg_errors[reg.name] = str(e)
            self.notify(f'Write failed: {e}', severity='error')

    # --- Event handlers ---

    def on_register_tree_register_selected(self, event: RegisterTree.RegisterSelected) -> None:
        self._selected_block = event.block
        self._selected_reg = event.reg
        self._selected_field = None
        self._read_register(event.block, event.reg)
        self._update_tree_values({(event.block.name, event.reg.name)})
        self._refresh_detail()

    def on_register_tree_block_selected(self, event: RegisterTree.BlockSelected) -> None:
        self._selected_block = event.block
        self._selected_reg = None
        self._selected_field = None
        self._refresh_detail()

    def on_register_tree_field_selected(self, event: RegisterTree.FieldSelected) -> None:
        self._selected_block = event.block
        self._selected_reg = event.reg
        self._selected_field = event.field
        self._read_register(event.block, event.reg)
        self._update_tree_values({(event.block.name, event.reg.name)})
        self._refresh_detail()

    def on_register_tree_nothing_selected(self, event: RegisterTree.NothingSelected) -> None:
        self._selected_block = None
        self._selected_reg = None
        self._selected_field = None
        self._refresh_detail()

    # --- Actions ---

    def _update_tree_values(self, changed_regs: set[tuple[str, str]] | None = None) -> None:
        """Update tree labels in-place for value changes."""
        self.query_one(RegisterTree).update_values(self.state, changed_regs)

    def action_read(self) -> None:
        if self._selected_field and self._selected_reg and self._selected_block:
            # Reading a field reads the parent register
            self._read_register(self._selected_block, self._selected_reg)
            self._update_tree_values({(self._selected_block.name, self._selected_reg.name)})
            self._refresh_detail()
        elif self._selected_reg and self._selected_block:
            self._read_register(self._selected_block, self._selected_reg)
            self._update_tree_values({(self._selected_block.name, self._selected_reg.name)})
            self._refresh_detail()
        elif self._selected_block:
            changed: set[tuple[str, str]] = set()
            for reg in self._selected_block.regs:
                self._read_register(self._selected_block, reg)
                changed.add((self._selected_block.name, reg.name))
            self._update_tree_values(changed)
            self._refresh_detail()
        else:
            self.notify('Select a register or block first', severity='warning')

    def action_write(self) -> None:
        if not self._selected_reg or not self._selected_block:
            self.notify('Select a register first', severity='warning')
            return

        block = self._selected_block
        reg = self._selected_reg
        bstate = self.state.block_states.get(block.name)
        current_value = bstate.reg_values.get(reg.name) if bstate else None

        data_size = reg.get_effective_data_size(block.data_size)
        preselect_field = self._selected_field.name if self._selected_field else None
        self.push_screen(
            WriteValueDialog(
                reg.name, current_value, data_size, reg.fields, preselect_field=preselect_field
            ),
            callback=self._on_write_dialog_result,
        )

    def _on_write_dialog_result(self, result: tuple[int, bool] | None) -> None:
        if result is None:
            return

        value, is_field_edit = result
        block = self._selected_block
        reg = self._selected_reg

        if not block or not reg:
            return

        if is_field_edit:
            # value is already the full register value with field modified
            pass

        self._write_register(block, reg, value)
        self._update_tree_values({(block.name, reg.name)})
        self._refresh_detail()

    def action_add(self) -> None:
        if not self.state.regfile:
            return

        if self._selected_reg and self._selected_block:
            # Add field to selected register
            self.push_screen(
                AddFieldDialog(),
                callback=self._on_add_field_result,
            )
        elif self._selected_block:
            # Add register to selected block
            self.push_screen(
                AddRegisterDialog(self._selected_block),
                callback=self._on_add_register_result,
            )
        else:
            # Add block
            self.push_screen(
                AddBlockDialog(self.target_mode),
                callback=self._on_add_block_result,
            )

    def _on_add_block_result(self, result: dict | None) -> None:
        if result is None or not self.state.regfile:
            return

        try:
            block = UnpackedRegBlock(
                name=result['name'],
                offset=result['offset'],
                size=result['size'],
                regs=[],
                addr_endianness=result['addr_endianness'],
                addr_size=result['addr_size'],
                data_endianness=result['data_endianness'],
                data_size=result['data_size'],
                description=result.get('description') or None,
            )
            self.state.regfile.blocks.append(block)
            self.state.block_states[block.name] = BlockState(block)
            self._map_block(block)
            self.query_one(RegisterTree).add_block_node(block, self.state)
        except Exception as e:
            self.notify(f'Failed to add block: {e}', severity='error')

    def _on_add_register_result(self, result: dict | None) -> None:
        if result is None or not self._selected_block:
            return

        block = self._selected_block

        try:
            reg = UnpackedRegister(
                name=result['name'],
                offset=result['offset'],
                fields=[],
                description=result.get('description') or None,
                data_endianness=result.get('data_endianness'),
                data_size=result.get('data_size'),
            )
            block.regs.append(reg)
            bstate = self.state.block_states.get(block.name)
            if bstate:
                bstate.reg_values[reg.name] = None
                bstate.reg_errors[reg.name] = None
            self.query_one(RegisterTree).add_register_node(block, reg, self.state)
        except Exception as e:
            self.notify(f'Failed to add register: {e}', severity='error')

    def _on_add_field_result(self, result: dict | None) -> None:
        if result is None or not self._selected_reg:
            return

        reg = self._selected_reg

        try:
            field = UnpackedField(
                name=result['name'],
                high=result['high'],
                low=result['low'],
                description=result.get('description') or None,
            )
            reg.fields.append(field)
            block = self._selected_block
            if block:
                self.query_one(RegisterTree).add_field_node(block, reg, field, self.state)
            self._refresh_detail()
        except Exception as e:
            self.notify(f'Failed to add field: {e}', severity='error')

    def action_delete(self) -> None:
        if not self.state.regfile:
            return

        if self._selected_field and self._selected_reg and self._selected_block:
            name = self._selected_field.name
            self.push_screen(
                ConfirmDialog(f'Delete field {name!r}?'),
                callback=self._on_delete_field_confirmed,
            )
        elif self._selected_reg and self._selected_block:
            name = self._selected_reg.name
            self.push_screen(
                ConfirmDialog(f'Delete register {name!r}?'),
                callback=self._on_delete_register_confirmed,
            )
        elif self._selected_block:
            name = self._selected_block.name
            self.push_screen(
                ConfirmDialog(f'Delete block {name!r}?'),
                callback=self._on_delete_block_confirmed,
            )

    def _on_delete_block_confirmed(self, confirmed: bool | None) -> None:
        if not confirmed or not self._selected_block or not self.state.regfile:
            return

        block = self._selected_block
        bstate = self.state.block_states.pop(block.name, None)
        if bstate and bstate.target:
            try:
                bstate.target.close()
            except Exception:
                pass
        self.state.regfile.blocks.remove(block)
        self._selected_block = None
        self._selected_reg = None
        self._ensure_poll_timer()
        self.query_one(RegisterTree).remove_block_node(block.name)
        self._refresh_detail()

    def _on_delete_register_confirmed(self, confirmed: bool | None) -> None:
        if not confirmed or not self._selected_reg or not self._selected_block:
            return

        block = self._selected_block
        reg = self._selected_reg
        block.regs.remove(reg)
        bstate = self.state.block_states.get(block.name)
        if bstate:
            bstate.reg_values.pop(reg.name, None)
            bstate.reg_errors.pop(reg.name, None)
            bstate.watched.discard(reg.name)
        self._selected_reg = None
        self.query_one(RegisterTree).remove_register_node(block.name, reg.name)
        self._refresh_detail()

    def _on_delete_field_confirmed(self, confirmed: bool | None) -> None:
        if not confirmed or not self._selected_field or not self._selected_reg:
            return

        reg = self._selected_reg
        field = self._selected_field
        block = self._selected_block
        reg.fields.remove(field)
        self._selected_field = None
        if block:
            self.query_one(RegisterTree).remove_field_node(block.name, reg.name, field.name)
        self._refresh_detail()

    def action_save(self) -> None:
        if not self.state.regfile:
            return

        self.push_screen(
            SaveDialog(self.state.regdb_path),
            callback=self._on_save_result,
        )

    def _on_save_result(self, path: str | None) -> None:
        if path:
            self._do_save(path)

    def _do_save(self, path: str) -> None:
        if not self.state.regfile:
            return

        try:
            with open(path, 'wb') as f:
                self.state.regfile.pack_to(f)
            self.state.regdb_path = path
            self._update_subtitle()
            self.notify(f'Saved to {path}')
        except Exception as e:
            self.notify(f'Save failed: {e}', severity='error')

    def action_poll(self) -> None:
        if self._selected_reg and self._selected_block:
            # Toggle watch on individual register
            block = self._selected_block
            reg = self._selected_reg
            bstate = self.state.block_states.get(block.name)
            if not bstate:
                return
            if reg.name in bstate.watched:
                bstate.watched.discard(reg.name)
                self.notify(f'Stopped watching {reg.name}')
            else:
                bstate.watched.add(reg.name)
                self.notify(f'Watching {reg.name}')
        elif self._selected_block:
            # Toggle watch on entire block
            bstate = self.state.block_states.get(self._selected_block.name)
            if not bstate:
                return
            bstate.watch_all = not bstate.watch_all
            if bstate.watch_all:
                self.notify(f'Watching all in {self._selected_block.name}')
            else:
                self.notify(f'Stopped watching {self._selected_block.name}')
        else:
            # Toggle watch on everything
            self.state.watch_all = not self.state.watch_all
            if self.state.watch_all:
                self.notify('Watching all registers')
            else:
                self.notify('Stopped watching all registers')
        self._ensure_poll_timer()
        self.query_one(RegisterTree).update_watch_labels(self.state)

    def action_poll_interval(self) -> None:
        self.push_screen(
            PollIntervalDialog(self.state.poll_interval),
            callback=self._on_poll_interval_result,
        )

    def _on_poll_interval_result(self, result: float | None) -> None:
        if result is None:
            return
        self.state.poll_interval = result
        self._restart_poll_timer()
        if result > 0:
            self.notify(f'Poll interval: {result}s')
        else:
            self.notify('Polling disabled')

    def action_format(self) -> None:
        if self.state.value_format == ValueFormat.HEX:
            self.state.value_format = ValueFormat.DEC
        elif self.state.value_format == ValueFormat.DEC:
            self.state.value_format = ValueFormat.BIN
        else:
            self.state.value_format = ValueFormat.HEX
        self.notify(f'Format: {self.state.value_format.value}')
        self._update_tree_values()
        self._refresh_detail()

    def action_toggle_values(self) -> None:
        self.state.show_values = not self.state.show_values
        if self.state.show_values:
            # Read all visible registers
            if self.state.regfile:
                for block in self.state.regfile.blocks:
                    for reg in block.regs:
                        bstate = self.state.block_states.get(block.name)
                        if bstate and bstate.reg_values.get(reg.name) is None:
                            self._read_register(block, reg)
        self._update_tree_values()

    # --- Polling ---

    def _has_anything_watched(self) -> bool:
        if self.state.watch_all:
            return True
        for bstate in self.state.block_states.values():
            if bstate.has_any_watched():
                return True
        return False

    def _ensure_poll_timer(self) -> None:
        """Start the poll timer if needed, or stop it if nothing to poll."""
        if self.state.poll_interval > 0 and self._has_anything_watched():
            if self._poll_timer is None:
                self._poll_timer = self.set_interval(self.state.poll_interval, self._poll_watched)
        else:
            self._stop_poll_timer()

    def _restart_poll_timer(self) -> None:
        self._stop_poll_timer()
        self._ensure_poll_timer()

    def _stop_poll_timer(self) -> None:
        if self._poll_timer is not None:
            self._poll_timer.stop()
            self._poll_timer = None

    def _poll_watched(self) -> None:
        if not self.state.regfile:
            return
        changed_regs: set[tuple[str, str]] = set()
        for block in self.state.regfile.blocks:
            bstate = self.state.block_states.get(block.name)
            if not bstate:
                continue
            poll_block = self.state.watch_all or bstate.watch_all
            for reg in block.regs:
                if poll_block or reg.name in bstate.watched:
                    old_val = bstate.reg_values.get(reg.name)
                    self._read_register(block, reg)
                    new_val = bstate.reg_values.get(reg.name)
                    if old_val != new_val:
                        changed_regs.add((block.name, reg.name))
        if changed_regs:
            tree = self.query_one(RegisterTree)
            tree.update_values(self.state, changed_regs)
            tree.highlight_changed(changed_regs)
            self._refresh_detail()
