"""AddFieldDialog for rwmem-tui."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static


class AddFieldDialog(ModalScreen[dict | None]):
    """Dialog to add a new field to a register."""

    CSS = """
    AddFieldDialog {
        align: center middle;
    }
    #add-field-container {
        width: 60;
        max-height: 80%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #add-field-container Label {
        margin-top: 1;
    }
    #add-field-container .buttons {
        margin-top: 1;
        height: auto;
    }
    #add-field-error {
        color: $error;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ('escape', 'cancel', 'Cancel'),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id='add-field-container'):
            yield Label('[bold]Add Field[/bold]')
            yield Label('Name')
            yield Input(placeholder='FIELD_NAME', id='field-name')
            yield Label('High bit')
            yield Input(placeholder='7', id='field-high')
            yield Label('Low bit')
            yield Input(placeholder='0', id='field-low')
            yield Label('Description (optional)')
            yield Input(placeholder='', id='field-description')
            yield Static('', id='add-field-error')
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
        error_widget = self.query_one('#add-field-error', Static)
        try:
            name = self.query_one('#field-name', Input).value.strip()
            if not name:
                raise ValueError('Name is required')
            high = int(self.query_one('#field-high', Input).value.strip())
            low = int(self.query_one('#field-low', Input).value.strip())

            if high < low:
                raise ValueError('High bit must be >= low bit')

            description = self.query_one('#field-description', Input).value.strip()

            self.dismiss(
                {
                    'name': name,
                    'high': high,
                    'low': low,
                    'description': description,
                }
            )
        except (ValueError, TypeError) as e:
            error_widget.update(f'[red]{e}[/red]')
