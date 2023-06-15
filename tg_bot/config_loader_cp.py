"""
В данном модуле описаны функции для ПУ загрузки / выгрузки конфиг-файлов.
Модуль реализован в виде плагина.
"""

from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from cardinal import Cardinal

from tg_bot import CBT, static_keyboards
from telebot import types
import logging
import os


logger = logging.getLogger("TGBot")


def init_config_loader_cp(cardinal: Cardinal, *args):
    tg = cardinal.telegram
    bot = tg.bot

    def open_config_loader(c: types.CallbackQuery):
        if c.message.text is None:
            bot.send_message(c.message.chat.id, "Здесь вы можете загрузить и выгрузить конфиги.",
                             reply_markup=static_keyboards.CONFIGS_UPLOADER)
            return
        bot.edit_message_text("Здесь вы можете загрузить и выгрузить конфиги.", c.message.chat.id,
                              c.message.id, reply_markup=static_keyboards.CONFIGS_UPLOADER)

    def send_config(c: types.CallbackQuery):
        """
        Отправляет файл конфига.
        """
        config_type = c.data.split(":")[1]
        if config_type == "main":
            path = "configs/_main.cfg"
            text = "Основной конфиг."
        elif config_type == "autoResponse":
            path = "configs/auto_response.cfg"
            text = "Конфиг автоответчика."
        elif config_type == "autoDelivery":
            path = "configs/auto_delivery.cfg"
            text = "Конфиг автовыдачи."
        else:
            bot.answer_callback_query(c.id)
            return

        back_button = types.InlineKeyboardMarkup()\
            .add(types.InlineKeyboardButton("◀️ Назад", callback_data="config_loader"))

        if not os.path.exists(path):
            bot.send_message(c.message.chat.id, f"❌ Конфиг <code>{path}</code> не обнаружен.",
                            reply_markup=back_button)
            bot.answer_callback_query(c.id)
            return

        with open(path, "r", encoding="utf-8") as f:
            data = f.read().strip()
            if not data:
                bot.send_message(c.message.chat.id, f"❌ Конфиг <code>{path}</code> пуст.",
                                 reply_markup=back_button)
                bot.answer_callback_query(c.id)
                return
            f.seek(0)
            bot.send_document(c.message.chat.id, f, caption=text, reply_markup=back_button)

        logger.info(f"Пользователь $MAGENTA@{c.from_user.username} (id: {c.from_user.id})$RESET запросил "
                    f"конфиг $YELLOW{path}$RESET.")
        bot.answer_callback_query(c.id)

    tg.cbq_handler(open_config_loader, lambda c: c.data == "config_loader")
    tg.cbq_handler(send_config, lambda c: c.data.startswith(f"{CBT.DOWNLOAD_CFG}:"))


BIND_TO_PRE_INIT = [init_config_loader_cp]
