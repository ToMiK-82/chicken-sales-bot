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

def _format_month(month_str: str) -> str:
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


def predict_next_month(data):
    n = len(data)
    if n < 2: return data[-1][1] if data else 0
    X = list(range(n))
    Y = [row[1] for row in data]
    sum_x, sum_y = sum(X), sum(Y)
    sum_xy = sum(x * y for x, y in zip(X, Y))
    sum_x2 = sum(x * x for x in X)
    denom = n * sum_x2 - sum_x ** 2
    if denom == 0: return Y[-1]
    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n
    return max(0, slope * n + intercept)


async def send_charts(
    ordered: List[Tuple[str, int]] = None,
    confirmed: List[Tuple[str, int]] = None,
    issued_qty: List[Tuple[str, int]] = None,
    rejections: List[Tuple[str, int]] = None,
    unique_clients: List[Tuple[str, int]] = None,
    year: str = "Неизвестно"
) -> Optional[io.BytesIO]:
    """
    Строит график динамики по нескольким метрикам.
    Возвращает io.BytesIO с изображением PNG.
    """
    # Собираем все месяцы
    all_months = set()
    for data in [ordered, confirmed, issued_qty, rejections, unique_clients]:
        if data:
            all_months.update(row[0] for row in data)

    if not all_months:
        return None

    months_str = sorted(all_months)
    months_int = list(range(1, len(months_str) + 1))

    def get_data(data_list: List[Tuple[str, int]]) -> List[int]:
        d: Dict[str, int] = dict(data_list) if data_list else {}
        return [d.get(m, 0) for m in months_str]

    # Получаем данные
    ord_data = get_data(ordered)
    conf_data = get_data(confirmed)
    issued_data = get_data(issued_qty)
    rej_data = get_data(rejections)
    clients_data = get_data(unique_clients)

    # Проверяем, есть ли хоть что-то для отображения
    if not any(ord_data + conf_data + issued_data + rej_data + clients_data):
        return None

    # Создаём график
    fig, ax1 = plt.subplots(figsize=(10, 5))

    # Левая ось: заказы, отказы, выдачи
    if any(ord_data):
        ax1.plot(months_int, ord_data, label="📥 Заказано", color="orange", marker="s", linewidth=2)
    if any(conf_data):
        ax1.plot(months_int, conf_data, label="✅ Подтверждено", color="green", marker="o", linewidth=2)
    if any(issued_data):
        ax1.plot(months_int, issued_data, label="🚚 Выдано (шт)", color="blue", marker="^", linewidth=2)
    if any(rej_data):
        ax1.plot(months_int, rej_data, label="❌ Отказы", color="red", marker="x", linewidth=2)

    ax1.set_ylabel("Количество", color="black")
    ax1.tick_params(axis='y', labelcolor="black")

    # Правая ось: клиенты
    ax2 = None
    if any(clients_data):
        ax2 = ax1.twinx()
        ax2.plot(months_int, clients_data, label="👥 Клиенты", color="purple", linestyle="--", marker="D", linewidth=2)
        ax2.set_ylabel("Клиенты", color="purple")
        ax2.tick_params(axis='y', labelcolor="purple")

    # Оформление
    ax1.set_title(f"Статистика за {year}", fontsize=14, pad=20)
    ax1.set_xticks(months_int)
    ax1.set_xticklabels([m.split('-')[1] for m in months_str])  # Только месяц (например, "Мар")
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
