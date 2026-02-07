"""Left-pane register tree widget for rwmem-tui."""

from __future__ import annotations

from textual.message import Message
from textual.widgets import Tree
from textual.widgets._tree import TreeNode

from rwmem.gen import UnpackedField, UnpackedRegBlock, UnpackedRegister
from rwmem.helpers import get_field_value

from .state import AppState
from .types import BlockNodeData, FieldNodeData, RegisterNodeData, format_value


class RegisterTree(Tree):
    """Left pane: hierarchical block/register/field tree."""

    class RegisterSelected(Message):
        def __init__(self, block: UnpackedRegBlock, reg: UnpackedRegister) -> None:
            super().__init__()
            self.block = block
            self.reg = reg

    class BlockSelected(Message):
        def __init__(self, block: UnpackedRegBlock) -> None:
            super().__init__()
            self.block = block

    class FieldSelected(Message):
        def __init__(
            self, block: UnpackedRegBlock, reg: UnpackedRegister, field: UnpackedField
        ) -> None:
            super().__init__()
            self.block = block
            self.reg = reg
            self.field = field

    class NothingSelected(Message):
        pass

    def __init__(self) -> None:
        super().__init__('Registers', id='reg-tree')
        self.app_state: AppState | None = None
        self._block_nodes: dict[str, TreeNode] = {}
        self._reg_nodes: dict[tuple[str, str], TreeNode] = {}
        self._field_nodes: dict[tuple[str, str, str], TreeNode] = {}

    def _make_field_label(
        self, block: UnpackedRegBlock, reg: UnpackedRegister, field: UnpackedField, state: AppState
    ) -> str:
        label = f'{field.name} [{field.high}:{field.low}]'
        if state.show_values:
            bstate = state.block_states.get(block.name)
            if bstate:
                val = bstate.reg_values.get(reg.name)
                if val is not None:
                    fv = get_field_value(val, field.high, field.low)
                    field_bits = field.high - field.low + 1
                    label += f' = {format_value(fv, state.value_format, field_bits)}'
        return label

    def rebuild(self, state: AppState) -> None:
        self.app_state = state
        self.clear()
        self._block_nodes.clear()
        self._reg_nodes.clear()
        self._field_nodes.clear()

        if state.regfile is None or len(state.regfile.blocks) == 0:
            self.root.add_leaf('No register database loaded. Press [a] to add a block.')
            return

        self.root.set_label(self._make_root_label(state))

        for block in state.regfile.blocks:
            block_label = self._make_block_label(block, state)
            block_node = self.root.add(block_label, data=BlockNodeData(block))
            self._block_nodes[block.name] = block_node

            for reg in block.regs:
                reg_label = self._make_reg_label(block, reg, state)

                if reg.fields:
                    reg_node = block_node.add(reg_label, data=RegisterNodeData(block, reg))
                    self._reg_nodes[(block.name, reg.name)] = reg_node
                    for field in reg.fields:
                        field_label = self._make_field_label(block, reg, field, state)
                        fnode = reg_node.add_leaf(
                            field_label, data=FieldNodeData(block, reg, field)
                        )
                        self._field_nodes[(block.name, reg.name, field.name)] = fnode
                    # Fields collapsed by default
                else:
                    reg_node = block_node.add_leaf(reg_label, data=RegisterNodeData(block, reg))
                    self._reg_nodes[(block.name, reg.name)] = reg_node

            block_node.expand()

        self.root.expand()

    def _make_reg_label(
        self, block: UnpackedRegBlock, reg: UnpackedRegister, state: AppState
    ) -> str:
        bstate = state.block_states.get(block.name)
        abs_addr = block.offset + reg.offset
        reg_label = f'{reg.name} @ +0x{reg.offset:X} (0x{abs_addr:X})'
        if state.show_values and bstate:
            val = bstate.reg_values.get(reg.name)
            err = bstate.reg_errors.get(reg.name)
            if err:
                reg_label += ' [red]ERR[/red]'
            elif val is not None:
                ds = reg.get_effective_data_size(block.data_size)
                reg_label += f' = {format_value(val, state.value_format, ds * 8)}'
        if bstate and reg.name in bstate.watched:
            reg_label += ' [yellow]●[/yellow]'
        return reg_label

    def _make_block_label(self, block: UnpackedRegBlock, state: AppState) -> str:
        bstate = state.block_states.get(block.name)
        block_label = f'{block.name} @ 0x{block.offset:X}'
        if bstate and bstate.error:
            block_label += ' [red](ERR)[/red]'
        if bstate and bstate.watch_all:
            block_label += ' [yellow]●[/yellow]'
        return block_label

    def _make_root_label(self, state: AppState) -> str:
        root_label = state.target_str or 'Registers'
        if state.watch_all:
            root_label += ' [yellow]●[/yellow]'
        return root_label

    def add_block_node(self, block: UnpackedRegBlock, state: AppState) -> None:
        """Surgically add a new block node under root."""
        self.app_state = state

        # If the tree was showing the "no database" placeholder, clear it
        if not self._block_nodes and self.root.children:
            # Remove placeholder leaf
            for child in list(self.root.children):
                child.remove()
            self.root.set_label(self._make_root_label(state))

        block_label = self._make_block_label(block, state)
        block_node = self.root.add(block_label, data=BlockNodeData(block))
        self._block_nodes[block.name] = block_node

        for reg in block.regs:
            reg_label = self._make_reg_label(block, reg, state)
            if reg.fields:
                reg_node = block_node.add(reg_label, data=RegisterNodeData(block, reg))
                self._reg_nodes[(block.name, reg.name)] = reg_node
                for field in reg.fields:
                    field_label = self._make_field_label(block, reg, field, state)
                    fnode = reg_node.add_leaf(field_label, data=FieldNodeData(block, reg, field))
                    self._field_nodes[(block.name, reg.name, field.name)] = fnode
            else:
                reg_node = block_node.add_leaf(reg_label, data=RegisterNodeData(block, reg))
                self._reg_nodes[(block.name, reg.name)] = reg_node

        block_node.expand()
        self.root.expand()

    def remove_block_node(self, block_name: str) -> None:
        """Surgically remove a block node and clean up tracking dicts."""
        block_node = self._block_nodes.pop(block_name, None)
        if block_node is None:
            return

        # Clean up reg and field node entries for this block
        reg_keys = [k for k in self._reg_nodes if k[0] == block_name]
        for k in reg_keys:
            del self._reg_nodes[k]
        field_keys = [k for k in self._field_nodes if k[0] == block_name]
        for k in field_keys:
            del self._field_nodes[k]

        block_node.remove()

    def add_register_node(
        self, block: UnpackedRegBlock, reg: UnpackedRegister, state: AppState
    ) -> None:
        """Surgically add a register node under its block."""
        self.app_state = state
        block_node = self._block_nodes.get(block.name)
        if block_node is None:
            return

        reg_label = self._make_reg_label(block, reg, state)
        if reg.fields:
            reg_node = block_node.add(reg_label, data=RegisterNodeData(block, reg))
            self._reg_nodes[(block.name, reg.name)] = reg_node
            for field in reg.fields:
                field_label = self._make_field_label(block, reg, field, state)
                fnode = reg_node.add_leaf(field_label, data=FieldNodeData(block, reg, field))
                self._field_nodes[(block.name, reg.name, field.name)] = fnode
        else:
            reg_node = block_node.add_leaf(reg_label, data=RegisterNodeData(block, reg))
            self._reg_nodes[(block.name, reg.name)] = reg_node

    def remove_register_node(self, block_name: str, reg_name: str) -> None:
        """Surgically remove a register node and clean up tracking dicts."""
        reg_node = self._reg_nodes.pop((block_name, reg_name), None)
        if reg_node is None:
            return

        # Clean up field node entries for this register
        field_keys = [k for k in self._field_nodes if k[0] == block_name and k[1] == reg_name]
        for k in field_keys:
            del self._field_nodes[k]

        reg_node.remove()

    def add_field_node(
        self,
        block: UnpackedRegBlock,
        reg: UnpackedRegister,
        field: UnpackedField,
        state: AppState,
    ) -> None:
        """Surgically add a field node under its register.

        If the register was a leaf (no fields before), convert it to an
        expandable node and expand it so the new field is visible.
        """
        self.app_state = state
        key = (block.name, reg.name)
        reg_node = self._reg_nodes.get(key)
        if reg_node is None:
            return

        # If the register was a leaf, make it expandable
        if not reg_node.allow_expand:
            reg_node.allow_expand = True

        field_label = self._make_field_label(block, reg, field, state)
        fnode = reg_node.add_leaf(field_label, data=FieldNodeData(block, reg, field))
        self._field_nodes[(block.name, reg.name, field.name)] = fnode

        # Expand so user sees the new field
        reg_node.expand()

    def remove_field_node(self, block_name: str, reg_name: str, field_name: str) -> None:
        """Surgically remove a field node.

        If the register has no more field nodes, convert it back to a leaf.
        """
        fnode = self._field_nodes.pop((block_name, reg_name, field_name), None)
        if fnode is None:
            return

        fnode.remove()

        # If register now has no field children, make it a leaf
        reg_node = self._reg_nodes.get((block_name, reg_name))
        if reg_node is not None and not reg_node.children:
            reg_node.allow_expand = False

    def update_watch_labels(self, state: AppState) -> None:
        """Update root, block, and register labels to reflect watch changes."""
        self.app_state = state
        if state.regfile is None:
            return

        self.root.set_label(self._make_root_label(state))

        for block in state.regfile.blocks:
            block_node = self._block_nodes.get(block.name)
            if block_node is not None:
                block_node.set_label(self._make_block_label(block, state))
            for reg in block.regs:
                reg_node = self._reg_nodes.get((block.name, reg.name))
                if reg_node is not None:
                    reg_node.set_label(self._make_reg_label(block, reg, state))

    def update_values(
        self, state: AppState, changed_regs: set[tuple[str, str]] | None = None
    ) -> None:
        """Update tree labels in-place for value changes.

        If changed_regs is provided, only those (block_name, reg_name) pairs
        are updated. Otherwise all register/field labels are refreshed.
        """
        self.app_state = state
        if state.regfile is None:
            return

        for block in state.regfile.blocks:
            for reg in block.regs:
                key = (block.name, reg.name)
                if changed_regs is not None and key not in changed_regs:
                    continue
                node = self._reg_nodes.get(key)
                if node:
                    node.set_label(self._make_reg_label(block, reg, state))
                for field in reg.fields:
                    fkey = (block.name, reg.name, field.name)
                    fnode = self._field_nodes.get(fkey)
                    if fnode:
                        fnode.set_label(self._make_field_label(block, reg, field, state))

    def highlight_changed(self, changed_regs: set[tuple[str, str]]) -> None:
        """Briefly highlight changed register/field nodes with yellow background."""
        for bname, rname in changed_regs:
            node = self._reg_nodes.get((bname, rname))
            if node:
                original = node.label
                node.set_label(f'[on dark_goldenrod]{original}[/on dark_goldenrod]')

                def _revert(n=node, lbl=original):
                    n.set_label(lbl)

                self.set_timer(1.5, _revert)

            # Also highlight field nodes
            state = self.app_state
            if state and state.regfile:
                for block in state.regfile.blocks:
                    if block.name != bname:
                        continue
                    for reg in block.regs:
                        if reg.name != rname:
                            continue
                        for field in reg.fields:
                            fnode = self._field_nodes.get((bname, rname, field.name))
                            if fnode:
                                forig = fnode.label
                                fnode.set_label(f'[on dark_goldenrod]{forig}[/on dark_goldenrod]')

                                def _frevert(fn=fnode, fl=forig):
                                    fn.set_label(fl)

                                self.set_timer(1.5, _frevert)

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        node = event.node
        data = node.data
        if data is None:
            self.post_message(self.NothingSelected())
        elif isinstance(data, BlockNodeData):
            self.post_message(self.BlockSelected(data.block))
        elif isinstance(data, RegisterNodeData):
            self.post_message(self.RegisterSelected(data.block, data.reg))
        elif isinstance(data, FieldNodeData):
            self.post_message(self.FieldSelected(data.block, data.reg, data.field))
