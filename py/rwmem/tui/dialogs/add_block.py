"""AddBlockDialog for rwmem-tui."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from rwmem.enums import Endianness

from ._helpers import parse_int


class AddBlockDialog(ModalScreen[dict | None]):
    """Dialog to add a new register block."""

    CSS = """
    AddBlockDialog {
        align: center middle;
    }
    #add-block-container {
        width: 60;
        max-height: 80%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #add-block-container Label {
        margin-top: 1;
    }
    #add-block-container .buttons {
        margin-top: 1;
        height: auto;
    }
    #add-block-error {
        color: $error;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ('escape', 'cancel', 'Cancel'),
    ]

    def __init__(self, target_mode: str) -> None:
        super().__init__()
        self._target_mode = target_mode

    def compose(self) -> ComposeResult:
        with VerticalScroll(id='add-block-container'):
            yield Label('[bold]Add Register Block[/bold]')
            yield Label('Name')
            yield Input(placeholder='BLOCK_NAME', id='block-name')
            yield Label('Base offset (hex)')
            yield Input(placeholder='0x0', id='block-offset', value='0x0')
            yield Label('Size (hex)')
            yield Input(placeholder='0x100', id='block-size', value='0x100')
            if self._target_mode == 'i2c':
                yield Label('Address endianness')
                yield Select(
                    [(e.name, e) for e in Endianness if e != Endianness.Default],
                    value=Endianness.Big,
                    id='block-addr-endian',
                )
                yield Label('Address size (bytes)')
                yield Select(
                    [(str(s), s) for s in (1, 2, 4, 8)],
                    value=1,
                    id='block-addr-size',
                )
            yield Label('Data endianness')
            yield Select(
                [(e.name, e) for e in Endianness if e != Endianness.Default],
                value=Endianness.Little,
                id='block-data-endian',
            )
            yield Label('Data size (bytes)')
            yield Select(
                [(str(s), s) for s in (1, 2, 3, 4, 8)],
                value=4,
                id='block-data-size',
            )
            yield Label('Description (optional)')
            yield Input(placeholder='', id='block-description')
            yield Static('', id='add-block-error')
            with Horizontal(classes='buttons'):
                yield Button('OK', variant='primary', id='ok')
                yield Button('Cancel', id='cancel')

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == 'cancel':
            self.dismiss(None)
        elif event.button.id == 'ok':
            self._submit()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _submit(self) -> None:
        error_widget = self.query_one('#add-block-error', Static)
        try:
            name = self.query_one('#block-name', Input).value.strip()
            if not name:
                raise ValueError('Name is required')
            offset = parse_int(self.query_one('#block-offset', Input).value)
            size = parse_int(self.query_one('#block-size', Input).value)

            if self._target_mode == 'i2c':
                addr_endian = self.query_one('#block-addr-endian', Select).value
                addr_size = self.query_one('#block-addr-size', Select).value
            else:
                # mmap doesn't use address encoding, but the data model
                # requires valid values
                addr_endian = Endianness.Little
                addr_size = 1

            data_endian = self.query_one('#block-data-endian', Select).value
            data_size = self.query_one('#block-data-size', Select).value
            description = self.query_one('#block-description', Input).value.strip()

            self.dismiss(
                {
                    'name': name,
                    'offset': offset,
                    'size': size,
                    'addr_endianness': addr_endian,
                    'addr_size': addr_size,
                    'data_endianness': data_endian,
                    'data_size': data_size,
                    'description': description,
                }
            )
        except (ValueError, TypeError) as e:
            error_widget.update(f'[red]{e}[/red]')
