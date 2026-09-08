"""The rwmem-tui application."""

from __future__ import annotations

import time
from collections.abc import Sequence

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.timer import Timer
from textual.widgets import Footer, Header, Tree
from textual.worker import Worker

from rwmem.gen import UnpackedField

from .model import Model, field_mask, field_value, format_value
from .session import RegRef, Session
from .widgets import (
    BlockNode,
    DetailPanel,
    FieldNode,
    IntervalScreen,
    NodeData,
    RegisterTree,
    RegNode,
    ValueScreen,
)


class RwmemTui(App[None]):
    CSS = """
    #main { height: 1fr; }
    #reg-tree { width: 1fr; min-width: 30; max-width: 50%; border-right: solid $accent; }
    #detail-panel { width: 2fr; padding: 0 1; }
    """
    BINDINGS = [
        Binding('r', 'read', 'Read'),
        Binding('w', 'write', 'Write'),
        Binding('p', 'poll', 'Poll'),
        Binding('P', 'poll_interval', 'Interval'),
        Binding('f', 'format', 'Format'),
        Binding('q', 'quit', 'Quit'),
    ]
    TITLE = 'rwmem-tui'

    def __init__(self, session: Session, model: Model, interval: float = 0.5) -> None:
        super().__init__()
        self.session = session
        self.model = model
        self.interval = interval

        self._selected: NodeData = None
        self._timer: Timer | None = None
        self._poll_worker: Worker[None] | None = None
        self._last_read: float | None = None
        self._read_count = 0

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id='main'):
            yield RegisterTree(self.model)
            yield DetailPanel(self.model, self.session.description)
        yield Footer()

    def on_mount(self) -> None:
        self._update_subtitle()
        self.query_one(DetailPanel).show(None)
        self.query_one(RegisterTree).focus()

    def on_unmount(self) -> None:
        # Close before the thread workers are waited for: closing releases
        # a worker blocked in a request. Idempotent, so the caller may close
        # again.
        self.session.close()

    # --- selection ------------------------------------------------------

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted[NodeData]) -> None:
        self._selected = event.node.data
        self._refresh_detail()

    def _scope_refs(self) -> list[RegRef]:
        """The registers the current selection covers."""
        sel = self._selected
        if isinstance(sel, (RegNode, FieldNode)):
            return [sel.ref]
        if isinstance(sel, BlockNode):
            return self.model.refs_in(sel.block)
        return self.model.refs_in()

    def _refresh_detail(self) -> None:
        self.query_one(DetailPanel).show(self._selected)

    def _update_subtitle(self) -> None:
        watched = len(self.model.watched_refs())
        if not watched:
            poll = 'not polling'
        elif self.interval > 0:
            poll = f'poll {self.interval}s, {watched} watched'
        else:
            poll = f'polling off, {watched} watched'
        last = ''
        if self._last_read is not None:
            last = f'  |  last read {time.strftime("%H:%M:%S", time.localtime(self._last_read))}'
        lost = '' if self.session.alive else 'CONNECTION LOST  |  '
        self.sub_title = (
            f'{lost}{self.session.description}  |  {poll}  |  {self.model.fmt.value}{last}'
        )

    # --- reading --------------------------------------------------------

    # Every read and write runs in a worker thread of its own, and the
    # session's lock puts them in order. A request made while another is in
    # flight waits for it, so a write during a long poll batch goes through
    # once the batch is done. Only a poll tick that finds the previous poll
    # still running is skipped.

    def action_read(self) -> None:
        self._read(self._scope_refs())

    def _read(self, refs: Sequence[RegRef], quiet: bool = False) -> Worker[None] | None:
        if not refs:
            return None
        return self.run_worker(lambda: self._read_worker(refs, quiet), thread=True, name='read')

    def _read_worker(self, refs: Sequence[RegRef], quiet: bool = False) -> None:
        try:
            results = self.session.read_many(refs)
        except Exception as e:  # noqa: BLE001 - shown to the user
            what = refs[0].reg.name if len(refs) == 1 else f'{len(refs)} registers'
            self.call_from_thread(self._io_failed, f'Reading {what} failed: {e}')
            return
        self.call_from_thread(self._apply_read, refs, results, quiet)

    def _io_failed(self, message: str) -> None:
        self.notify(message, severity='error', timeout=10)
        self._update_timer()
        self._update_subtitle()

    def _apply_read(
        self, refs: Sequence[RegRef], results: Sequence[int | Exception], quiet: bool = False
    ) -> None:
        self._last_read = time.time()
        self._read_count += 1

        tree = self.query_one(RegisterTree)
        for ref, result in zip(refs, results, strict=True):
            self.model.apply(ref, result)
            tree.refresh_reg(ref)

        # A polled register that fails shows the error on its row; only a
        # read asked for gets a notice, or every tick would add one.
        if len(refs) == 1 and isinstance(results[0], Exception) and not quiet:
            self.notify(f'{refs[0].reg.name}: {results[0]}', severity='error')

        self._refresh_detail()
        self._update_subtitle()

    # --- writing --------------------------------------------------------

    def action_write(self) -> None:
        sel = self._selected
        if isinstance(sel, FieldNode):
            ref, field = sel.ref, sel.field
        elif isinstance(sel, RegNode):
            ref, field = sel.ref, None
        else:
            self.notify('Select a register or a field to write', severity='warning')
            return

        st = self.model.state(ref)
        if field is not None:
            bits = field.high - field.low + 1
            title = f'{ref.block.name}.{ref.reg.name}.{field.name} [{field.high}:{field.low}]'
            cur = field_value(st.value, field) if st.value is not None else None
        else:
            bits = ref.bits
            title = f'{ref.block.name}.{ref.reg.name}'
            cur = st.value
        current = (
            f'current: {format_value(cur, self.model.fmt, bits)}'
            if cur is not None
            else 'current: not read'
        )

        def done(value: int | None) -> None:
            if value is not None:
                self._write(ref, field, value)

        self.push_screen(ValueScreen(title, current, (1 << bits) - 1), callback=done)

    def _write(self, ref: RegRef, field: UnpackedField | None, value: int) -> None:
        self.run_worker(lambda: self._write_worker(ref, field, value), thread=True, name='write')

    def _write_worker(self, ref: RegRef, field: UnpackedField | None, value: int) -> None:
        # A field write is a read-modify-write; the session does it in one
        # go, so another write cannot get between the read and the write.
        try:
            if field is not None:
                readback = self.session.write(ref, value << field.low, field_mask(field))
            else:
                readback = self.session.write(ref, value)
        except Exception as e:  # noqa: BLE001 - shown to the user
            self.call_from_thread(self._io_failed, f'Write failed: {e}')
            return
        self.call_from_thread(self._apply_read, [ref], [readback])

    # --- polling --------------------------------------------------------

    def action_poll(self) -> None:
        sel = self._selected
        m = self.model
        tree = self.query_one(RegisterTree)

        if isinstance(sel, (RegNode, FieldNode)):
            key = sel.ref.key
            if key in m.watched_regs:
                m.watched_regs.discard(key)
                self.notify(f'Stopped polling {sel.ref.reg.name}')
            else:
                m.watched_regs.add(key)
                self.notify(f'Polling {sel.ref.reg.name}')
            tree.refresh_reg(sel.ref)
        elif isinstance(sel, BlockNode):
            name = sel.block.name
            if name in m.watched_blocks:
                m.watched_blocks.discard(name)
                self.notify(f'Stopped polling {name}')
            else:
                m.watched_blocks.add(name)
                self.notify(f'Polling {name}')
            tree.refresh_block(sel.block)
        else:
            m.watch_all = not m.watch_all
            self.notify('Polling everything' if m.watch_all else 'Stopped polling everything')
            tree.refresh_all()

        self._update_timer()
        self._update_subtitle()

    def _update_timer(self) -> None:
        # A session that has lost its agent is not polled: every tick would
        # only fail again.
        want = self.interval > 0 and bool(self.model.watched_refs()) and self.session.alive
        if want and self._timer is None:
            self._timer = self.set_interval(self.interval, self._poll_tick)
        elif not want and self._timer is not None:
            self._timer.stop()
            self._timer = None

    def _poll_tick(self) -> None:
        # A tick that finds the previous poll still running is skipped, so a
        # slow device does not build up a backlog of polls.
        if self._poll_worker is not None and not self._poll_worker.is_finished:
            return
        self._poll_worker = self._read(self.model.watched_refs(), quiet=True)

    def action_poll_interval(self) -> None:
        def done(value: float | None) -> None:
            if value is None:
                return
            self.interval = value
            if self._timer is not None:
                self._timer.stop()
                self._timer = None
            self._update_timer()
            self._update_subtitle()
            self.notify(f'Poll interval {value}s' if value > 0 else 'Polling disabled')

        self.push_screen(IntervalScreen(self.interval), callback=done)

    # --- misc -----------------------------------------------------------

    def action_format(self) -> None:
        self.model.fmt = self.model.fmt.next()
        self.query_one(RegisterTree).refresh_all()
        self._refresh_detail()
        self._update_subtitle()
