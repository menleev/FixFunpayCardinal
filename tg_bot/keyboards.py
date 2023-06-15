"""
Функции генерации клавиатур для суб-панелей управления.
"""

from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from cardinal import Cardinal

from telebot.types import InlineKeyboardButton as B
from telebot import types

from tg_bot import utils, CBT, MENU_CFG
from tg_bot.utils import NotificationTypes

from FunPayAPI.types import SubCategoryTypes

import Utils

import logging
import random
import os

logger = logging.getLogger("TGBot")


def power_off(instance_id: int, state: int) -> types.InlineKeyboardMarkup:
    """
    Создает клавиатуру выключения бота.

    :param instance_id: ID запуска бота.
    :param state: текущей этап клавиатуры.

    :return: экземпляр клавиатуры.
    """
    keyboard = types.InlineKeyboardMarkup()
    if state == 0:
        keyboard.row(B("✅ Да", callback_data=f"{CBT.SHUT_DOWN}:1:{instance_id}"),
                     B("❌ Нет", callback_data=CBT.CANCEL_SHUTTING_DOWN))
    elif state == 1:
        keyboard.row(B("❌ Нет", callback_data=CBT.CANCEL_SHUTTING_DOWN),
                     B("✅ Да", callback_data=f"{CBT.SHUT_DOWN}:2:{instance_id}"))
    elif state == 2:
        yes_button_num = random.randint(1, 10)
        yes_button = B("✅ Да", callback_data=f"{CBT.SHUT_DOWN}:3:{instance_id}")
        no_button = B("❌ Нет", callback_data=CBT.CANCEL_SHUTTING_DOWN)
        buttons = [*[no_button] * (yes_button_num - 1), yes_button, *[no_button] * (10 - yes_button_num)]
        keyboard.add(*buttons, row_width=2)
    elif state == 3:
        yes_button_num = random.randint(1, 30)
        yes_button = B("✅ Да", callback_data=f"{CBT.SHUT_DOWN}:4:{instance_id}")
        no_button = B("❌ Нет", callback_data=CBT.CANCEL_SHUTTING_DOWN)
        buttons = [*[no_button] * (yes_button_num - 1), yes_button, *[no_button] * (30 - yes_button_num)]
        keyboard.add(*buttons, row_width=5)
    elif state == 4:
        yes_button_num = random.randint(1, 40)
        yes_button = B("❌ Нет", callback_data=f"{CBT.SHUT_DOWN}:5:{instance_id}")
        no_button = B("✅ Да", callback_data=CBT.CANCEL_SHUTTING_DOWN)
        buttons = [*[yes_button] * (yes_button_num - 1), no_button, *[yes_button] * (40 - yes_button_num)]
        keyboard.add(*buttons, row_width=7)
    elif state == 5:
        keyboard.add(B("✅ Дэ", callback_data=f"{CBT.SHUT_DOWN}:6:{instance_id}"))
    return keyboard


def main_settings(cardinal: Cardinal) -> types.InlineKeyboardMarkup:
    """
    Создает клавиатуру основных переключателей (CBT.CATEGORY:main).

    :param cardinal: экземпляр кардинала.

    :return: экземпляр клавиатуры.
    """
    keyboard = types.InlineKeyboardMarkup() \
        .row(B(f"Автоподнятие {'🟢' if int(cardinal.MAIN_CFG['FunPay']['autoRaise']) else '🔴'}",
               callback_data=f"{CBT.SWITCH}:FunPay:autoRaise"),
             B(f"Автоответчик {'🟢' if int(cardinal.MAIN_CFG['FunPay']['autoResponse']) else '🔴'}",
               callback_data=f"{CBT.SWITCH}:FunPay:autoResponse")) \
        .row(B(f"Автовыдача {'🟢' if int(cardinal.MAIN_CFG['FunPay']['autoDelivery']) else '🔴'}",
               callback_data=f"{CBT.SWITCH}:FunPay:autoDelivery"),
             B(f"Мульти-выдача {utils.bool_to_text(cardinal.MAIN_CFG['FunPay'].getboolean('multiDelivery'))}",
               callback_data=f"{CBT.SWITCH}:FunPay:multiDelivery")) \
        .row(B(f"Активация лотов {'🟢' if int(cardinal.MAIN_CFG['FunPay']['autoRestore']) else '🔴'}",
               callback_data=f"{CBT.SWITCH}:FunPay:autoRestore"),
             B(f"Деактивация лотов {'🟢' if int(cardinal.MAIN_CFG['FunPay']['autoDisable']) else '🔴'}",
               callback_data=f"{CBT.SWITCH}:FunPay:autoDisable")) \
        .add(B("◀️ Назад", callback_data=CBT.MAIN))
    return keyboard


def new_message_view_settings(cardinal: Cardinal) -> types.InlineKeyboardMarkup:
    """
    Создает клавиатуру настроек вида уведомлений о новых сообщениях.

    :param cardinal: экземпляр кардинала.
    """
    keyboard = types.InlineKeyboardMarkup() \
        .add(B(f"Отображать мои сообщения "
               f"{'🟢' if int(cardinal.MAIN_CFG['NewMessageView']['includeMyMessages']) else '🔴'}",
               callback_data=f"{CBT.SWITCH}:NewMessageView:includeMyMessages")) \
        .add(B(f"Отображать сообщения FunPay "
               f"{'🟢' if int(cardinal.MAIN_CFG['NewMessageView']['includeFPMessages']) else '🔴'}",
               callback_data=f"{CBT.SWITCH}:NewMessageView:includeFPMessages")) \
        .add(B(f"Отображать сообщения бота "
               f"{'🟢' if int(cardinal.MAIN_CFG['NewMessageView']['includeBotMessages']) else '🔴'}",
               callback_data=f"{CBT.SWITCH}:NewMessageView:includeBotMessages")) \
        .add(B(f"Увед., если сообщения только от меня "
               f"{'🟢' if int(cardinal.MAIN_CFG['NewMessageView']['notifyOnlyMyMessages']) else '🔴'}",
               callback_data=f"{CBT.SWITCH}:NewMessageView:notifyOnlyMyMessages")) \
        .add(B(f"Увед., если сообщения только от FP "
               f"{'🟢' if int(cardinal.MAIN_CFG['NewMessageView']['notifyOnlyFPMessages']) else '🔴'}",
               callback_data=f"{CBT.SWITCH}:NewMessageView:notifyOnlyFPMessages")) \
        .add(B(f"Увед., если сообщения только от бота "
               f"{'🟢' if int(cardinal.MAIN_CFG['NewMessageView']['notifyOnlyBotMessages']) else '🔴'}",
               callback_data=f"{CBT.SWITCH}:NewMessageView:notifyOnlyBotMessages")) \
        .add(B("◀️ Назад", callback_data=CBT.MAIN2))

    return keyboard


def old_users_settings(cardinal: Cardinal):
    keyboard = types.InlineKeyboardMarkup()\
        .add(B(f"Приветствовать пользователя {utils.bool_to_text(cardinal.MAIN_CFG['Greetings'].getboolean('sendGreetings'))}",
               callback_data=f"{CBT.SWITCH}:Greetings:sendGreetings"))\
        .add(B(f"Игнорировать существующие чаты {utils.bool_to_text(cardinal.MAIN_CFG['Greetings'].getboolean('cacheInitChats'))}",
               callback_data=f"{CBT.SWITCH}:Greetings:cacheInitChats"))\
        .add(B(f"✏️ Изменить текст приветственного сообщения", callback_data=CBT.EDIT_GREETINGS_TEXT))\
        .add(B(f"◀️ Назад", callback_data=CBT.MAIN2))
    return keyboard


def order_confirm_reply_settings(cardinal: Cardinal):
    keyboard = types.InlineKeyboardMarkup()\
        .add(B(f"Отправлять сообщение {utils.bool_to_text(cardinal.MAIN_CFG['OrderConfirm'].getboolean('sendReply'))}",
               callback_data=f"{CBT.SWITCH}:OrderConfirm:sendReply")) \
        .add(B(f"✏️ Изменить текст сообщения", callback_data=CBT.EDIT_ORDER_CONFIRM_REPLY_TEXT)) \
        .add(B(f"◀️ Назад", callback_data=CBT.MAIN2))
    return keyboard


def review_reply_settings(cardinal: Cardinal):
    keyboard = types.InlineKeyboardMarkup()
    for i in range(1, 6):
        keyboard.row(B(f"{'⭐'*i}{' '*(10-i)}",
                       callback_data=f"{CBT.SEND_REVIEW_REPLY_TEXT}:{i}"),
                     B(f"{utils.bool_to_text(cardinal.MAIN_CFG['ReviewReply'].getboolean(f'star{i}Reply'))}",
                       callback_data=f"{CBT.SWITCH}:ReviewReply:star{i}Reply"),
                     B(f"✏️",
                       callback_data=f"{CBT.EDIT_REVIEW_REPLY_TEXT}:{i}"))
    keyboard.add(B(f"◀️ Назад", callback_data=CBT.MAIN2))
    return keyboard


def notifications_settings(cardinal: Cardinal, chat_id: int) -> types.InlineKeyboardMarkup:
    """
    Создает клавиатуру настроек уведомлений (CBT.CATEGORY:telegram).

    :param cardinal: экземпляр кардинала.
    :param chat_id: ID чата, в котором вызвана данная клавиатура.
    """
    tg = cardinal.telegram
    keyboard = types.InlineKeyboardMarkup() \
        .row(B(f"Новое сообщение "
               f"{'🔔' if tg.is_notification_enabled(chat_id, NotificationTypes.new_message) else '🔕'}",
               callback_data=f"{CBT.SWITCH_TG_NOTIFICATIONS}:{chat_id}:{NotificationTypes.new_message}"),
             B(f"Введена команда "
               f"{'🔔' if tg.is_notification_enabled(chat_id, NotificationTypes.command) else '🔕'}",
               callback_data=f"{CBT.SWITCH_TG_NOTIFICATIONS}:{chat_id}:{NotificationTypes.command}")) \
        .row(B(f"Новый заказ "
               f"{'🔔' if tg.is_notification_enabled(chat_id, NotificationTypes.new_order) else '🔕'}",
               callback_data=f"{CBT.SWITCH_TG_NOTIFICATIONS}:{chat_id}:{NotificationTypes.new_order}"),
             B(f"Заказ подтвержден "
               f"{'🔔' if tg.is_notification_enabled(chat_id, NotificationTypes.order_confirmed) else '🔕'}",
               callback_data=f"{CBT.SWITCH_TG_NOTIFICATIONS}:{chat_id}:{NotificationTypes.order_confirmed}")) \
        .row(B(f"Активация лота "
               f"{'🔔' if tg.is_notification_enabled(chat_id, NotificationTypes.lots_restore) else '🔕'}",
               callback_data=f"{CBT.SWITCH_TG_NOTIFICATIONS}:{chat_id}:{NotificationTypes.lots_restore}"),
             B("Деактивация лота "
               f"{'🔔' if tg.is_notification_enabled(chat_id, NotificationTypes.lots_deactivate) else '🔕'}",
               callback_data=f"{CBT.SWITCH_TG_NOTIFICATIONS}:{chat_id}:{NotificationTypes.lots_deactivate}")) \
        .row(B(f"Выдача товара "
               f"{'🔔' if tg.is_notification_enabled(chat_id, NotificationTypes.delivery) else '🔕'}",
               callback_data=f"{CBT.SWITCH_TG_NOTIFICATIONS}:{chat_id}:{NotificationTypes.delivery}"),
             B(f"Поднятие лотов "
               f"{'🔔' if tg.is_notification_enabled(chat_id, NotificationTypes.lots_raise) else '🔕'}",
               callback_data=f"{CBT.SWITCH_TG_NOTIFICATIONS}:{chat_id}:{NotificationTypes.lots_raise}")) \
        .add(B(f"Оставлен отзыв "
               f"{'🔔' if tg.is_notification_enabled(chat_id, NotificationTypes.review) else '🔕'}",
               callback_data=f"{CBT.SWITCH_TG_NOTIFICATIONS}:{chat_id}:{NotificationTypes.review}")) \
        .add(B(f"Запуск бота "
               f"{'🔔' if tg.is_notification_enabled(chat_id, NotificationTypes.bot_start) else '🔕'}",
               callback_data=f"{CBT.SWITCH_TG_NOTIFICATIONS}:{chat_id}:{NotificationTypes.bot_start}")) \
        .add(B(f"Прочее (плагины) "
               f"{'🔔' if tg.is_notification_enabled(chat_id, NotificationTypes.other) else '🔕'}",
               callback_data=f"{CBT.SWITCH_TG_NOTIFICATIONS}:{chat_id}:{NotificationTypes.other}")) \
        .add(B("◀️ Назад", callback_data=CBT.MAIN))
    return keyboard


def announcements_settings(cardinal: Cardinal, chat_id: int):
    """
    Создает клавиатуру настроек уведомлений объявлений.

    :param cardinal: экземпляр кардинала.
    :param chat_id: ID чата, в котором вызвана данная клавиатура.
    """
    tg = cardinal.telegram
    keyboard = types.InlineKeyboardMarkup() \
        .add(B(f"Объявления "
               f"{'🔔' if tg.is_notification_enabled(chat_id, NotificationTypes.announcement) else '🔕'}",
               callback_data=f"{CBT.SWITCH_TG_NOTIFICATIONS}:{chat_id}:{NotificationTypes.announcement}")) \
        .add(B(f"Реклама "
               f"{'🔔' if tg.is_notification_enabled(chat_id, NotificationTypes.ad) else '🔕'}",
               callback_data=f"{CBT.SWITCH_TG_NOTIFICATIONS}:{chat_id}:{NotificationTypes.ad}"))
    return keyboard


def block_list_settings(cardinal: Cardinal) -> types.InlineKeyboardMarkup:
    """
    Создает клавиатуру настроек черного списка (CBT.CATEGORY:blockList).

    :param cardinal: экземпляр кардинала.
    """
    keyboard = types.InlineKeyboardMarkup() \
        .add(B(f"Блокировать автовыдачу "
               f"{'🟢' if int(cardinal.MAIN_CFG['BlockList']['blockDelivery']) else '🔴'}",
               callback_data=f"{CBT.SWITCH}:BlockList:blockDelivery")) \
        .add(B(f"Блокировать автоответ "
               f"{'🟢' if int(cardinal.MAIN_CFG['BlockList']['blockResponse']) else '🔴'}",
               callback_data=f"{CBT.SWITCH}:BlockList:blockResponse")) \
        .add(B(f"Не уведомлять о новых сообщениях "
               f"{'🟢' if int(cardinal.MAIN_CFG['BlockList']['blockNewMessageNotification']) else '🔴'}",
               callback_data=f"{CBT.SWITCH}:BlockList:blockNewMessageNotification")) \
        .add(B(f"Не уведомлять о новых заказах "
               f"{'🟢' if int(cardinal.MAIN_CFG['BlockList']['blockNewOrderNotification']) else '🔴'}",
               callback_data=f"{CBT.SWITCH}:BlockList:blockNewOrderNotification")) \
        .add(B(f"Не уведомлять о введенных командах "
               f"{'🟢' if int(cardinal.MAIN_CFG['BlockList']['blockCommandNotification']) else '🔴'}",
               callback_data=f"{CBT.SWITCH}:BlockList:blockCommandNotification")) \
        .add(B("◀️ Назад", callback_data=CBT.MAIN))
    return keyboard


def commands_list(cardinal: Cardinal, offset: int) -> types.InlineKeyboardMarkup:
    """
    Создает клавиатуру со списком команд (CBT.CMD_LIST:<offset>).

    :param cardinal: экземпляр кардинала.
    :param offset: смещение списка команд.
    """
    keyboard = types.InlineKeyboardMarkup()
    commands = cardinal.RAW_AR_CFG.sections()[offset: offset + MENU_CFG.AR_BTNS_AMOUNT]
    if not commands and offset != 0:
        offset = 0
        commands = cardinal.RAW_AR_CFG.sections()[offset: offset + MENU_CFG.AR_BTNS_AMOUNT]

    for index, cmd in enumerate(commands):
        #  CBT.EDIT_CMD:номер команды:смещение (для кнопки назад)
        keyboard.add(B(cmd, callback_data=f"{CBT.EDIT_CMD}:{offset + index}:{offset}"))

    keyboard = utils.add_navigation_buttons(keyboard, offset, MENU_CFG.AR_BTNS_AMOUNT, len(commands),
                                            len(cardinal.RAW_AR_CFG.sections()), CBT.CMD_LIST)

    keyboard.add(B("🤖 В настройки автоответчика", callback_data=f"{CBT.CATEGORY}:autoResponse")) \
        .add(B("📋 В главное меню", callback_data=CBT.MAIN))
    return keyboard


def edit_command(cardinal: Cardinal, command_index: int, offset: int) -> types.InlineKeyboardMarkup:
    """
    Создает клавиатуру изменения параметров команды (CBT.EDIT_CMD:<command_num>:<offset>).

    :param cardinal: экземпляр кардинала.
    :param command_index: номер команды.
    :param offset: смещение списка команд.
    """
    command = cardinal.RAW_AR_CFG.sections()[command_index]
    command_obj = cardinal.RAW_AR_CFG[command]
    keyboard = types.InlineKeyboardMarkup() \
        .add(B(f"✏️ Редактировать ответ",
               callback_data=f"{CBT.EDIT_CMD_RESPONSE_TEXT}:{command_index}:{offset}")) \
        .add(B(f"✏️ Редактировать уведомление",
               callback_data=f"{CBT.EDIT_CMD_NOTIFICATION_TEXT}:{command_index}:{offset}")) \
        .add(B(f"Уведомление в Telegram "
               f"{utils.bool_to_text(command_obj.get('telegramNotification'), on='🔔', off='🔕')}",
               callback_data=f"{CBT.SWITCH_CMD_NOTIFICATION}:{command_index}:{offset}")) \
        .add(B("🗑️ Удалить команду / сет команд", callback_data=f"{CBT.DEL_CMD}:{command_index}:{offset}")) \
        .row(B("◀️ Назад", callback_data=f"{CBT.CMD_LIST}:{offset}"),
             B("🔄 Обновить", callback_data=f"{CBT.EDIT_CMD}:{command_index}:{offset}"))
    return keyboard


def products_files_list(offset: int) -> types.InlineKeyboardMarkup:
    """
    Создает клавиатуру со списком файлов с товарами (CBT.PRODUCTS_FILES_LIST:<offset>).

    :param offset: смещение списка файлов.
    """
    keyboard = types.InlineKeyboardMarkup()
    files = os.listdir("storage/products")[offset:offset + MENU_CFG.PF_BTNS_AMOUNT]
    if not files and offset != 0:
        offset = 0
        files = os.listdir("storage/products")[offset:offset + 5]

    for index, name in enumerate(files):
        amount = Utils.cardinal_tools.count_products(f"storage/products/{name}")
        keyboard.add(B(f"{amount} шт., {name}", callback_data=f"{CBT.EDIT_PRODUCTS_FILE}:{offset + index}:{offset}"))

    keyboard = utils.add_navigation_buttons(keyboard, offset, MENU_CFG.PF_BTNS_AMOUNT, len(files),
                                            len(os.listdir("storage/products")), CBT.PRODUCTS_FILES_LIST)

    keyboard.add(B("📦 В настройки автовыдачи", callback_data=f"{CBT.CATEGORY}:autoDelivery")) \
        .add(B("📋 В главное меню", callback_data=CBT.MAIN))
    return keyboard


def products_file_edit(file_number: int, offset: int, confirmation: bool = False) \
        -> types.InlineKeyboardMarkup:
    """
    Создает клавиатуру изменения файла с товарами (CBT.EDIT_PRODUCTS_FILE:<file_index>:<offset>).

    :param file_number: номер файла.
    :param offset: смещение списка файлов с товарами.
    :param confirmation: включить ли в клавиатуру подтверждение удаления файла.
    """
    keyboard = types.InlineKeyboardMarkup() \
        .add(B("➕ Добавить товары",
               callback_data=f"{CBT.ADD_PRODUCTS_TO_FILE}:{file_number}:{file_number}:{offset}:0")) \
        .add(B("⤵️ Скачать файл с товарами.", callback_data=f"download_products_file:{file_number}:{offset}"))
    if not confirmation:
        keyboard.add(B("🗑️ Удалить файл с товарами", callback_data=f"del_products_file:{file_number}:{offset}"))
    else:
        keyboard.row(B("✅ Да", callback_data=f"confirm_del_products_file:{file_number}:{offset}"),
                     B("❌ Нет", callback_data=f"{CBT.EDIT_PRODUCTS_FILE}:{file_number}:{offset}"))
    keyboard.row(B("◀️ Назад", callback_data=f"{CBT.PRODUCTS_FILES_LIST}:{offset}"),
                 B("🔄 Обновить", callback_data=f"{CBT.EDIT_PRODUCTS_FILE}:{file_number}:{offset}"))
    return keyboard


def lots_list(cardinal: Cardinal, offset: int) -> types.InlineKeyboardMarkup:
    """
    Создает клавиатуру со списком лотов (lots:<offset>).

    :param cardinal: экземпляр кардинала.
    :param offset: смещение списка лотов.
    """
    keyboard = types.InlineKeyboardMarkup()
    lots = cardinal.AD_CFG.sections()[offset: offset + MENU_CFG.AD_BTNS_AMOUNT]
    if not lots and offset != 0:
        offset = 0
        lots = cardinal.AD_CFG.sections()[offset: offset + MENU_CFG.AD_BTNS_AMOUNT]

    for index, lot in enumerate(lots):
        keyboard.add(B(lot, callback_data=f"{CBT.EDIT_AD_LOT}:{offset + index}:{offset}"))

    keyboard = utils.add_navigation_buttons(keyboard, offset, MENU_CFG.AD_BTNS_AMOUNT, len(lots),
                                            len(cardinal.AD_CFG.sections()), CBT.AD_LOTS_LIST)

    keyboard.add(B("📦 В настройки автовыдачи", callback_data=f"{CBT.CATEGORY}:autoDelivery")) \
        .add(B("📋 В главное меню", callback_data=CBT.MAIN))
    return keyboard


def funpay_lots_list(cardinal: Cardinal, offset: int):
    """
    Создает клавиатуру со списком лотов с FunPay (funpay_lots:<offset>).
    """
    keyboard = types.InlineKeyboardMarkup()
    lots = cardinal.tg_profile.get_common_lots()
    lots = lots[offset: offset + MENU_CFG.FP_LOTS_BTNS_AMOUNT]
    if not lots and offset != 0:
        offset = 0
        lots = cardinal.tg_profile.get_common_lots()[offset: offset + MENU_CFG.FP_LOTS_BTNS_AMOUNT]

    for index, lot in enumerate(lots):
        keyboard.add(B(lot.description, callback_data=f"{CBT.ADD_AD_TO_LOT}:{offset + index}:{offset}"))

    keyboard = utils.add_navigation_buttons(keyboard, offset, MENU_CFG.FP_LOTS_BTNS_AMOUNT, len(lots),
                                            len(cardinal.tg_profile.get_common_lots()), CBT.FP_LOTS_LIST)

    keyboard.row(B("➕ Ввести вручную", callback_data=f"{CBT.ADD_AD_TO_LOT_MANUALLY}:{offset}"),
                 B("🔄 Сканировать FunPay", callback_data=f"update_funpay_lots:{offset}")) \
        .add(B("📦 В настройки автовыдачи", callback_data=f"{CBT.CATEGORY}:autoDelivery")) \
        .add(B("📋 В главное меню", callback_data=CBT.MAIN))
    return keyboard


def edit_lot(cardinal: Cardinal, lot_number: int, offset: int) -> types.InlineKeyboardMarkup:
    """
    Создает клавиатуру изменения лота (CBT.EDIT_AD_LOT:<lot_num>:<offset>).

    :param cardinal: экземпляр кардинала.
    :param lot_number: номер лота.
    :param offset: смещение списка слотов.
    """

    lot = cardinal.AD_CFG.sections()[lot_number]
    lot_obj = cardinal.AD_CFG[lot]
    file_name = lot_obj.get("productsFileName")
    kb = types.InlineKeyboardMarkup() \
        .add(B("✏️ Редактировать текст выдачи",
               callback_data=f"{CBT.EDIT_LOT_DELIVERY_TEXT}:{lot_number}:{offset}"))
    if not file_name:
        kb.add(B("⛓️ Привязать файл с товарами",
                 callback_data=f"{CBT.BIND_PRODUCTS_FILE}:{lot_number}:{offset}"))
    else:
        if file_name not in os.listdir("storage/products"):
            with open(f"storage/products/{file_name}", "w", encoding="utf-8"):
                pass
        file_number = os.listdir("storage/products").index(file_name)

        kb.row(B("⛓️ Привязать файл с товарами",
                 callback_data=f"{CBT.BIND_PRODUCTS_FILE}:{lot_number}:{offset}"),
               B("➕ Добавить товары",
                 callback_data=f"{CBT.ADD_PRODUCTS_TO_FILE}:{file_number}:{lot_number}:{offset}:1"))

    params = {
        "ad": cardinal.MAIN_CFG["FunPay"].getboolean("autoDelivery"),
        "md": cardinal.MAIN_CFG["FunPay"].getboolean("multiDelivery"),
        "ares": cardinal.MAIN_CFG["FunPay"].getboolean("autoRestore"),
        "adis": cardinal.MAIN_CFG["FunPay"].getboolean("autoDisable"),
    }

    kb.row(B(f"Выдача {utils.bool_to_text(lot_obj.get('disable'), '🔴', '🟢') if params['ad'] else '⚪'}",
             callback_data=f"{f'switch_lot:disable:{lot_number}:{offset}' if params['ad'] else CBT.PARAM_DISABLED}"),
           B(f"Мультивыдача {utils.bool_to_text(lot_obj.get('disableMultiDelivery'), '🔴', '🟢') if params['md'] else '⚪'}",
             callback_data=f"{f'switch_lot:disableMultiDelivery:{lot_number}:{offset}' if params['md'] else CBT.PARAM_DISABLED}")) \
        .row(B(f"Восст. {utils.bool_to_text(lot_obj.get('disableAutoRestore'), '🔴', '🟢') if params['ares'] else '⚪'}",
               callback_data=f"{f'switch_lot:disableAutoRestore:{lot_number}:{offset}' if params['ares'] else CBT.PARAM_DISABLED}"),
             B(f"Деакт. {utils.bool_to_text(lot_obj.get('disableAutoDisable'), '🔴', '🟢') if params['adis'] else '⚪'}",
               callback_data=f"{f'switch_lot:disableAutoDisable:{lot_number}:{offset}' if params['adis'] else CBT.PARAM_DISABLED}")) \
        .row(B("👾 Тест автовыдачи", callback_data=f"test_auto_delivery:{lot_number}:{offset}"),
             B("🗑️ Удалить лот", callback_data=f"{CBT.DEL_AD_LOT}:{lot_number}:{offset}")) \
        .row(B("◀️ Назад", callback_data=f"{CBT.AD_LOTS_LIST}:{offset}"),
             B("🔄 Обновить", callback_data=f"{CBT.EDIT_AD_LOT}:{lot_number}:{offset}"))
    return kb


# Прочее
def new_order(order_id: str, username: str, node_id: int,
              confirmation: bool = False, no_refund: bool = False) -> types.InlineKeyboardMarkup:
    """
    Генерирует клавиатуру для сообщения о новом заказе.

    :param order_id: ID заказа (без #).
    :param username: никнейм покупателя.
    :param node_id: ID чата с покупателем.
    :param confirmation: заменить ли кнопку "Вернуть деньги" на подтверждение "Да" / "Нет"?
    :param no_refund: убрать ли кнопки, связанные с возвратом денег?
    """
    keyboard = types.InlineKeyboardMarkup()
    if not no_refund:
        if confirmation:
            keyboard.row(B(text="✅ Да", callback_data=f"{CBT.REFUND_CONFIRMED}:{order_id}:{node_id}:{username}"),
                         B(text="❌ Нет", callback_data=f"{CBT.REFUND_CANCELLED}:{order_id}:{node_id}:{username}"))
        else:
            keyboard.add(B(text="💸 Вернуть деньги",
                           callback_data=f"{CBT.REQUEST_REFUND}:{order_id}:{node_id}:{username}"))

    keyboard.add(B(text="🌐 Открыть страницу заказа", url=f"https://funpay.com/orders/{order_id}/")) \
        .row(B(text="📨 Ответить", callback_data=f"{CBT.SEND_FP_MESSAGE}:{node_id}:{username}"),
             B(text="📝 Заготовки", callback_data=f"{CBT.TMPLT_LIST_ANS_MODE}:0:{node_id}:{username}:2:{order_id}:"
                                                 f"{1 if no_refund else 0}"))
    return keyboard


def reply(node_id: int, username: str, again: bool = False, extend: bool = False) -> types.InlineKeyboardMarkup:
    """
    Генерирует кнопку для отправки сообщения из Telegram в ЛС пользователю FunPay.

    :param node_id: ID переписки, в которую нужно отправить сообщение.
    :param username: никнейм пользователя, с которым ведется переписка.
    :param again: заменить текст "Отправить" на "Отправить еще"?
    :param extend: добавить ли кнопку "Расширить"?
    """
    buttons = [B(text=f"{'📨 Ответ' if not again else '📨 Отправить еще'}",
               callback_data=f"{CBT.SEND_FP_MESSAGE}:{node_id}:{username}"),
               B(text="📝 Шаблоны",
                 callback_data=f"{CBT.TMPLT_LIST_ANS_MODE}:0:{node_id}:{username}:{int(again)}:{int(extend)}")]
    if extend:
        buttons.append(B(text="➕ Больше",
                         callback_data=f"{CBT.EXTEND_CHAT}:{node_id}:{username}"))
    buttons.append(B(text=f"🌐 {username}", url=f"https://funpay.com/chat/?node={node_id}"))
    keyboard = types.InlineKeyboardMarkup() \
        .row(*buttons)
    return keyboard


def templates_list(cardinal: Cardinal, offset: int) \
        -> types.InlineKeyboardMarkup:
    """
    Создает клавиатуру со списком шаблонов ответов. (CBT.TMPLT_LIST:<offset>).

    :param cardinal: экземпляр кардинала.
    :param offset: смещение списка шаблонов.
    """
    keyboard = types.InlineKeyboardMarkup()
    templates = cardinal.telegram.answer_templates[offset: offset + MENU_CFG.TMPLT_BTNS_AMOUNT]
    if not templates and offset != 0:
        offset = 0
        templates = cardinal.telegram.answer_templates[offset: offset + MENU_CFG.TMPLT_BTNS_AMOUNT]

    for index, tmplt in enumerate(templates):
        keyboard.add(B(tmplt, callback_data=f"{CBT.EDIT_TMPLT}:{offset + index}:{offset}"))

    keyboard = utils.add_navigation_buttons(keyboard, offset, MENU_CFG.TMPLT_BTNS_AMOUNT, len(templates),
                                            len(cardinal.telegram.answer_templates), CBT.TMPLT_LIST)
    keyboard.add(B("➕ Добавить заготовку", callback_data=f"{CBT.ADD_TMPLT}:{offset}")) \
        .add(B("📋 В главное меню", callback_data=CBT.MAIN))
    return keyboard


def edit_template(cardinal: Cardinal, template_index: int, offset: int) -> types.InlineKeyboardMarkup:
    """
    Создает клавиатуру изменения шаблона ответа (CBT.EDIT_TMPLT:<template_index>:<offset>).

    :param cardinal: экземпляр кардинала.
    :param template_index: числовой индекс шаблона ответа.
    :param offset: смещение списка шаблонов ответа.
    """
    keyboard = types.InlineKeyboardMarkup() \
        .add(B("◀️ Назад", callback_data=f"{CBT.TMPLT_LIST}:{offset}")) \
        .add(B("🗑️ Удалить", callback_data=f"{CBT.DEL_TMPLT}:{template_index}:{offset}"))
    return keyboard


def templates_list_ans_mode(cardinal: Cardinal, offset: int, node_id: int, username: str, prev_page: int,
                            extra: list | None = None):
    """
    Создает клавиатуру со списком шаблонов ответов.
    (CBT.TMPLT_LIST_ANS_MODE:{offset}:{node_id}:{username}:{prev_page}:{extra}).


    :param cardinal: экземпляр кардинала.
    :param offset: смещение списка шаблонов ответа.
    :param node_id: ID чата, в который нужно отправить шаблон.
    :param username: никнейм пользователя, с которым ведется переписка.
    :param prev_page: предыдущая страница.
    :param extra: доп данные для пред. страницы.
    """

    keyboard = types.InlineKeyboardMarkup()
    templates = cardinal.telegram.answer_templates[offset: offset + MENU_CFG.TMPLT_BTNS_AMOUNT]
    extra_str = ":" + ":".join(str(i) for i in extra) if extra else ""

    if not templates and offset != 0:
        offset = 0
        templates = cardinal.telegram.answer_templates[offset: offset + MENU_CFG.TMPLT_BTNS_AMOUNT]

    for index, tmplt in enumerate(templates):
        keyboard.add(B(tmplt.replace("$username", username),
                       callback_data=f"{CBT.SEND_TMPLT}:{offset + index}:{node_id}:{username}:{prev_page}{extra_str}"))

    extra_list = [node_id, username, prev_page]
    extra_list.extend(extra)
    keyboard = utils.add_navigation_buttons(keyboard, offset, MENU_CFG.TMPLT_BTNS_AMOUNT, len(templates),
                                            len(cardinal.telegram.answer_templates), CBT.TMPLT_LIST_ANS_MODE,
                                            extra_list)

    if prev_page == 0:
        keyboard.add(B("◀️ Назад", callback_data=f"{CBT.BACK_TO_REPLY_KB}:{node_id}:{username}:0{extra_str}"))
    elif prev_page == 1:
        keyboard.add(B("◀️ Назад", callback_data=f"{CBT.BACK_TO_REPLY_KB}:{node_id}:{username}:1{extra_str}"))
    elif prev_page == 2:
        keyboard.add(B("◀️ Назад", callback_data=f"{CBT.BACK_TO_ORDER_KB}:{node_id}:{username}{extra_str}"))
    return keyboard


def plugins_list(cardinal: Cardinal, offset: int):
    """
    Создает клавиатуру со списком плагинов (CBT.PLUGINS_LIST:<offset>).

    :param cardinal: экземпляр кардинала.
    :param offset: смещение списка плагинов.
    """
    keyboard = types.InlineKeyboardMarkup()
    plugins = list(cardinal.plugins.keys())[offset: offset + MENU_CFG.PLUGINS_BTNS_AMOUNT]
    if not plugins and offset != 0:
        offset = 0
        plugins = list(cardinal.plugins.keys())[offset: offset + MENU_CFG.PLUGINS_BTNS_AMOUNT]

    for uuid in plugins:
        #  CBT.EDIT_CMD:номер команды:смещение (для кнопки назад)
        keyboard.add(B(f"{cardinal.plugins[uuid].name} {utils.bool_to_text(cardinal.plugins[uuid].enabled)}",
                       callback_data=f"{CBT.EDIT_PLUGIN}:{uuid}:{offset}"))

    keyboard = utils.add_navigation_buttons(keyboard, offset, MENU_CFG.PLUGINS_BTNS_AMOUNT, len(plugins),
                                            len(list(cardinal.plugins.keys())), CBT.PLUGINS_LIST)

    keyboard.add(B("➕ Добавить плагин", callback_data=f"{CBT.UPLOAD_PLUGIN}:{offset}")) \
        .add(B("📋 В главное меню", callback_data=CBT.MAIN2))
    return keyboard


def edit_plugin(cardinal: Cardinal, uuid: str, offset: int, ask_to_delete: bool = False):
    """
    Создает клавиатуру управления плагином.

    :param cardinal: экземпляр кардинала.
    :param uuid: UUID плагина.
    :param offset: смещение списка плагинов.
    :param ask_to_delete: вставить ли подтверждение удаления плагина?
    """
    plugin_obj = cardinal.plugins[uuid]
    keyboard = types.InlineKeyboardMarkup()
    active_text = "Деактивировать" if cardinal.plugins[uuid].enabled else "Активировать"
    keyboard.add(B(active_text, callback_data=f"{CBT.TOGGLE_PLUGIN}:{uuid}:{offset}"))

    if plugin_obj.commands:
        keyboard.add(B("⌨️ Команды", callback_data=f"{CBT.PLUGIN_COMMANDS}:{uuid}:{offset}"))
    if plugin_obj.settings_page:
        keyboard.add(B("⚙️ Настройки", callback_data=f"{CBT.PLUGIN_SETTINGS}:{uuid}:{offset}"))

    if not ask_to_delete:
        keyboard.add(B("🗑️ Удалить", callback_data=f"{CBT.DELETE_PLUGIN}:{uuid}:{offset}"))
    else:
        keyboard.row(B("✅ Да", callback_data=f"{CBT.CONFIRM_DELETE_PLUGIN}:{uuid}:{offset}"),
                     B("❌ Нет", callback_data=f"{CBT.CANCEL_DELETE_PLUGIN}:{uuid}:{offset}"))
    keyboard.add(B("◀️ Назад", callback_data=f"{CBT.PLUGINS_LIST}:{offset}"))

    return keyboard
