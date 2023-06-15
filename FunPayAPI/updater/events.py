from __future__ import annotations
import time
from enum import Enum
from ..common import utils
from .. import types


class EventTypes(Enum):
    """
    Класс, в котором хранятся все типы событий FunPayAPI.
    """
    INITIAL_CHAT = 0
    """Обнаружен чат (при первом запросе Runner'а)."""

    CHATS_LIST_CHANGED = 1
    """Список чатов и/или последнее сообщение одного/нескольких чатов изменилось."""

    LAST_CHAT_MESSAGE_CHANGED = 2
    """В чате изменилось последнее сообщение."""

    NEW_MESSAGE = 3
    """Обнаружено новое сообщение в истории чата."""

    INITIAL_ORDER = 4
    """Обнаружен заказ (при первом запросе Runner'а)."""

    ORDERS_LIST_CHANGED = 5
    """Список заказов и/или статус одного/нескольких заказов изменился."""

    NEW_ORDER = 6
    """Новый заказ."""

    ORDER_STATUS_CHANGED = 7
    """Статус заказа изменился."""


class BaseEvent:
    """
    Базовый класс события.
    """
    def __init__(self, runner_tag: str, event_type: EventTypes, event_time: int | float | None = None):
        """
        :param runner_tag: тег Runner'а.
        :param event_type: тип события.
        :param event_time: время события (лучше не указывать, будет генерироваться автоматически).
        """
        self.runner_tag = runner_tag
        self.type = event_type
        self.time = event_time if event_type is not None else time.time()


class InitialChatEvent(BaseEvent):
    """
    Класс события: обнаружен чата при первом запросе Runner'а.
    """
    def __init__(self, runner_tag: str, chat_obj: types.ChatShortcut):
        super(InitialChatEvent, self).__init__(runner_tag, EventTypes.INITIAL_CHAT)
        self.chat = chat_obj


class ChatsListChangedEvent(BaseEvent):
    """
    Класс события: список чатов и / или содержимое одного / нескольких чатов изменилось.
    """
    def __init__(self, runner_tag: str):
        super(ChatsListChangedEvent, self).__init__(runner_tag, EventTypes.CHATS_LIST_CHANGED)
        # todo: добавить список всех чатов.


class LastChatMessageChangedEvent(BaseEvent):
    """
    Класс события: последнее сообщение в чате изменилось.
    """
    def __init__(self, runner_tag: str, chat_obj: types.ChatShortcut):
        super(LastChatMessageChangedEvent, self).__init__(runner_tag, EventTypes.LAST_CHAT_MESSAGE_CHANGED)
        self.chat = chat_obj


class NewMessageEvent(BaseEvent):
    """
    Класс события: в истории чата обнаружено новое сообщение.
    """
    def __init__(self, runner_tag: str, message_obj: types.Message, stack: MessageEventsStack | None = None):
        super(NewMessageEvent, self).__init__(runner_tag, EventTypes.NEW_MESSAGE)
        self.message = message_obj
        self.stack = stack


class MessageEventsStack:
    """
    Класс, описывающий стэк событий новых сообщений.
    Нужен для того, чтобы объединять события новых сообщений от одного пользователя и одного запроса.
    """
    def __init__(self):
        self.__id = utils.random_tag()
        self.__stack = []

    def add_events(self, messages: list[NewMessageEvent]):
        self.__stack.extend(messages)

    def get_stack(self) -> list[NewMessageEvent]:
        return self.__stack

    def id(self) -> str:
        return self.__id


class InitialOrderEvent(BaseEvent):
    """
    Класс события: обнаружен заказ при первом запросе Runner'а.
    """
    def __init__(self, runner_tag: str, order_obj: types.OrderShortcut):
        super(InitialOrderEvent, self).__init__(runner_tag, EventTypes.INITIAL_ORDER)
        self.order = order_obj


class OrdersListChangedEvent(BaseEvent):
    """
    Класс события: список заказов и/или статус одного/нескольких заказов изменился.
    """
    def __init__(self, runner_tag: str, purchases: int, sales: int):
        super(OrdersListChangedEvent, self).__init__(runner_tag, EventTypes.ORDERS_LIST_CHANGED)
        self.purchases = purchases
        self.sales = sales


class NewOrderEvent(BaseEvent):
    """
    Класс события: в списке заказов обнаружен новый заказ.
    """
    def __init__(self, runner_tag: str, order_obj: types.OrderShortcut):
        super(NewOrderEvent, self).__init__(runner_tag, EventTypes.NEW_ORDER)
        self.order = order_obj


class OrderStatusChangedEvent(BaseEvent):
    """
    Класс события: статус заказа изменился.
    """
    def __init__(self, runner_tag: str, order_obj: types.OrderShortcut):
        super(OrderStatusChangedEvent, self).__init__(runner_tag, EventTypes.ORDER_STATUS_CHANGED)
        self.order = order_obj
