from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    import FunPayAPI.account

import FunPayAPI.types

from datetime import datetime
import Utils.exceptions
import itertools
import psutil
import json
import sys
import os
import re


PHOTO_RE = re.compile(r'\$photo=[\d]+')


def count_products(products_file_path: str) -> int:
    """
    Считает кол-во товара в указанном файле.

    :param products_file_path: путь до файла с товарами.

    :return: кол-во товара в указанном файле.
    """
    if not os.path.exists(products_file_path):
        return 0
    with open(products_file_path, "r", encoding="utf-8") as f:
        products = f.read()
    products = products.split("\n")
    products = list(itertools.filterfalse(lambda el: not el, products))
    return len(products)


def cache_block_list(block_list: list[str]) -> None:
    """
    Кэширует черный список.

    :param block_list: черный список.
    """
    if not os.path.exists("storage/cache"):
        os.makedirs("storage/cache")

    with open("storage/cache/block_list.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(block_list, indent=4))


def load_block_list() -> list[str]:
    """
    Загружает черный список.

    :return: черный список.
    """
    if not os.path.exists("storage/cache/block_list.json"):
        return []

    with open("storage/cache/block_list.json", "r", encoding="utf-8") as f:
        block_list = f.read()

        try:
            block_list = json.loads(block_list)
        except json.decoder.JSONDecodeError:
            return []
        return block_list


def cache_disabled_plugins(disabled_plugins: list[str]) -> None:
    """
    Кэширует UUID отключенных плагинов.

    :param disabled_plugins: список UUID отключенных плагинов.
    """
    if not os.path.exists("storage/cache"):
        os.makedirs("storage/cache")

    with open("storage/cache/disabled_plugins.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(disabled_plugins))


def load_disabled_plugins() -> list[str]:
    """
    Загружает список UUID отключенных плагинов из кэша.

    :return: список UUID отключенных плагинов.
    """
    if not os.path.exists("storage/cache/disabled_plugins.json"):
        return []

    with open("storage/cache/disabled_plugins.json", "r", encoding="utf-8") as f:
        try:
            return json.loads(f.read())
        except json.decoder.JSONDecodeError:
            return []


def cache_old_users(old_users: dict):
    """
    Сохраняет в кэш список пользователей, которые уже писали на аккаунт.
    """
    if not os.path.exists("storage/cache"):
        os.makedirs("storage/cache")
    with open(f"storage/cache/old_users.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(old_users, ensure_ascii=False))


def load_old_users() -> list[str]:
    """
    Загружает из кэша список пользователей, которые уже писали на аккаунт.

    :return: список никнеймов пользователей.
    """
    if not os.path.exists(f"storage/cache/old_users.json"):
        return []
    with open(f"storage/cache/old_users.json", "r", encoding="utf-8") as f:
        users = f.read()
    return json.loads(users)


def create_greetings(account: FunPayAPI.account.Account):
    """
    Генерирует приветствие для вывода в консоль после загрузки данных о пользователе.
    """
    current_time = datetime.now()
    if current_time.hour < 4:
        greetings = "Какая прекрасная ночь"
    elif current_time.hour < 12:
        greetings = "Доброе утро"
    elif current_time.hour < 17:
        greetings = "Добрый день"
    else:
        greetings = "Добрый вечер"

    currency = f" {account.currency}" if account.currency is not None else ""

    lines = [
        f"* {greetings}, $CYAN{account.username}.",
        f"* Ваш ID: $YELLOW{account.id}.",
        f"* Ваш текущий баланс: $YELLOW{account.balance}{currency}.",
        f"* Текущие незавершенные сделки: $YELLOW{account.active_sales}.",
        f"* Удачной торговли!"
    ]

    length = 40
    greetings_text = f"\n{'-'*length}\n"
    for line in lines:
        greetings_text += line + " "*(length - len(line.replace("$CYAN", "").replace("$YELLOW", "")) - 1) + "$RESET*\n"
    greetings_text += f"{'-'*length}\n"
    return greetings_text


def time_to_str(time_: int):
    """
    Конвертирует число в строку формата "Хд Хч Хмин Хсек"

    :param time_: число для конвертации.

    :return: строку-время.
    """
    days = time_ // 86400
    hours = (time_ - days * 86400) // 3600
    minutes = (time_ - days * 86400 - hours * 3600) // 60
    seconds = time_ - days * 86400 - hours * 3600 - minutes * 60

    if not any([days, hours, minutes, seconds]):
        return "0 сек"
    time_str = ""
    if days:
        time_str += f"{days}д"
    if hours:
        time_str += f" {hours}ч"
    if minutes:
        time_str += f" {minutes}мин"
    if seconds:
        time_str += f" {seconds}сек"
    return time_str.strip()


def get_month_name(month_number: int) -> str:
    """
    Возвращает название месяца в родительном падеже.

    :param month_number: номер месяца.

    :return: название месяца в родительном падеже.
    """
    months = [
        "Января", "Февраля", "Марта",
        "Апреля", "Мая", "Июня",
        "Июля", "Августа", "Сентября",
        "Октября", "Ноября", "Декабря"
    ]
    if month_number > len(months):
        return months[0]
    return months[month_number-1]


def get_products(path: str, amount: int = 1) -> list[list[str] | int] | None:
    """
    Берет из товарного файла товар/-ы, удаляет их из товарного файла.

    :param path: путь до файла с товарами.
    :param amount: кол-во товара.

    :return: [[Товар/-ы], оставшееся кол-во товара]
    """
    with open(path, "r", encoding="utf-8") as f:
        products = f.read()

    products = products.split("\n")

    # Убираем пустые элементы
    products = list(itertools.filterfalse(lambda el: not el, products))

    if not products:
        raise Utils.exceptions.NoProductsError(path)

    elif len(products) < amount:
        raise Utils.exceptions.NotEnoughProductsError(path, len(products), amount)

    got_products = products[:amount]
    save_products = products[amount:]
    amount = len(save_products)

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(save_products))

    return [got_products, amount]


def add_products(path: str, products: list[str]) -> None:
    """
    Добавляет товары в файл с товарами.

    :param path: путь до файла с товарами.
    :param products: товары.

    :return:
    """
    with open(path, "r", encoding="utf-8") as f:
        old_products = f.read()

    old_products = old_products.split("\n")
    old_products.extend(products)

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(old_products))


def format_msg_text(text: str, obj: FunPayAPI.types.Message | FunPayAPI.types.ChatShortcut) -> str:
    """
    Форматирует текст, подставляя значения переменных, доступных для MessageEvent.

    :param text: текст для форматирования.
    :param obj: экземпляр types.Message или types.ChatShortcut.

    :return: форматированый текст.
    """
    date_obj = datetime.now()
    month_name = get_month_name(date_obj.month)
    date = date_obj.strftime("%d.%m.%Y")
    str_date = f"{date_obj.day} {month_name}"
    str_full_date = str_date + f" {date_obj.year} года"

    time_ = date_obj.strftime("%H:%M")
    time_full = date_obj.strftime("%H:%M:%S")

    username = obj.author if isinstance(obj, FunPayAPI.types.Message) else obj.name
    message_text = obj.text if isinstance(obj, FunPayAPI.types.Message) else obj.last_message_text
    chat_id = str(obj.chat_id) if isinstance(obj, FunPayAPI.types.Message) else str(obj.id)

    variables = {
        "$full_date_text": str_full_date,
        "$date_text": str_date,
        "$date": date,
        "$time": time_,
        "$full_time": time_full,
        "$username": username,
        "$message_text": message_text,
        "$chat_id": chat_id
    }

    for var in variables:
        text = text.replace(var, variables[var])
    return text


def format_order_text(text: str, order: FunPayAPI.types.OrderShortcut | FunPayAPI.types.Order) -> str:
    """
    Форматирует текст, подставляя значения переменных, доступных для Order.

    :param text: текст для форматирования.
    :param order: экземпляр Order.

    :return: форматированый текст.
    """
    date_obj = datetime.now()
    month_name = get_month_name(date_obj.month)
    date = date_obj.strftime("%d.%m.%Y")
    str_date = f"{date_obj.day} {month_name}"
    str_full_date = str_date + f" {date_obj.year} года"

    time_ = date_obj.strftime("%H:%M")
    time_full = date_obj.strftime("%H:%M:%S")

    variables = {
        "$full_date_text": str_full_date,
        "$date_text": str_date,
        "$date": date,
        "$time": time_,
        "$full_time": time_full,
        "$username": order.buyer_username,
        "$order_desc": order.description if isinstance(order, FunPayAPI.types.OrderShortcut) else order.short_description if order.short_description else "",
        "$order_title": order.description if isinstance(order, FunPayAPI.types.OrderShortcut) else order.short_description if order.short_description else "",
        "$order_id": order.id
    }

    for var in variables:
        text = text.replace(var, variables[var])
    return text


def restart_program():
    """
    Полный перезапуск FPC.
    """
    python = sys.executable
    os.execl(python, python, *sys.argv)
    try:
        process = psutil.Process()
        for handler in process.open_files():
            os.close(handler.fd)
        for handler in process.connections():
            os.close(handler.fd)
    except:
        pass


def shut_down():
    """
    Полное отключение FPC.
    """
    try:
        process = psutil.Process()
        process.terminate()
    except:
        pass