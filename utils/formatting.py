# utils/formatting.py
from datetime import datetime
from typing import Optional
import re

def format_phone(phone: Optional[str]) -> str:
    """
    Форматирует телефон в единый вид: +7 XXX XXX-XX-XX
    Поддерживает:
        - +79787292469
        - 89787292469
        - +7 (978) 729-24-69
        - 8 978 729-24-69
    """
    if not phone:
        return ""

    # Удаляем всё, кроме цифр
    digits = ''.join(filter(str.isdigit, phone))

    # Обработка 8 или 7 в начале
    if len(digits) == 11:
        if digits.startswith("8"):
            digits = "7" + digits[1:]
        if digits.startswith("7"):
            return f"+7 {digits[1:4]} {digits[4:7]}-{digits[7:9]}-{digits[9:]}"

    return phone.strip()


def parse_date_input(date_str: Optional[str]) -> str | None:
    """
    Парсит строку с датой и возвращает в формате 'YYYY-MM-DD'.
    Поддерживаемые форматы:
        - 01-12-2025
        - 2025-12-01
        - 01.12.2025
        - 2025.12.01
    Возвращает None, если не удалось распознать.
    """
    if not date_str or not isinstance(date_str, str):
        return None

    date_str = date_str.strip()
    formats = ["%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y", "%Y.%m.%d"]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            # Проверка: год в разумных пределах
            if 2000 <= dt.year <= 2100:
                return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def format_date_display(date_str: Optional[str]) -> str:
    """
    Форматирует дату из 'YYYY-MM-DD' в 'DD-MM-YYYY'.
    Если не удаётся — возвращает исходную строку.
    """
    if not date_str or not isinstance(date_str, str):
        return "—"

    try:
        dt = datetime.strptime(date_str.split()[0], "%Y-%m-%d")
        return dt.strftime("%d-%m-%Y")
    except Exception:
        return date_str