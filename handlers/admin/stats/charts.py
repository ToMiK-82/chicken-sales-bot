# handlers/admin/stats/charts.py

"""
Функции построения графиков.
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io

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


async def send_charts(breed_sales, total_orders, rejections, unique_clients, year):
    months_str = sorted(set(
        [row[0] for row in total_orders + rejections + unique_clients if row]
    ))
    if not months_str: return None
    months_int = list(range(1, len(months_str) + 1))

    def get_data(data_list):
        d = dict(data_list)
        return [d.get(m, 0) for m in months_str]

    orders = get_data(total_orders)
    rejects = get_data(rejections)
    clients = get_data(unique_clients)

    if not any(orders) and not any(rejects) and not any(clients): return None

    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.plot(months_int, orders, label="Заказы", color="green", marker="o", linewidth=2)
    ax1.plot(months_int, rejects, label="Отказы", color="red", marker="x", linewidth=2)
    ax1.set_ylabel("Заказы / Отказы", color="black")
    ax1.tick_params(axis='y', labelcolor="black")

    ax2 = ax1.twinx()
    ax2.plot(months_int, clients, label="Клиенты", color="purple", linestyle="--", marker="s", linewidth=2)
    ax2.set_ylabel("Клиенты", color="purple")
    ax2.tick_params(axis='y', labelcolor="purple")

    ax1.set_title(f"Статистика за {year}", fontsize=14, pad=20)
    ax1.set_xticks(months_int)
    ax1.set_xticklabels([m.split('-')[1] for m in months_str])
    ax1.legend(loc="upper left")
    ax2.legend(loc="upper right")
    plt.grid(True, axis='y', alpha=0.3)
    plt.tight_layout()

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
