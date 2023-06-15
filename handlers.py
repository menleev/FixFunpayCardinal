"""
В данном модуле написаны хэндлеры для разных эвентов.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from cardinal import Cardinal

from FunPayAPI.types import MessageTypes, RaiseResponse, Message, OrderShortcut, Order
from FunPayAPI import exceptions, utils as fp_utils
from FunPayAPI.updater.events import *


from tg_bot import utils, keyboards
from Utils import cardinal_tools
from threading import Thread
import configparser
import logging
import time
import re

LAST_STACK_ID = ""


logger = logging.getLogger("FPC.handlers")


ORDER_HTML_TEMPLATE = """<a href="https://funpay.com/orders/DELIVERY_TEST/" class="tc-item info">
    <div class="tc-date">
        <div class="tc-date-time">сегодня, 00:00</div>
        <div class="tc-date-left">1 минуту назад</div>
    </div>

    <div class="tc-order">#DELIVERY_TEST</div>
    <div class="order-desc">
        <div>ТЕСТ АВТОВЫДАЧИ</div>
        <div class="text-muted">$lot_name</div>
    </div>

    <div class="tc-user">
        <div class="media media-user mt0 offline">
        <div class="media-left">
            <div class="avatar-photo pseudo-a" tabindex="0" data-href="https://funpay.com/users/000000/" style="background-image: url(https://s.funpay.com/s/avatar/6d/h3/6dh3m89zv8k90kwlj9bg.jpg);"></div>
        </div>
        <div class="media-body">
            <div class="media-user-name">
                <span class="pseudo-a" tabindex="0" data-href="https://funpay.com/users/000000/">$username</span>
            </div>
            <div class="media-user-status">был миллион лет назад</div>
        </div>
    </div>
        <div class="tc-status text-primary">Оплачен</div>
        <div class="tc-price text-nowrap tc-seller-sum">999999.0<span class="unit">₽</span></div>
</a>"""


AMOUNT_EXPRESSION = re.compile(r'\d+ шт\.')


# Новое сообщение (REGISTER_TO_NEW_MESSAGE)
def log_msg_handler(cardinal: Cardinal, event: NewMessageEvent):
    """
    Логирует полученное сообщение.
    """
    message_text, name, chat_id = str(event.message), event.message.chat_name, event.message.chat_id
    logger.info(f"$MAGENTA┌──$RESET Новое сообщение в переписке с пользователем $YELLOW{name} (node: {chat_id}):")

    for index, line in enumerate(message_text.split("\n")):
        if not index:
            logger.info(f"$MAGENTA└───> $CYAN{line}")
        else:
            logger.info(f"      $CYAN{line}")


def save_already_exists_chat_handler(cardinal: Cardinal, event: InitialChatEvent):
    """
    Кэширует существующие чаты (чтобы не отправлять приветственные сообщения).
    """
    if not cardinal.MAIN_CFG["Greetings"].getboolean("cacheInitChats"):
        return
    if event.chat.name not in cardinal.old_users:
        cardinal.old_users.append(event.chat.name)
        cardinal_tools.cache_old_users(cardinal.old_users)


def send_greetings_handler(cardinal: Cardinal, event: NewMessageEvent):
    """
    Отправляет приветственное сообщение.
    """
    if not cardinal.MAIN_CFG["Greetings"].getboolean("sendGreetings"):
        return

    obj = event.message
    chat_id, chat_name, message_text, message_type = obj.chat_id, obj.chat_name, str(obj), obj.type
    its_me = obj.author_id == cardinal.account.id
    if any([chat_name in cardinal.old_users, its_me, message_type != MessageTypes.NON_SYSTEM]):
        return

    def send_greetings():
        logger.info(f"Новый чат $YELLOW{chat_name}$RESET. Отправляю приветственное сообщение.")
        text = cardinal_tools.format_msg_text(cardinal.MAIN_CFG["Greetings"]["greetingsText"], obj)
        result = cardinal.send_message(chat_id, text, chat_name)
        if not result:
            logger.error(f"Не удалось отправить приветственное сообщение в чат $YELLOW{chat_name} (ID: {chat_id})$RESET.")
    Thread(target=send_greetings, daemon=True).start()


def add_old_user_handler(cardinal: Cardinal, event: NewMessageEvent):
    """
    Добавляет пользователя в список написавших.
    """
    chat_name = event.message.chat_name
    if chat_name in cardinal.old_users:
        return
    cardinal.old_users.append(chat_name)
    cardinal_tools.cache_old_users(cardinal.old_users)


def send_response_handler(cardinal: Cardinal, event: NewMessageEvent):
    """
    Проверяет, является ли сообщение командой, и если да, отправляет ответ на данную команду.
    """
    if not cardinal.MAIN_CFG["FunPay"].getboolean("autoResponse"):
        return

    obj, message_text = event.message, str(event.message)
    chat_id, chat_name, username = event.message.chat_id, event.message.chat_name, event.message.author

    if cardinal.MAIN_CFG["BlockList"].getboolean("blockResponse") and username in cardinal.block_list:
        return

    command = message_text.strip().lower()
    if command not in cardinal.AR_CFG:
        return

    def send_response():
        logger.info(f"Получена команда $YELLOW{command}$RESET "
                    f"в переписке с пользователем $YELLOW{chat_name} (ID чата: {chat_id}).")
        response_text = cardinal_tools.format_msg_text(cardinal.AR_CFG[command]["response"], obj)
        result = cardinal.send_message(chat_id, response_text, chat_name)
        if not result:
            logger.error(f"Не удалось отправить ответ на команду в чат с пользователем $YELLOW{chat_name}$RESET.")

    Thread(target=send_response, daemon=True).start()


def send_new_message_notification_handler(cardinal: Cardinal, event: NewMessageEvent) -> None:
    """
    Отправляет уведомление о новом сообщении в телеграм.
    """
    if not cardinal.telegram:
        return
    global LAST_STACK_ID
    if event.stack.id() == LAST_STACK_ID:
        return
    LAST_STACK_ID = event.stack.id()

    events = []
    not_my = False
    my = False
    fp = False
    bot = False
    for i in event.stack.get_stack():
        if i.message.author_id == 0:
            if int(cardinal.MAIN_CFG["NewMessageView"]["includeFPMessages"]):
                events.append(i)
                fp = True
        elif i.message.by_bot:
            if int(cardinal.MAIN_CFG["NewMessageView"]["includeBotMessages"]):
                events.append(i)
                bot = True
        elif i.message.author_id == cardinal.account.id:
            if int(cardinal.MAIN_CFG["NewMessageView"]["includeMyMessages"]):
                events.append(i)
                my = True
        else:
            events.append(i)
            not_my = True
    if not events:
        return

    if len([i for i in [my, fp, bot, not_my] if i]) == 1:
        if my and not cardinal.MAIN_CFG["NewMessageView"].getboolean("notifyOnlyMyMessages"):
            return
        elif fp and not cardinal.MAIN_CFG["NewMessageView"].getboolean("notifyOnlyFPMessages"):
            return
        elif bot and not cardinal.MAIN_CFG["NewMessageView"].getboolean("notifyOnlyBotMessages"):
            return

    text = ""
    last_message_author_id = -1
    last_by_bot = False
    for i in events:
        message_text = str(event.message)
        if message_text.strip().lower() in cardinal.AR_CFG.sections() and len(events) < 2:
            continue
        elif message_text.startswith("!автовыдача") and len(events) < 2:
            continue

        if i.message.author_id == last_message_author_id and i.message.by_bot == last_by_bot:
            author = ""
        elif i.message.author_id == cardinal.account.id:
            author = "<i><b>🤖 Вы (бот):</b></i> " if i.message.by_bot else "<i><b>🫵 Вы:</b></i> "
        elif i.message.author_id == 0:
            author = f"<i><b>🔵 {i.message.author}: </b></i>"
        elif i.message.author == i.message.chat_name:
            author = f"<i><b>👤 {i.message.author}: </b></i>"
        else:
            author = f"<i><b>🆘 {i.message.author} (тех. поддержка): </b></i>"
        msg_text = f"<code>{i.message}</code>" if i.message.text else f"<a href=\"{i.message}\">Фотография</a>"
        text += f"{author}{msg_text}\n\n"
        last_message_author_id = i.message.author_id
        last_by_bot = i.message.by_bot

    chat_id, chat_name = event.message.chat_id, event.message.chat_name

    if cardinal.MAIN_CFG["BlockList"].getboolean("blockNewMessageNotification") and chat_name in cardinal.block_list:
        return
    if not text:
        return

    kb = keyboards.reply(chat_id, chat_name, extend=True)
    Thread(target=cardinal.telegram.send_notification, args=(text, kb, utils.NotificationTypes.new_message),
           daemon=True).start()


def send_review_notification(cardinal: Cardinal, order: Order, chat_id: int, reply_text: str | None):
    if not cardinal.telegram:
        return
    reply_text = f"\n\n🗨️<b>Ответ:</b> \n<code>{reply_text}</code>" if reply_text else ""
    Thread(target=cardinal.telegram.send_notification,
           args=(f"🔮 Вы получили {'⭐' * order.review.stars} за заказ <code>{order.id}</code>!\n\n"
                 f"💬<b>Отзыв:</b>\n<code>{order.review.text}</code>{reply_text}",
                 keyboards.new_order(order.id, order.buyer_username, chat_id),
                 utils.NotificationTypes.review),
           daemon=True).start()


def process_review(cardinal: Cardinal, event: NewMessageEvent):
    message_type, its_me = event.message.type, cardinal.account.username in str(event.message)
    message_text, chat_id = str(event.message), event.message.chat_id
    if message_type not in [types.MessageTypes.NEW_FEEDBACK, types.MessageTypes.FEEDBACK_CHANGED] or its_me:
        return

    def send_reply():
        res = fp_utils.RegularExpressions()
        order_id = res.ORDER_ID.findall(message_text)
        if not order_id:
            return
        order_id = order_id[0][1:]
        try:
            order = cardinal.account.get_order(order_id)
        except:
            logger.error(f"Не удалось получить информацию о заказе #{order_id}.")
            logger.debug("TRACEBACK", exc_info=True)
            return

        if not order.review or not order.review.stars:
            return

        logger.info(f"Изменен отзыв за на заказ {order.id}.")

        toggle = f"star{order.review.stars}Reply"
        text = f"star{order.review.stars}ReplyText"
        reply_text = None
        if cardinal.MAIN_CFG["ReviewReply"].getboolean(toggle) and cardinal.MAIN_CFG["ReviewReply"].get(text):
            try:
                reply_text = cardinal_tools.format_order_text(cardinal.MAIN_CFG["ReviewReply"].get(text), order)
                cardinal.account.send_review(order_id, reply_text, 5)
            except:
                logger.error(f"Произошла ошибка при ответе на отзыв {order_id}.")
                logger.debug("TRACEBACK", exc_info=True)
        send_review_notification(cardinal, order, chat_id, reply_text)
    Thread(target=send_reply, daemon=True).start()


def send_command_notification_handler(cardinal: Cardinal, event: NewMessageEvent):
    """
    Отправляет уведомление о введенной команде в телеграм.
    """
    if not cardinal.telegram:
        return
    obj, message_text, message_type = event.message, str(event.message), event.message.type
    chat_id, chat_name, username = event.message.chat_id, event.message.chat_name, event.message.author

    if cardinal.MAIN_CFG["BlockList"].getboolean("blockCommandNotification") and username in cardinal.block_list:
        return
    command = message_text.strip().lower()
    if command not in cardinal.AR_CFG or not cardinal.AR_CFG[command].getboolean("telegramNotification"):
        return

    if not cardinal.AR_CFG[command].get("notificationText"):
        text = f"Пользователь {username} ввел команду <code>{utils.escape(command)}</code>."
    else:
        text = cardinal_tools.format_msg_text(cardinal.AR_CFG[command]["notificationText"], obj)

    Thread(target=cardinal.telegram.send_notification, args=(text, keyboards.reply(chat_id, chat_name),
                                                             utils.NotificationTypes.command), daemon=True).start()


def test_auto_delivery_handler(cardinal: Cardinal, event: NewMessageEvent):
    """
    Выполняет тест автовыдачи.
    """
    obj, message_text = event.message, str(event.message)
    chat_name = event.message.chat_name

    if not message_text.startswith("!автовыдача"):
        return
    split = message_text.split(" ")
    if len(split) < 2:
        logger.warning("Одноразовый ключ автовыдачи не обнаружен.")
        return

    key = split[1].strip()
    if key not in cardinal.delivery_tests:
        logger.warning("Невалидный одноразовый ключ автовыдачи.")
        return

    lot_name = cardinal.delivery_tests[key]
    del cardinal.delivery_tests[key]
    logger.info(f"Одноразовый ключ $YELLOW{key}$RESET удален.")

    fake_order = OrderShortcut("ADTEST", lot_name, 0.0, chat_name, 000000, types.OrderStatuses.PAID,
                               ORDER_HTML_TEMPLATE.replace("$username", chat_name).replace("$lot_name", lot_name))

    fake_event = NewOrderEvent(event.runner_tag, fake_order)
    cardinal.run_handlers(cardinal.new_order_handlers, (cardinal, fake_event,))


def send_categories_raised_notification_handler(cardinal: Cardinal, response: RaiseResponse) -> None:
    """
    Отправляет уведомление о поднятии лотов в Telegram.
    """
    if not response.complete or not cardinal.telegram:
        return

    categories_names = [i.fullname for i in response.raised_subcategories]
    categories_text = "\n".join(f"<code>{i}</code>" for i in categories_names)
    text = f"""⤴️<b><i>Поднял следующие категории:</i></b>
{categories_text}"""
    Thread(target=cardinal.telegram.send_notification,
           args=(text, ),
           kwargs={"notification_type": utils.NotificationTypes.lots_raise}, daemon=True).start()


# Изменен список ордеров (REGISTER_TO_ORDERS_LIST_CHANGED)
def get_lot_config_by_name(cardinal: Cardinal, name: str) -> configparser.SectionProxy | None:
    """
    Ищет секцию лота в конфиге автовыдачи.

    :param cardinal: экземпляр кардинала.
    :param name: название лота.

    :return: секцию конфига или None.
    """
    for i in cardinal.AD_CFG.sections():
        if i in name:
            return cardinal.AD_CFG[i]
    return None


def check_products_amount(config_obj: configparser.SectionProxy) -> int:
    file_name = config_obj.get("productsFileName")
    if not file_name:
        return 1
    return cardinal_tools.count_products(f"storage/products/{file_name}")


def update_current_lots_handler(cardinal: Cardinal, event: OrdersListChangedEvent):
    logger.info("Получаю информацию о лотах...")
    attempts = 3
    while attempts:
        try:
            cardinal.curr_profile = cardinal.account.get_user(cardinal.account.id)
            cardinal.curr_profile_last_tag = event.runner_tag
            break
        except:
            logger.error("Произошла ошибка при получении информации о лотах.")
            logger.debug("TRACEBACK", exc_info=True)
            attempts -= 1
            time.sleep(2)
    if not attempts:
        logger.error("Не удалось получить информацию о лотах: превышено кол-во попыток.")
        return


# Новый ордер (REGISTER_TO_NEW_ORDER)
def log_new_order_handler(cardinal: Cardinal, event: NewOrderEvent, *args):
    """
    Логирует новый заказ.
    """
    logger.info(f"Новый заказ! ID: $YELLOW#{event.order.id}$RESET")


def send_new_order_notification_handler(cardinal: Cardinal, event: NewOrderEvent, *args):
    """
    Отправляет уведомления о новом заказе в телеграм.
    """
    if not cardinal.telegram:
        return

    if event.order.buyer_username in cardinal.block_list and \
            cardinal.MAIN_CFG["BlockList"].getboolean("blockNewOrderNotification"):
        return

    text = f"""💰 <b>Новый заказ: </b> <code>{utils.escape(event.order.description)}</code>
    
<b><i>🙍‍♂️ Покупатель:</i></b>  <code>{event.order.buyer_username}</code>
<b><i>💵 Сумма:</i></b>  <code>{event.order.price}</code>
<b><i>📇 ID:</i></b> <code>#{event.order.id}</code>"""

    chat_id = cardinal.account.get_chat_by_name(event.order.buyer_username, True).id
    keyboard = keyboards.new_order(event.order.id, event.order.buyer_username, chat_id)
    Thread(target=cardinal.telegram.send_notification, args=(text, keyboard, utils.NotificationTypes.new_order),
           daemon=True).start()


def deliver_product(cardinal: Cardinal, event: NewOrderEvent, delivery_obj: configparser.SectionProxy,
                    *args) -> tuple[Message | None, str, int] | None:
    """
    Форматирует текст товара и отправляет его покупателю.

    :return: результат выполнения. None - если лота нет в конфиге.
    [Результат выполнения, текст товара, оставшееся кол-во товара] - в любом другом случае.
    """
    chat_id = cardinal.account.get_chat_by_name(event.order.buyer_username).id
    response_text = cardinal_tools.format_order_text(delivery_obj["response"], event.order)

    # Проверяем, есть ли у лота файл с товарами. Если нет, то просто отправляем response лота.
    if delivery_obj.get("productsFileName") is None:
        result = cardinal.send_message(chat_id, response_text, event.order.buyer_username)
        if not result:
            logger.error(f"Не удалось отправить товар для ордера $YELLOW{event.order.id}$RESET. ")
        return result, response_text, -1

    # Получаем товар.
    file_name = delivery_obj.get("productsFileName")
    products = []
    if cardinal.MAIN_CFG["FunPay"].getboolean("multiDelivery") and not delivery_obj.getboolean("disableMultiDelivery"):
        result = AMOUNT_EXPRESSION.findall(event.order.description)
        if result:
            amount = int(result[0].split(" ")[0])
            products = cardinal_tools.get_products(f"storage/products/{file_name}", amount)
    if not products:
        products = cardinal_tools.get_products(f"storage/products/{file_name}")

    product_text = "\n".join(products[0]).replace("\\n", "\n")
    response_text = response_text.replace("$product", product_text)

    # Отправляем товар.
    result = cardinal.send_message(chat_id, response_text, event.order.buyer_username)

    # Если произошла какая-либо ошибка при отправлении товара, возвращаем товар обратно в файл с товарами.
    if not result:
        cardinal_tools.add_products(f"storage/products/{file_name}", products[0])
        logger.error(f"Не удалось отправить товар для ордера $YELLOW{event.order.id}$RESET. ")
    return result, response_text, cardinal_tools.count_products(f"storage/products/{file_name}")


def deliver_product_handler(cardinal: Cardinal, event: NewOrderEvent, *args) -> None:
    """
    Обертка для deliver_product(), обрабатывающая ошибки.
    """
    if not cardinal.MAIN_CFG["FunPay"].getboolean("autoDelivery"):
        return
    if event.order.buyer_username in cardinal.block_list and cardinal.MAIN_CFG["BlockList"].getboolean("blockDelivery"):
        logger.info(f"Пользователь {event.order.buyer_username} находится в ЧС и включена блокировка автовыдачи. "
                    f"$YELLOW(ID: {event.order.id})$RESET")
        if cardinal.telegram:
            text = f"⛔ Пользователь " \
                   f"<a href=\"https://funpay.com/users/{event.order.buyer_id}/\">{event.order.buyer_username}</a> " \
                   f"находится в ЧС и включена блокировка автовыдачи."
            Thread(target=cardinal.telegram.send_notification, args=(text, ),
                   kwargs={"notification_type": utils.NotificationTypes.delivery}, daemon=True).start()
        return

    # Ищем название лота в конфиге.
    delivery_obj = None
    config_lot_name = ""
    for lot_name in cardinal.AD_CFG:
        if lot_name in event.order.description:
            delivery_obj = cardinal.AD_CFG[lot_name]
            config_lot_name = lot_name
            break

    if delivery_obj is None:
        logger.info(f"Лот \"{event.order.description}\" не обнаружен в конфиге автовыдачи.")
        return

    if delivery_obj.getboolean("disable"):
        logger.info(f"Для лота \"{event.order.description}\" отключена автовыдача.")
        return

    cardinal.run_handlers(cardinal.pre_delivery_handlers, (cardinal, event, config_lot_name))

    try:
        result = deliver_product(cardinal, event, delivery_obj, *args)
        if not result[0]:
            cardinal.run_handlers(cardinal.post_delivery_handlers,
                                  (cardinal, event, config_lot_name, "Превышено кол-во попыток.", result[2], True))
        else:
            logger.info(f"Товар для ордера {event.order.id} выдан.")
            cardinal.run_handlers(cardinal.post_delivery_handlers,
                                  (cardinal, event, config_lot_name, result[1], result[2], False))
    except Exception as e:
        logger.error(f"Произошла непредвиденная ошибка при обработке заказа {event.order.id}.")
        logger.debug("TRACEBACK", exc_info=True)
        cardinal.run_handlers(cardinal.post_delivery_handlers,
                              (cardinal, event, config_lot_name, str(e), -1, True))


# REGISTER_TO_POST_DELIVERY
def send_delivery_notification_handler(cardinal: Cardinal, event: NewOrderEvent, config_lot_name: str,
                                       delivery_text: str, products_left: int, errored: bool = False, *args):
    """
    Отправляет уведомление в телеграм об отправке товара.
    """
    if cardinal.telegram is None:
        return

    if errored:
        text = f"""❌ Произошла ошибка при выдаче товара для ордера <code>{event.order.id}</code>.

Ошибка: <code>{utils.escape(delivery_text)}</code>"""
    else:
        amount = "<b>∞</b>" if products_left == -1 else f"<code>{products_left}</code>"
        text = f"""✅ Успешно выдал товар для ордера <code>{event.order.id}</code>.

🛒 <b><i>Товар:</i></b>
<code>{utils.escape(delivery_text)}</code>

📋 <b><i>Осталось товаров: </i></b>{amount}"""

    Thread(target=cardinal.telegram.send_notification, args=(text, ),
           kwargs={"notification_type": utils.NotificationTypes.delivery}, daemon=True).start()


def update_lot_state(cardinal: Cardinal, lot: types.LotShortcut, task: int) -> bool:
    """
    Обновляет состояние лота

    :param cardinal: экземпляр Кардинала.

    :param lot: экземпляр лота.

    :param task: -1 - деактивировать лот. 1 - активировать лот.

    :return: результат выполнения.
    """
    attempts = 3
    while attempts:
        try:
            lot_fields = cardinal.account.get_lot_fields(lot.id, lot.subcategory.id)
            if task == 1:
                lot_fields.active = True
                cardinal.account.save_lot(lot_fields)
                logger.info(f"Восстановил лот $YELLOW{lot.description}$RESET.")
            elif task == -1:
                lot_fields.active = False
                cardinal.account.save_lot(lot_fields)
                logger.info(f"Деактивировал лот $YELLOW{lot.description}$RESET.")
            return True
        except Exception as e:
            if isinstance(e, exceptions.RequestFailedError) and e.status_code == 404:
                logger.error(f"Произошла ошибка при изменении состояния лота $YELLOW{lot.description}$RESET:"
                             "лот не найден.")
                return False
            logger.error(f"Произошла ошибка при изменении состояния лота $YELLOW{lot.description}$RESET.")
            logger.debug("TRACEBACK", exc_info=True)
            attempts -= 1
            time.sleep(2)
    logger.error(f"Не удалось изменить состояние лота $YELLOW{lot.description}$RESET: превышено кол-во попыток.")
    return False


def update_lots_states(cardinal: Cardinal, event: NewOrderEvent):
    if not any([cardinal.MAIN_CFG["FunPay"].getboolean("autoRestore"),
                cardinal.MAIN_CFG["FunPay"].getboolean("autoDisable")]):
        return
    if cardinal.curr_profile_last_tag != event.runner_tag or cardinal.last_state_change_tag == event.runner_tag:
        return

    lots = cardinal.curr_profile.get_sorted_lots(1)

    deactivated = []
    restored = []
    for lot in cardinal.profile.get_lots():
        # -1 - деактивировать
        # 0 - ничего не делать
        # 1 - восстановить
        current_task = 0
        config_obj = get_lot_config_by_name(cardinal, lot.description)

        # Если лот уже деактивирован
        if lot.id not in lots:
            # и не найден в конфиге автовыдачи (глобальное автовосстановление включено)
            if config_obj is None:
                if cardinal.MAIN_CFG["FunPay"].getboolean("autoRestore"):
                    current_task = 1

            # и найден в конфиге автовыдачи
            else:
                # и глобальное автовосстановление вкл. + не выключено в самом лоте в конфиге автовыдачи
                if cardinal.MAIN_CFG["FunPay"].getboolean("autoRestore") and \
                        config_obj.get("disableAutoRestore") in ["0", None]:
                    # если глобальная автодеактивация выключена - восстанавливаем.
                    if not cardinal.MAIN_CFG["FunPay"].getboolean("autoDisable"):
                        current_task = 1
                    # если глобальная автодеактивация включена - восстанавливаем только если есть товары.
                    else:
                        if check_products_amount(config_obj):
                            current_task = 1

        # Если же лот активен
        else:
            # и найден в конфиге автовыдачи
            if config_obj:
                products_count = check_products_amount(config_obj)
                # и все условия выполнены: нет товаров + включено глобальная автодеактивация + она не выключена в
                # самом лоте в конфига автовыдачи - отключаем.
                if all((not products_count, cardinal.MAIN_CFG["FunPay"].getboolean("autoDisable"),
                        config_obj.get("disableAutoDisable") in ["0", None])):
                    current_task = -1

        if current_task:
            result = update_lot_state(cardinal, lot, current_task)
            if result:
                if current_task == -1:
                    deactivated.append(lot.description)
                elif current_task == 1:
                    restored.append(lot.description)
            time.sleep(0.5)

    if deactivated:
        lots = "\n".join(deactivated)
        text = f"""🔴 <b>Деактивировал лоты:</b>
        
<code>{lots}</code>"""
        Thread(target=cardinal.telegram.send_notification, args=(text, ),
               kwargs={"notification_type": utils.NotificationTypes.lots_deactivate}, daemon=True).start()
    if restored:
        lots = "\n".join(restored)
        text = f"""🟢 <b>Активировал лоты:</b>

<code>{lots}</code>"""
        Thread(target=cardinal.telegram.send_notification, args=(text,),
               kwargs={"notification_type": utils.NotificationTypes.lots_restore}, daemon=True).start()
    cardinal.last_state_change_tag = event.runner_tag


def update_lots_state_handler(cardinal: Cardinal, event: NewOrderEvent, *args):
    Thread(target=update_lots_states, args=(cardinal, event), daemon=True).start()


# BIND_TO_ORDER_STATUS_CHANGED
def send_thank_u_message_handler(cardinal: Cardinal, event: OrderStatusChangedEvent):
    """
    Отправляет ответное сообщение на подтверждение заказа.
    """
    if not cardinal.MAIN_CFG["OrderConfirm"].getboolean("sendReply"):
        return
    if not event.order.status == types.OrderStatuses.CLOSED:
        return

    text = cardinal.MAIN_CFG["OrderConfirm"]["replyText"]
    chat = cardinal.account.get_chat_by_name(event.order.buyer_username, True)
    text = cardinal_tools.format_order_text(text, event.order)
    logger.info(f"Пользователь %YELLOW{event.order.buyer_username}$RESET подтвердил выполнение заказа "
                f"$YELLOW{event.order.id}.$RESET")
    logger.info(f"Отправляю ответное сообщение ...")
    Thread(target=cardinal.send_message, args=(chat.id, text, event.order.buyer_username), daemon=True).start()


def send_order_confirmed_notification_handler(cardinal: Cardinal, event: OrderStatusChangedEvent):
    """
    Отправляет уведомление о подтверждении заказа в Telegram.
    """
    if not event.order.status == types.OrderStatuses.CLOSED:
        return

    chat = cardinal.account.get_chat_by_name(event.order.buyer_username, True)
    Thread(target=cardinal.telegram.send_notification,
           args=(f"""🪙 Пользователь <a href="https://funpay.com/chat/?node={chat.id}">{event.order.buyer_username}</a> """
                 f"""подтвердил выполнение заказа <code>{event.order.id}</code>.""",
                 keyboards.new_order(event.order.id, event.order.buyer_username, chat.id),
                 utils.NotificationTypes.order_confirmed),
           daemon=True).start()


# REGISTER_TO_POST_START
def send_bot_started_notification_handler(cardinal: Cardinal, *args) -> None:
    """
    Отправляет уведомление о запуске бота в телеграм.
    """
    if cardinal.telegram is None:
        return

    if cardinal.account.currency is None:
        curr = ""
    else:
        curr = cardinal.account.currency
    text = f"""✅ <b><u>FunPay Cardinal запущен!</u></b>

ℹ️ <b><i>Версия:</i></b> <code>{cardinal.VERSION}</code>
👑 <b><i>Аккаунт:</i></b>  <code>{cardinal.account.username}</code> | <code>{cardinal.account.id}</code>
💰 <b><i>Баланс:</i></b> <code>{cardinal.account.balance}{curr}</code>
📊 <b><i>Незавершенных ордеров:</i></b>  <code>{cardinal.account.active_sales}</code>"""

    for i in cardinal.telegram.init_messages:
        try:
            cardinal.telegram.bot.edit_message_text(text, i[0], i[1])
        except:
            continue


BIND_TO_INIT_MESSAGE = [save_already_exists_chat_handler]

BIND_TO_NEW_MESSAGE = [log_msg_handler,
                       send_greetings_handler,
                       add_old_user_handler,
                       send_response_handler,
                       process_review,
                       send_new_message_notification_handler,
                       send_command_notification_handler,
                       test_auto_delivery_handler]

BIND_TO_POST_LOTS_RAISE = [send_categories_raised_notification_handler]

BIND_TO_ORDERS_LIST_CHANGED = [update_current_lots_handler]

BIND_TO_NEW_ORDER = [log_new_order_handler, send_new_order_notification_handler, deliver_product_handler,
                     update_lots_state_handler]

BIND_TO_ORDER_STATUS_CHANGED = [send_thank_u_message_handler, send_order_confirmed_notification_handler]

BIND_TO_POST_DELIVERY = [send_delivery_notification_handler]

BIND_TO_POST_START = [send_bot_started_notification_handler]
