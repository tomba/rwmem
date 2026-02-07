"""WriteValueDialog for rwmem-tui."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from rwmem.gen import UnpackedField
from rwmem.helpers import get_field_value, set_field_value

from ._helpers import parse_int


class WriteValueDialog(ModalScreen[tuple[int, bool] | None]):
    """Dialog to write a register or field value.

    Returns (value, is_field_edit) or None if cancelled.
    """

    CSS = """
    WriteValueDialog {
        align: center middle;
    }
    #write-container {
        width: 60;
        max-height: 80%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #write-container Label {
        margin-top: 1;
    }
    #write-container .buttons {
        margin-top: 1;
        height: auto;
    }
    #write-error {
        color: $error;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ('escape', 'cancel', 'Cancel'),
    ]

    def __init__(
        self,
        reg_name: str,
        current_value: int | None,
        data_size: int,
        fields: list[UnpackedField],
        preselect_field: str | None = None,
    ) -> None:
        super().__init__()
        self._reg_name = reg_name
        self._current_value = current_value
        self._data_size = data_size
        self._fields = fields
        self._preselect_field = preselect_field

    def compose(self) -> ComposeResult:
        current_hex = ''
        if self._current_value is not None:
            nchars = (self._data_size * 8 + 3) // 4
            current_hex = f'0x{self._current_value:0{nchars}X}'

        write_options = [('Full register', 'full')]
        for field in self._fields:
            write_options.append((f'{field.name} [{field.high}:{field.low}]', field.name))

        initial_target = self._preselect_field if self._preselect_field else 'full'

        # Determine initial value display based on target
        initial_value = current_hex
        if self._preselect_field and self._current_value is not None:
            for field in self._fields:
                if field.name == self._preselect_field:
                    fv = get_field_value(self._current_value, field.high, field.low)
                    initial_value = hex(fv)
                    break

        with Vertical(id='write-container'):
            yield Label(f'[bold]Write {self._reg_name}[/bold]')
            if self._current_value is not None:
                yield Label(f'Current value: {current_hex}')
            else:
                yield Label('[dim]No value read yet (will write directly)[/dim]')
            yield Label('Target')
            yield Select(write_options, value=initial_target, id='write-target')
            yield Label('New value')
            yield Input(placeholder='0x0', id='write-value', value=initial_value)
            yield Static('', id='write-error')
            with Horizontal(classes='buttons'):
                yield Button('Write', variant='primary', id='ok')
                yield Button('Cancel', id='cancel')

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != 'write-target':
            return
        target = event.value
        value_input = self.query_one('#write-value', Input)
        if target == 'full':
            if self._current_value is not None:
                nchars = (self._data_size * 8 + 3) // 4
                value_input.value = f'0x{self._current_value:0{nchars}X}'
            else:
                value_input.value = ''
        else:
            # Field selected - show current field value
            if self._current_value is not None:
                for field in self._fields:
                    if field.name == target:
                        fv = get_field_value(self._current_value, field.high, field.low)
                        value_input.value = hex(fv)
                        break

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == 'cancel':
            self.dismiss(None)
        elif event.button.id == 'ok':
            self._submit()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _submit(self) -> None:
        error_widget = self.query_one('#write-error', Static)
        try:
            target = self.query_one('#write-target', Select).value
            raw_value = parse_int(self.query_one('#write-value', Input).value)
            max_val = (1 << (self._data_size * 8)) - 1

            if target == 'full':
                if raw_value < 0 or raw_value > max_val:
                    raise ValueError(f'Value out of range (0..0x{max_val:X})')
                self.dismiss((raw_value, False))
            else:
                # Field-level write: read-modify-write
                for field in self._fields:
                    if field.name == target:
                        field_max = (1 << (field.high - field.low + 1)) - 1
                        if raw_value < 0 or raw_value > field_max:
                            raise ValueError(f'Field value out of range (0..0x{field_max:X})')
                        base = self._current_value if self._current_value is not None else 0
                        new_val = set_field_value(base, field.high, field.low, raw_value)
                        self.dismiss((new_val, True))
                        return
                raise ValueError(f'Unknown field: {target}')
        except (ValueError, TypeError) as e:
            error_widget.update(f'[red]{e}[/red]')
