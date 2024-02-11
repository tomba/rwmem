from __future__ import annotations

def genmask(high: int, low: int):
    return ((1 << (high + 1)) - 1) & ~((1 << low) - 1)

def get_field_value(r_val: int, high: int, low: int):
    mask = genmask(high, low)
    return (r_val & mask) >> low

def set_field_value(r_val: int, high: int, low: int, f_val: int):
    mask = genmask(high, low)
    return (r_val & ~mask) | ((f_val << low) & mask)
