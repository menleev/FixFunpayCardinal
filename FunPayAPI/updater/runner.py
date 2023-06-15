from __future__ import annotations
from typing import TYPE_CHECKING, Generator
if TYPE_CHECKING:
    from ..account import Account

import json
import logging
from bs4 import BeautifulSoup

from ..common import exceptions
from .events import *


logger = logging.getLogger("FunPayAPI.runner")


class Runner:
    """
    Класс для получения новых событий FunPay.
    """
    def __init__(self, account: Account, disable_message_requests: bool = False,
                 disabled_order_requests: bool = False):
        """
        :param account: экземпляр аккаунта (должен быть инициализирован с помощью метода Account.get()).
        :param disable_message_requests: отключить ли запросы для получения истории чатов?
            Если True, Runner.listen() не будет возвращать события events.NewMessageEvent.
            Из событий, связанных с чатами, будут возвращаться следующие события:
            events.InitialChatEvent,
            events.ChatsListChangedEvent,
            events.LastChatMessageChangedEvent.
        :param disabled_order_requests: отключить ли запросы для получения списка заказов?
            Если True, Runner.listen() не будет возвращать события events.InitialOrderEvent, events.NewOrderEvent,
            events.OrderStatusChangedEvent.
            Из событий, связанных с заказами, будет возвращаться только событие events.OrdersListChangedEvent.
        """
        # todo добавить события и исключение событий о новых покупках (не продажах!)
        if not account.is_initiated():
            raise exceptions.AccountNotInitiatedError()
        if account.runner:
            raise Exception("К аккаунту уже привязан Runner!")  # todo

        self.make_msg_requests = False if disable_message_requests else True
        """Делать ли доп. запросы для получения всех новых сообщений изменившихся чатов?"""
        self.make_order_requests = False if disabled_order_requests else True
        """Делать ли доп запросы для получения все новых / изменившихся заказов?"""

        self.__first_request = True
        self.__last_msg_event_tag = utils.random_tag()
        self.__last_order_event_tag = utils.random_tag()

        self.saved_orders: dict[int, types.OrderShortcut] = {}
        """Сохраненные состояния заказов ({ID заказа: экземпляр types.OrderShortcut})."""
        self.last_messages: dict[int, str] = {}
        """ID последний сообщений ({ID чата: текст сообщения (до 250 символов)})."""
        self.by_bot_ids: dict[int, list[int]] = {}
        """ID сообщений, отправленных с помощью self.account.send_message ({ID чата: [ID сообщения, ...]})."""
        self.last_messages_ids: dict[int, int] = {}
        """ID последних сообщений в чатах ({ID чата: ID последнего сообщения})."""

        self.account = account
        """Экземпляр аккаунта, к которому привязан Runner."""
        self.account.runner = self

    def get_updates(self) -> dict:
        """
        Запрашивает список событий FunPay.

        :return: ответ FunPay.
        """
        orders = {
            "type": "orders_counters",
            "id": self.account.id,
            "tag": self.__last_order_event_tag,
            "data": False
        }
        chats = {
            "type": "chat_bookmarks",
            "id": self.account.id,
            "tag": self.__last_msg_event_tag,
            "data": False
        }
        payload = {
            "objects": json.dumps([orders, chats]),
            "request": False,
            "csrf_token": self.account.csrf_token
        }
        headers = {
            "accept": "*/*",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-requested-with": "XMLHttpRequest"
        }

        response = self.account.method("post", "https://funpay.com/runner/", headers, payload, raise_not_200=True)
        json_response = response.json()
        logger.debug(f"Получены данные о событиях: {json_response}")
        return json_response

    def parse_updates(self, updates: dict) -> list[InitialChatEvent | ChatsListChangedEvent |
                                                   LastChatMessageChangedEvent | NewMessageEvent | InitialOrderEvent |
                                                   OrdersListChangedEvent | NewOrderEvent | OrderStatusChangedEvent]:
        """
        Парсит ответ FunPay и создает события.

        :param updates: результат выполнения функции Runner.get_updates()

        :return: список событий.
        """
        events = []
        for obj in updates["objects"]:
            if obj.get("type") == "chat_bookmarks":
                events.extend(self.parse_chat_updates(obj))
            elif obj.get("type") == "orders_counters":
                events.extend(self.parse_order_updates(obj))

        if self.__first_request:
            self.__first_request = False
        return events

    def parse_chat_updates(self, obj) -> list[InitialChatEvent | ChatsListChangedEvent | LastChatMessageChangedEvent |
                                              NewMessageEvent]:
        """
        Парсит события, связанные с чатами.

        :param obj: словарь из результата выполнения функции Runner.get_updates(), где "type" == "chat_bookmarks".

        :return: список событий, связанных с чатами.
        """
        events, lcmc_events = [], []
        self.__last_msg_event_tag = obj.get("tag")
        parser = BeautifulSoup(obj["data"]["html"], "html.parser")
        chats = parser.find_all("a", {"class": "contact-item"})

        # Получаем все изменившиеся чаты
        for msg in chats:
            chat_id = int(msg["data-id"])
            last_msg_text = msg.find("div", {"class": "contact-item-message"}).text
            if self.last_messages.get(chat_id) == last_msg_text:
                continue
            unread = True if "unread" in msg.get("class") else False
            chat_with = msg.find("div", {"class": "media-user-name"}).text
            chat_obj = types.ChatShortcut(chat_id, chat_with, last_msg_text, unread, str(msg))
            self.account.add_chats([chat_obj])
            self.last_messages[chat_id] = last_msg_text

            if self.__first_request:
                events.append(InitialChatEvent(self.__last_msg_event_tag, chat_obj))
                continue
            lcmc_events.append(LastChatMessageChangedEvent(self.__last_msg_event_tag, chat_obj))

        if lcmc_events:
            events.append(ChatsListChangedEvent(self.__last_msg_event_tag))

        if not self.make_msg_requests:
            events.extend(lcmc_events)
            return events

        while lcmc_events:
            chats_pack = lcmc_events[:10]
            del lcmc_events[:10]
            chats_data = {i.chat.id: i.chat.name for i in chats_pack}
            new_msg_events = self.generate_new_message_events(chats_data)
            for i in chats_pack:
                events.append(i)
                if new_msg_events.get(i.chat.id):
                    events.extend(new_msg_events[i.chat.id])
        return events

    def generate_new_message_events(self, chats_data: dict[int, str]) -> dict[int, list[NewMessageEvent]]:
        """
        Получает историю переданных чатов и генерирует NewMessageEvent'ы.

        :param chats_data: ID чатов и никнеймы собеседников (None, если никнейм неизвестен)
            Например: {48392847: "SLLMK", 58392098: "Amongus", 38948728: None}

        :return: словарь с NewMessageEvent'ами в формате {ID чата: [список событий]}
        """
        attempts = 3
        while attempts:
            attempts -= 1
            try:
                chats_messages = self.account.get_chats_histories(chats_data)
                break
            except exceptions.RequestFailedError as e:
                logger.error(e)
            except:
                logger.error(f"Не удалось получить истории чатов {list(chats_data.keys())}.")
                logger.debug("TRACEBACK", exc_info=True)
            time.sleep(1)
        else:
            logger.error(f"Не удалось получить истории чатов {list(chats_data.keys())}: превышено кол-во попыток.")
            return {}

        result = {}
        for chat_id in chats_messages:
            messages = chats_messages[chat_id]
            result[chat_id] = []
            self.by_bot_ids[chat_id] = [] if not self.by_bot_ids.get(chat_id) else self.by_bot_ids[chat_id]

            # Удаляем все сообщения, у которых ID меньше сохраненного последнего сообщения
            if self.last_messages_ids.get(chat_id):
                messages = [i for i in messages if i.id > self.last_messages_ids[chat_id]]
            if not messages:
                continue

            # Отмечаем все сообщения, отправленные с помощью Account.send_message()
            if self.by_bot_ids.get(chat_id):
                for i in messages:
                    if i.id in self.by_bot_ids[chat_id]:
                        i.by_bot = True

            stack = MessageEventsStack()

            # если в runner'е нет сохраненного ID последнего сообщения, сохраняем ID последнего сообщения и возвращаем
            # только 1 событие (нового последнего сообщения).
            if not self.last_messages_ids.get(chat_id):
                self.last_messages_ids[chat_id] = messages[-1].id  # Перезаписываем ID последнего сообщение
                last_message = messages[-1]
                event = NewMessageEvent(self.__last_msg_event_tag, last_message, stack)
                stack.add_events([event])
                result[chat_id] = [event]
                # Чистим игнор. ID, которые меньше сохраненного ID последнего сообщения, дабы не забивать память.
                self.by_bot_ids[chat_id] = [i for i in self.by_bot_ids[chat_id] if i >
                                            self.last_messages_ids[chat_id]]
                continue

            self.last_messages_ids[chat_id] = messages[-1].id  # Перезаписываем ID последнего сообщение
            self.by_bot_ids[chat_id] = [i for i in self.by_bot_ids[chat_id] if i >
                                        self.last_messages_ids[chat_id]]

            for msg in messages:
                event = NewMessageEvent(self.__last_msg_event_tag, msg, stack)
                stack.add_events([event])
                result[chat_id].append(event)
        return result

    def parse_order_updates(self, obj) -> list[InitialOrderEvent | OrdersListChangedEvent | NewOrderEvent |
                                               OrderStatusChangedEvent]:
        """
        Парсит события, связанные с продажами.

        :param obj: словарь из результата выполнения функции Runner.get_updates(), где "type" == "orders_counters".

        :return: список событий, связанных с продажами.
        """
        events = []
        self.__last_order_event_tag = obj.get("tag")
        if not self.__first_request:
            events.append(OrdersListChangedEvent(self.__last_order_event_tag,
                                                 obj["data"]["buyer"], obj["data"]["seller"]))
        if not self.make_order_requests:
            return events

        attempts = 3
        while attempts:
            attempts -= 1
            try:
                orders_list = self.account.get_sales()
                break
            except exceptions.RequestFailedError as e:
                logger.error(e)
            except:
                logger.error("Не удалось обновить список ордеров.")
                logger.debug("TRACEBACK", exc_info=True)
            time.sleep(1)
        else:
            logger.error("Не удалось обновить список продаж: превышено кол-во попыток.")
            return events

        for order in orders_list[1]:
            if order.id not in self.saved_orders:
                if self.__first_request:
                    events.append(InitialOrderEvent(self.__last_order_event_tag, order))
                else:
                    events.append(NewOrderEvent(self.__last_order_event_tag, order))
                    if order.status == types.OrderStatuses.CLOSED:
                        events.append(OrderStatusChangedEvent(self.__last_order_event_tag, order))
                self.update_order(order)

            elif order.status != self.saved_orders[order.id].status:
                events.append(OrderStatusChangedEvent(self.__last_order_event_tag, order))
                self.update_order(order)
        return events

    def update_last_message(self, chat_id: int, message_text: str | None):
        """
        Обновляет сохраненный текст последнего сообщения чата.

        :param chat_id: ID чата.
        :param message_text: текст сообщения (если None - заменяется за "Изображение").
        """
        if message_text is None:
            message_text = "Изображение"
        self.last_messages[chat_id] = message_text[:250]

    def update_order(self, order: types.OrderShortcut):
        """
        Обновляет сохраненное состояние переданного заказа.

        :param order: экземпляр класса заказа, которого нужно обновить
        """
        self.saved_orders[order.id] = order

    def mark_as_by_bot(self, chat_id: int, message_id: int):
        """
        Помечает сообщение с переданным ID, как отправленный с помощью self.account.send_message.

        :param chat_id: ID чата.
        :param message_id: ID сообщения.
        """
        if self.by_bot_ids.get(chat_id) is None:
            self.by_bot_ids[chat_id] = [message_id]
        else:
            self.by_bot_ids[chat_id].append(message_id)

    def listen(self, requests_delay: int | float = 6.0,
               ignore_exceptions: bool = True) -> Generator[InitialChatEvent | ChatsListChangedEvent |
                                                            LastChatMessageChangedEvent | NewMessageEvent |
                                                            InitialOrderEvent | OrdersListChangedEvent | NewOrderEvent |
                                                            OrderStatusChangedEvent]:
        """
        Бесконечно отправляет запросы для получения новых событий.

        :param requests_delay: задержка между запросами (в секундах).

        :param ignore_exceptions: игнорировать ошибки?
        """
        while True:
            try:
                updates = self.get_updates()
                events = self.parse_updates(updates)
                for event in events:
                    yield event
            except Exception as e:
                if not ignore_exceptions:
                    raise e
                else:
                    logger.error("Произошла ошибка при получении событий. "
                                 "(ничего страшного, если это сообщение появляется нечасто).")
                    logger.debug("TRACEBACK", exc_info=True)
            time.sleep(requests_delay)
