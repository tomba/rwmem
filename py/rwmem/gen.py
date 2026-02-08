from __future__ import annotations

import io
from typing import Sequence

from ._packer import RegFilePacker
from .enums import Endianness


# Custom exception classes for validation errors
class RegGenValidationError(ValueError):
    """Base class for register generation validation errors."""

    pass


class FieldValidationError(RegGenValidationError):
    """Raised when a field definition is invalid."""

    pass


class RegisterValidationError(RegGenValidationError):
    """Raised when a register definition is invalid."""

    pass


class BlockValidationError(RegGenValidationError):
    """Raised when a register block definition is invalid."""

    pass


class RegFileValidationError(RegGenValidationError):
    """Raised when a register file definition is invalid."""

    pass


class UnpackedField:
    def __init__(self, name: str, high: int, low: int, description: str | None = None) -> None:
        self._validate_inputs(name, high, low, description)
        self.name = name
        self.high = high
        self.low = low
        self.description = description

    def _validate_inputs(self, name: str, high: int, low: int, description: str | None) -> None:
        """Validate field inputs and raise descriptive errors."""
        if not name or not isinstance(name, str):
            raise FieldValidationError('Field name must be a non-empty string')

        if not isinstance(high, int) or not isinstance(low, int):
            raise FieldValidationError(
                f"Field '{name}': high and low must be integers, got high={type(high).__name__}, low={type(low).__name__}"
            )

        if high < 0 or low < 0:
            raise FieldValidationError(
                f"Field '{name}': bit positions must be non-negative, got high={high}, low={low}"
            )

        if high < low:
            raise FieldValidationError(
                f"Field '{name}': high bit ({high}) must be >= low bit ({low})"
            )

        if high > 63:  # Reasonable maximum for register bit positions
            raise FieldValidationError(
                f"Field '{name}': high bit position ({high}) exceeds maximum (63)"
            )

        if description is not None and not isinstance(description, str):
            raise FieldValidationError(
                f"Field '{name}': description must be a string or None, got {type(description).__name__}"
            )

    def validate_against_register_width(self, register_name: str, data_size: int) -> None:
        """Validate that field fits within register data width."""
        max_bit = (data_size * 8) - 1
        if self.high > max_bit:
            raise FieldValidationError(
                f"Field '{self.name}' in register '{register_name}': "
                f'high bit ({self.high}) exceeds register width ({data_size} bytes = {max_bit} max bit)'
            )


class UnpackedRegister:
    def __init__(
        self,
        name: str,
        offset: int,
        fields: Sequence[UnpackedField] | None = None,
        description: str | None = None,
        reset_value: int = 0,
        data_endianness: Endianness | None = None,
        data_size: int | None = None,
    ) -> None:
        self._validate_inputs(name, offset, description, reset_value, data_endianness, data_size)
        self.name = name
        self.offset = offset
        self.description = description
        self.reset_value = reset_value
        self.data_endianness = data_endianness
        self.data_size = data_size

        if fields:
            self.fields = list(fields)
            self._validate_field_overlaps()
        else:
            self.fields = []

    def _validate_inputs(
        self,
        name: str,
        offset: int,
        description: str | None,
        reset_value: int,
        data_endianness: Endianness | None,
        data_size: int | None,
    ) -> None:
        """Validate register inputs and raise descriptive errors."""
        if not name or not isinstance(name, str):
            raise RegisterValidationError('Register name must be a non-empty string')

        if not isinstance(offset, int):
            raise RegisterValidationError(
                f"Register '{name}': offset must be an integer, got {type(offset).__name__}"
            )

        if offset < 0:
            raise RegisterValidationError(
                f"Register '{name}': offset must be non-negative, got {offset}"
            )

        if description is not None and not isinstance(description, str):
            raise RegisterValidationError(
                f"Register '{name}': description must be a string or None, got {type(description).__name__}"
            )

        if not isinstance(reset_value, int):
            raise RegisterValidationError(
                f"Register '{name}': reset_value must be an integer, got {type(reset_value).__name__}"
            )

        if reset_value < 0:
            raise RegisterValidationError(
                f"Register '{name}': reset_value must be non-negative, got {reset_value}"
            )

        # Validate optional endianness parameters
        if data_endianness is not None and not isinstance(data_endianness, Endianness):
            raise RegisterValidationError(
                f"Register '{name}': data_endianness must be an Endianness enum or None, got {type(data_endianness).__name__}"
            )

        # Validate optional size parameters
        if data_size is not None and (
            not isinstance(data_size, int) or data_size not in range(1, 9)
        ):
            raise RegisterValidationError(
                f"Register '{name}': data_size must be 1-8 bytes or None, got {data_size}"
            )

    def _validate_field_overlaps(self) -> None:
        """Check for overlapping fields within this register."""
        if len(self.fields) <= 1:
            return

        # Create list of (low, high, name) tuples for overlap checking
        field_ranges = [(f.low, f.high, f.name) for f in self.fields]
        field_ranges.sort()  # Sort by low bit

        for i in range(len(field_ranges) - 1):
            curr_low, curr_high, curr_name = field_ranges[i]
            next_low, next_high, next_name = field_ranges[i + 1]

            if curr_high >= next_low:
                raise RegisterValidationError(
                    f"Register '{self.name}': overlapping fields '{curr_name}' ({curr_high}:{curr_low}) "
                    f"and '{next_name}' ({next_high}:{next_low})"
                )

    def get_effective_data_size(self, block_data_size: int) -> int:
        """Get effective data size, using register-specific size or inheriting from block."""
        return self.data_size if self.data_size is not None else block_data_size

    def get_effective_data_endianness(self, block_data_endianness: Endianness) -> Endianness:
        """Get effective data endianness, using register-specific endianness or inheriting from block."""
        return self.data_endianness if self.data_endianness is not None else block_data_endianness

    def validate_reset_value(self, effective_data_size: int) -> None:
        """Validate that reset_value fits within effective data size."""
        max_value = (1 << (effective_data_size * 8)) - 1
        if self.reset_value > max_value:
            raise RegisterValidationError(
                f"Register '{self.name}': reset_value (0x{self.reset_value:x}) exceeds maximum for {effective_data_size}-byte register (0x{max_value:x})"
            )

    def validate_against_block(
        self,
        block_name: str,
        block_offset: int,
        block_size: int,
        block_addr_size: int,
        block_data_size: int,
    ) -> None:
        """Validate register against its containing block."""
        effective_data_size = self.get_effective_data_size(block_data_size)

        # Validate reset value fits within effective data size
        self.validate_reset_value(effective_data_size)

        # Check if register fits within block boundaries (if block size is specified)
        if block_size > 0:
            reg_end = self.offset + effective_data_size
            if reg_end > block_size:
                raise RegisterValidationError(
                    f"Register '{self.name}' in block '{block_name}': "
                    f'register extends beyond block boundary (offset {self.offset} + size {effective_data_size} > block size {block_size})'
                )

        # Validate fields against register data width
        for field in self.fields:
            field.validate_against_register_width(self.name, effective_data_size)


class UnpackedRegBlock:
    def __init__(
        self,
        name: str,
        offset: int,
        size: int,
        regs: Sequence[UnpackedRegister],
        addr_endianness: Endianness,
        addr_size: int,
        data_endianness: Endianness,
        data_size: int,
        description: str | None = None,
    ) -> None:
        self._validate_inputs(
            name, offset, size, addr_endianness, addr_size, data_endianness, data_size, description
        )

        self.name = name
        self.offset = offset
        self.size = size
        self.addr_endianness = addr_endianness
        self.addr_size = addr_size
        self.data_endianness = data_endianness
        self.data_size = data_size
        self.description = description

        # Store registers and validate them
        self.regs = list(regs)
        self._validate_register_overlaps()
        self._validate_registers_against_block()

    def _validate_inputs(
        self,
        name: str,
        offset: int,
        size: int,
        addr_endianness: Endianness,
        addr_size: int,
        data_endianness: Endianness,
        data_size: int,
        description: str | None,
    ) -> None:
        """Validate block inputs and raise descriptive errors."""
        if not name or not isinstance(name, str):
            raise BlockValidationError('Block name must be a non-empty string')

        if not isinstance(offset, int):
            raise BlockValidationError(
                f"Block '{name}': offset must be an integer, got {type(offset).__name__}"
            )

        if offset < 0:
            raise BlockValidationError(f"Block '{name}': offset must be non-negative, got {offset}")

        if not isinstance(size, int):
            raise BlockValidationError(
                f"Block '{name}': size must be an integer, got {type(size).__name__}"
            )

        if size < 0:
            raise BlockValidationError(f"Block '{name}': size must be non-negative, got {size}")

        if not isinstance(addr_endianness, Endianness):
            raise BlockValidationError(
                f"Block '{name}': addr_endianness must be an Endianness enum, got {type(addr_endianness).__name__}"
            )

        if not isinstance(data_endianness, Endianness):
            raise BlockValidationError(
                f"Block '{name}': data_endianness must be an Endianness enum, got {type(data_endianness).__name__}"
            )

        if addr_size not in (1, 2, 4, 8):
            raise BlockValidationError(
                f"Block '{name}': addr_size must be 1, 2, 4, or 8, got {addr_size}"
            )

        if data_size not in range(1, 9):
            raise BlockValidationError(
                f"Block '{name}': data_size must be 1-8 bytes, got {data_size}"
            )

        if description is not None and not isinstance(description, str):
            raise BlockValidationError(
                f"Block '{name}': description must be a string or None, got {type(description).__name__}"
            )

    def _validate_register_overlaps(self) -> None:
        """Check for overlapping registers within this block."""
        if len(self.regs) <= 1:
            return

        # Create list of (offset, end_offset, name) tuples for overlap checking
        # Use effective data size for each register
        reg_ranges = []
        for r in self.regs:
            effective_size = r.get_effective_data_size(self.data_size)
            reg_ranges.append((r.offset, r.offset + effective_size, r.name))
        reg_ranges.sort()  # Sort by offset

        for i in range(len(reg_ranges) - 1):
            curr_start, curr_end, curr_name = reg_ranges[i]
            next_start, next_end, next_name = reg_ranges[i + 1]

            if curr_end > next_start:
                raise BlockValidationError(
                    f"Block '{self.name}': overlapping registers '{curr_name}' (0x{curr_start:x}-0x{curr_end:x}) "
                    f"and '{next_name}' (0x{next_start:x}-0x{next_end:x})"
                )

    def _validate_registers_against_block(self) -> None:
        """Validate all registers against block constraints."""
        for reg in self.regs:
            reg.validate_against_block(
                self.name, self.offset, self.size, self.addr_size, self.data_size
            )


class UnpackedRegFile:
    def __init__(
        self, name: str, blocks: Sequence[UnpackedRegBlock], description: str | None = None
    ) -> None:
        self._validate_inputs(name, description)
        self.name = name
        self.description = description

        # Store blocks and validate them
        self.blocks = list(blocks)
        self._validate_block_overlaps()

    def _validate_inputs(self, name: str, description: str | None) -> None:
        """Validate regfile inputs and raise descriptive errors."""
        if not name or not isinstance(name, str):
            raise RegFileValidationError('Register file name must be a non-empty string')

        if description is not None and not isinstance(description, str):
            raise RegFileValidationError(
                f"Register file '{name}': description must be a string or None, got {type(description).__name__}"
            )

    def _validate_block_overlaps(self) -> None:
        """Check for overlapping blocks within this register file."""
        if len(self.blocks) <= 1:
            return

        # Create list of (offset, end_offset, name) tuples for overlap checking
        block_ranges = []
        for block in self.blocks:
            if block.size > 0:
                block_ranges.append((block.offset, block.offset + block.size, block.name))
            # Skip blocks with size 0 (auto-calculated) for overlap checking

        if len(block_ranges) <= 1:
            return

        block_ranges.sort()  # Sort by offset

        for i in range(len(block_ranges) - 1):
            curr_start, curr_end, curr_name = block_ranges[i]
            next_start, next_end, next_name = block_ranges[i + 1]

            if curr_end > next_start:
                raise RegFileValidationError(
                    f"Register file '{self.name}': overlapping blocks '{curr_name}' (0x{curr_start:x}-0x{curr_end:x}) "
                    f"and '{next_name}' (0x{next_start:x}-0x{next_end:x})"
                )

    def pack_to(self, out: io.IOBase):
        packer = RegFilePacker(self)
        packer.pack_to(out)


def create_register_file(name: str, blocks_spec, description: str | None = None) -> UnpackedRegFile:
    """Create UnpackedRegFile from mixed tuple/object specifications.

    Args:
        name: Register file name
        blocks_spec: Sequence of UnpackedRegBlock objects or tuples
        description: Optional description

    Returns:
        UnpackedRegFile with all specifications converted to objects
    """
    converted_blocks = [_convert_block_spec(block_spec) for block_spec in blocks_spec]
    return UnpackedRegFile(name, converted_blocks, description)


def _convert_block_spec(block_spec):
    """Convert block specification to UnpackedRegBlock object."""
    if isinstance(block_spec, UnpackedRegBlock):
        return block_spec
    elif isinstance(block_spec, tuple):
        (
            name,
            offset,
            size,
            regs_spec,
            addr_endianness,
            addr_size,
            data_endianness,
            data_size,
            *rest,
        ) = block_spec
        description = rest[0] if rest else None
        converted_regs = [_convert_register_spec(reg_spec) for reg_spec in regs_spec]
        return UnpackedRegBlock(
            name,
            offset,
            size,
            converted_regs,
            addr_endianness,
            addr_size,
            data_endianness,
            data_size,
            description,
        )
    else:
        raise TypeError(
            f'Block specification must be UnpackedRegBlock or tuple, got {type(block_spec).__name__}'
        )


def _convert_register_spec(reg_spec):
    """Convert register specification to UnpackedRegister object."""
    if isinstance(reg_spec, UnpackedRegister):
        return reg_spec
    elif isinstance(reg_spec, tuple):
        name, offset, *rest = reg_spec
        fields_spec = rest[0] if rest else []
        converted_fields = [_convert_field_spec(field_spec) for field_spec in fields_spec]
        return UnpackedRegister(name, offset, converted_fields)
    else:
        raise TypeError(
            f'Register specification must be UnpackedRegister or tuple, got {type(reg_spec).__name__}'
        )


def _convert_field_spec(field_spec):
    """Convert field specification to UnpackedField object."""
    if isinstance(field_spec, UnpackedField):
        return field_spec
    elif isinstance(field_spec, tuple):
        return UnpackedField(*field_spec)
    else:
        raise TypeError(
            f'Field specification must be UnpackedField or tuple, got {type(field_spec).__name__}'
        )
