"""ConfirmDialog for rwmem-tui."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ConfirmDialog(ModalScreen[bool]):
    """Simple yes/no confirmation dialog."""

    CSS = """
    ConfirmDialog {
        align: center middle;
    }
    #confirm-container {
        width: 50;
        height: auto;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #confirm-container .buttons {
        margin-top: 1;
        height: auto;
    }
    """

    BINDINGS = [
        ('escape', 'cancel', 'Cancel'),
    ]

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(id='confirm-container'):
            yield Label(self._message)
            with Horizontal(classes='buttons'):
                yield Button('Yes', variant='error', id='yes')
                yield Button('No', variant='primary', id='no')

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == 'yes')

    def action_cancel(self) -> None:
        self.dismiss(False)
