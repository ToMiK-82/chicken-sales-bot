"""
Функции построения графиков.
✅ Поддерживает:
- Заказано (pending + active)
- Подтверждено (active + issued)
- Выдано (в штуках)
- Отказы
- Уникальные клиенты
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
from typing import List, Tuple, Optional, Dict

# --- Константы ---
COLORS = {
    "ordered": "#FFA500",      # orange
    "confirmed": "#2E8B57",    # seagreen
    "issued": "#1E90FF",       # dodgerblue
    "rejections": "#DC143C",   # crimson
    "clients": "#800080"       # purple
}

DataList = List[Tuple[str, int]]


def _format_month(month_str: str) -> str:
    """Преобразует YYYY-MM → 'Мар 2024'"""
    months = {
        '01': 'Янв', '02': 'Фев', '03': 'Мар', '04': 'Апр',
        '05': 'Май', '06': 'Июн', '07': 'Июл', '08': 'Авг',
        '09': 'Сен', '10': 'Окт', '11': 'Ноя', '12': 'Дек'
    }
    try:
        year, month = month_str.split('-')
        return f"{months.get(month, month)} {year}"
    except:
        return month_str


def predict_next_month(data: DataList) -> float:
    """
    Простая линейная регрессия для прогноза следующего значения.
    Возвращает float >= 0.
    """
    n = len(data)
    if n < 2:
        return data[-1][1] if data else 0

    X = list(range(n))
    Y = [row[1] for row in data]
    sum_x, sum_y = sum(X), sum(Y)
    sum_xy = sum(x * y for x, y in zip(X, Y))
    sum_x2 = sum(x * x for x in X)
    denom = n * sum_x2 - sum_x ** 2

    if denom == 0:
        return Y[-1]

    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n
    prediction = slope * n + intercept
    return max(0, prediction)


async def send_charts(
    ordered: DataList = None,
    confirmed: DataList = None,
    issued_qty: DataList = None,
    rejections: DataList = None,
    unique_clients: DataList = None,
    year: str = "Неизвестно"
) -> Optional[io.BytesIO]:
    """
    Строит график динамики по нескольким метрикам.
    Возвращает io.BytesIO с изображением PNG.
    """
    # Собираем и сортируем все месяцы
    all_months = set()
    for data in [ordered, confirmed, issued_qty, rejections, unique_clients]:
        if data:
            all_months.update(row[0] for row in data)

    if not all_months:
        return None

    months_str = sorted(all_months)  # YYYY-MM
    months_pos = list(range(1, len(months_str) + 1))

    def get_data(data_list: DataList) -> List[int]:
        d = dict(data_list or [])
        return [d.get(m, 0) for m in months_str]

    # Получаем данные
    ord_data = get_data(ordered)
    conf_data = get_data(confirmed)
    issued_data = get_data(issued_qty)
    rej_data = get_data(rejections)
    clients_data = get_data(unique_clients)

    # Проверяем, есть ли что рисовать
    if not any(ord_data + conf_data + issued_data + rej_data + clients_data):
        return None

    # Создаём график
    fig, ax1 = plt.subplots(figsize=(12, 6))

    # Левая ось: заказы, выдачи, отказы
    if any(ord_data):
        ax1.plot(months_pos, ord_data, label="📥 Заказано", color=COLORS["ordered"],
                 marker="s", linewidth=2)
    if any(conf_data):
        ax1.plot(months_pos, conf_data, label="✅ Подтверждено", color=COLORS["confirmed"],
                 marker="o", linewidth=2)
    if any(issued_data):
        ax1.plot(months_pos, issued_data, label="🚚 Выдано (шт)", color=COLORS["issued"],
                 marker="^", linewidth=2)
    if any(rej_data):
        ax1.plot(months_pos, rej_data, label="❌ Отказы", color=COLORS["rejections"],
                 marker="x", linewidth=2)

    ax1.set_ylabel("Количество", color="black")
    ax1.tick_params(axis='y', labelcolor="black")

    # Правая ось: уникальные клиенты
    ax2 = None
    if any(clients_data):
        ax2 = ax1.twinx()
        ax2.plot(months_pos, clients_data, label="👥 Уникальные клиенты", color=COLORS["clients"],
                 linestyle="--", marker="D", linewidth=2)
        ax2.set_ylabel("Клиенты", color=COLORS["clients"])
        ax2.tick_params(axis='y', labelcolor=COLORS["clients"])

    # Оформление
    ax1.set_title(f"📊 Статистика за {year}", fontsize=16, pad=20)
    ax1.set_xticks(months_pos)
    ax1.set_xticklabels([_format_month(m) for m in months_str], rotation=0)
    ax1.legend(loc="upper left")
    if ax2:
        ax2.legend(loc="upper right")

    plt.grid(True, axis='y', alpha=0.3)
    plt.tight_layout()

    # Сохраняем в буфер
    buf = io.BytesIO()
    try:
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
        buf.seek(0)
    except Exception as e:
        plt.close()
        buf.close()
        return None
    finally:
        plt.close()

    return buf
