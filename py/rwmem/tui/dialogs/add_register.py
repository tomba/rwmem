"""AddRegisterDialog for rwmem-tui."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from rwmem.enums import Endianness
from rwmem.gen import UnpackedRegBlock

from ._helpers import parse_int


class AddRegisterDialog(ModalScreen[dict | None]):
    """Dialog to add a new register to a block."""

    CSS = """
    AddRegisterDialog {
        align: center middle;
    }
    #add-reg-container {
        width: 60;
        max-height: 80%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #add-reg-container Label {
        margin-top: 1;
    }
    #add-reg-container .buttons {
        margin-top: 1;
        height: auto;
    }
    #add-reg-error {
        color: $error;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ('escape', 'cancel', 'Cancel'),
    ]

    def __init__(self, block: UnpackedRegBlock) -> None:
        super().__init__()
        self._block = block

    def compose(self) -> ComposeResult:
        endian_options = [('Inherit from block', None)]
        endian_options += [(e.name, e) for e in Endianness if e != Endianness.Default]

        size_options = [('Inherit from block', None)]
        size_options += [(str(s), s) for s in (1, 2, 3, 4, 8)]

        with VerticalScroll(id='add-reg-container'):
            yield Label(f'[bold]Add Register to {self._block.name}[/bold]')
            yield Label('Name')
            yield Input(placeholder='REG_NAME', id='reg-name')
            yield Label('Offset within block (hex)')
            yield Input(placeholder='0x0', id='reg-offset', value='0x0')
            yield Label('Data endianness')
            yield Select(endian_options, value=None, id='reg-data-endian')
            yield Label('Data size (bytes)')
            yield Select(size_options, value=None, id='reg-data-size')
            yield Label('Description (optional)')
            yield Input(placeholder='', id='reg-description')
            yield Static('', id='add-reg-error')
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
        error_widget = self.query_one('#add-reg-error', Static)
        try:
            name = self.query_one('#reg-name', Input).value.strip()
            if not name:
                raise ValueError('Name is required')
            offset = parse_int(self.query_one('#reg-offset', Input).value)
            data_endian = self.query_one('#reg-data-endian', Select).value
            data_size = self.query_one('#reg-data-size', Select).value
            description = self.query_one('#reg-description', Input).value.strip()

            self.dismiss(
                {
                    'name': name,
                    'offset': offset,
                    'data_endianness': data_endian,
                    'data_size': data_size,
                    'description': description,
                }
            )
        except (ValueError, TypeError) as e:
            error_widget.update(f'[red]{e}[/red]')
