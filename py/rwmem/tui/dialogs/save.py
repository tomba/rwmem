"""SaveDialog for rwmem-tui."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static


class SaveDialog(ModalScreen[str | None]):
    """Dialog to save to current path or choose a new path."""

    CSS = """
    SaveDialog {
        align: center middle;
    }
    #save-container {
        width: 60;
        height: auto;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #save-container Label {
        margin-top: 1;
    }
    #save-container .buttons {
        margin-top: 1;
        height: auto;
    }
    #save-error {
        color: $error;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ('escape', 'cancel', 'Cancel'),
    ]

    def __init__(self, current_path: str | None) -> None:
        super().__init__()
        self._current_path = current_path

    def compose(self) -> ComposeResult:
        with Vertical(id='save-container'):
            yield Label('[bold]Save[/bold]')
            if self._current_path:
                yield Label(f'Current file: {self._current_path}')
                yield Button('Overwrite', variant='primary', id='overwrite')
            yield Label('File path')
            yield Input(
                placeholder='output.regdb',
                id='save-path',
                value=self._current_path or '',
            )
            yield Static('', id='save-error')
            with Horizontal(classes='buttons'):
                yield Button('Save As', variant='primary', id='save-as')
                yield Button('Cancel', id='cancel')

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == 'cancel':
            self.dismiss(None)
        elif event.button.id == 'overwrite':
            self.dismiss(self._current_path)
        elif event.button.id == 'save-as':
            self._submit()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _submit(self) -> None:
        error_widget = self.query_one('#save-error', Static)
        path = self.query_one('#save-path', Input).value.strip()
        if not path:
            error_widget.update('[red]Path is required[/red]')
            return
        self.dismiss(path)
