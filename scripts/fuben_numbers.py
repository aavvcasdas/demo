#!/usr/bin/env python3
"""Shared, conservative Chinese / Arabic quantity parsing (no eval, stdlib only)."""
from decimal import Decimal, InvalidOperation
import re
import unicodedata

DIGITS = {c: n for n, chars in enumerate(('零〇', '一壹', '二两贰', '三叁', '四肆', '五伍', '六陆', '七柒', '八捌', '九玖')) for c in chars}
UNITS = {'十': 10, '拾': 10, '百': 100, '佰': 100, '千': 1000, '仟': 1000}
NUM_PATTERN = r'[0-9零〇一二两三四五六七八九十百千万亿壹贰叁肆伍陆柒捌玖拾佰仟][0-9零〇一二两三四五六七八九十百千万亿壹贰叁肆伍陆柒捌玖拾佰仟点.，,]{0,79}'


def number(text: str, *, colloquial: bool = False) -> Decimal:
    text = unicodedata.normalize('NFKC', str(text)).strip().replace('，', ',')
    if not text or len(text) > 80:
        raise ValueError('empty or overlong number')
    if re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)', text):
        return Decimal(text)
    if re.fullmatch(r'[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?', text):
        return Decimal(text.replace(',', ''))
    if text.startswith(('负', '-')):
        return -number(text[1:], colloquial=colloquial)
    # Recurse at the largest section, preserving e.g. 一亿二千万 / 2.5万 / 一万亿.
    for unit, scale in (('亿', 100000000), ('万', 10000)):
        if unit in text:
            if text.count(unit) != 1:
                raise ValueError('repeated section unit')
            left, right = text.split(unit)
            if not left:
                raise ValueError('missing quantity before section unit')
            result = number(left, colloquial=colloquial) * scale
            if right:
                if colloquial and len(right) == 1 and right in DIGITS and DIGITS[right] != 0:
                    result += DIGITS[right] * (scale // 10)
                elif len(right) == 1 and right in DIGITS and DIGITS[right] != 0:
                    raise ValueError('ambiguous colloquial number; spell out the unit')
                else:
                    result += number(right, colloquial=colloquial)
            return result
    if '点' in text:
        left, right = text.split('点', 1)
        if not right or any(c not in DIGITS for c in right):
            raise ValueError('invalid decimal digits')
        return number(left or '零') + Decimal('0.' + ''.join(str(DIGITS[c]) for c in right))
    if all(c in DIGITS for c in text):
        return Decimal(''.join(str(DIGITS[c]) for c in text))
    total, pending, previous_unit, last_unit, zero_after_unit = 0, '', 10000, 1, False
    for c in text:
        if c in DIGITS or c.isascii() and c.isdigit():
            value = DIGITS[c] if c in DIGITS else int(c)
            pending += str(value)
            if value == 0:
                zero_after_unit = True
        elif c in UNITS:
            unit = UNITS[c]
            if unit >= previous_unit:
                raise ValueError('units must descend')
            if not pending and not (unit == 10 and total == 0):
                raise ValueError('missing digit before unit')
            total += int(pending or '1') * unit
            pending, previous_unit, last_unit, zero_after_unit = '', unit, unit, False
        else:
            raise ValueError('not a number: ' + text)
    if pending:
        tail = int(pending)
        if len(pending) == 1 and last_unit >= 100 and tail and not zero_after_unit:
            if not colloquial:
                raise ValueError('ambiguous colloquial number; spell out the unit')
            tail *= last_unit // 10
        total += tail
    return Decimal(total)


def numeric(text, *, colloquial=True):
    """Compatibility helper: JSON-safe int/float, None for uncertain quantities."""
    try:
        value = number(text, colloquial=colloquial)
        return int(value) if value == value.to_integral_value() else float(value)
    except (ValueError, InvalidOperation, OverflowError):
        return None
