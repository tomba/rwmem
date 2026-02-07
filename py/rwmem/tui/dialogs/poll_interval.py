"""PollIntervalDialog for rwmem-tui."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static


class PollIntervalDialog(ModalScreen[float | None]):
    """Dialog to set the poll interval."""

    CSS = """
    PollIntervalDialog {
        align: center middle;
    }
    #poll-interval-container {
        width: 50;
        height: auto;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #poll-interval-container Label {
        margin-top: 1;
    }
    #poll-interval-container .buttons {
        margin-top: 1;
        height: auto;
    }
    #poll-interval-error {
        color: $error;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ('escape', 'cancel', 'Cancel'),
    ]

    def __init__(self, current_interval: float) -> None:
        super().__init__()
        self._current_interval = current_interval

    def compose(self) -> ComposeResult:
        if self._current_interval > 0:
            current_str = str(self._current_interval)
        else:
            current_str = '0'

        with Vertical(id='poll-interval-container'):
            yield Label('[bold]Poll Interval[/bold]')
            yield Label('Interval in seconds (0 to disable)')
            yield Input(
                placeholder='0.1',
                id='poll-interval-value',
                value=current_str,
            )
            yield Static('', id='poll-interval-error')
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
        error_widget = self.query_one('#poll-interval-error', Static)
        try:
            text = self.query_one('#poll-interval-value', Input).value.strip()
            if not text:
                raise ValueError('Value is required')
            interval = float(text)
            if interval < 0:
                raise ValueError('Interval must be >= 0')
            if interval > 0 and interval < 0.05:
                raise ValueError('Minimum interval is 0.05s')
            self.dismiss(interval)
        except ValueError as e:
            error_widget.update(f'[red]{e}[/red]')
