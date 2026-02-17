# utils/datetime.py
from datetime import datetime

def parse_date_input(date_str: str) -> str | None:
    """
    Преобразует строку с датой в формат "YYYY-MM-DD".
    Поддерживает: ДД-ММ-ГГГГ, ГГГГ-ММ-ДД, ДД.ММ.ГГГГ, ГГГГ.ММ.ДД
    """
    date_str = date_str.strip()
    formats = ["%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y", "%Y.%m.%d"]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            if 2000 <= dt.year <= 2100:
                return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None

def format_date_display(date_str: str) -> str:
    """Преобразует YYYY-MM-DD → DD-MM-YYYY"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%d-%m-%Y")
    except:
        return date_str