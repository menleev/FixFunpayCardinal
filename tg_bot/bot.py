"""
В данном модуле написан Telegram бот.
"""

from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from cardinal import Cardinal

import re
import os
import sys
import time
import random
import string
import psutil
import telebot
import logging

from telebot import types

from tg_bot import utils, static_keyboards as skb, keyboards as kb, CBT
from Utils import cardinal_tools, update_checker


logger = logging.getLogger("TGBot")


class TGBot:
    def __init__(self, cardinal: Cardinal):
        self.cardinal = cardinal
        self.bot = telebot.TeleBot(self.cardinal.MAIN_CFG["Telegram"]["token"], parse_mode="HTML",
                                   allow_sending_without_reply=True, num_threads=5)

        self.authorized_users = utils.load_authorized_users()

        # [(chat_id, message_id)]
        self.init_messages = []

        # {
        #     chat_id: {
        #         user_id: {
        #             "state": None | "statusText",
        #             "data": { ... },
        #             "msg_id": int
        #         }
        #     }
        # }
        self.user_states = {}

        # {
        #    chat_id: {
        #        utils.NotificationTypes.new_message: bool,
        #        utils.NotificationTypes.new_order: bool,
        #        ...
        #    },
        # }
        #
        self.notification_settings = utils.load_notifications_settings()

        self.answer_templates = utils.load_answer_templates()

        self.commands = {
            "menu": "открыть панель настроек",
            "profile": "получить статистику аккаунта",
            "test_lot": "создать ключ для теста автовыдачи",
            "upload_img": "выгружает изображение на сервер FunPay",
            "ban": "добавить пользователя в ЧС",
            "unban": "удалить пользователя из ЧС",
            "block_list": "получить ЧС",
            "watermark": "изменить вотемарку сообщений",
            "logs": "получить лог-файл",
            "del_logs": "удалить старые лог-файлы",
            "about": "информация об этой версии FPC",
            "check_updates": "проверить на наличие обновлений",
            "update": "обновиться до следующей версии",
            "sys": "информация о нагрузке на систему",
            "restart": "перезагрузить бота",
            "power_off": "выключить бота"
        }

        self.file_handlers = {}

    # User states
    def get_user_state(self, chat_id: int, user_id: int) -> dict | None:
        """
        Получает текущее состояние пользователя.

        :param chat_id: id чата.
        :param user_id: id пользователя.

        :return: состояние + доп. данные.
        """
        if chat_id not in self.user_states or user_id not in self.user_states[chat_id] or \
                not self.user_states[chat_id][user_id].get("state"):
            return None
        return self.user_states[chat_id][user_id]

    def set_user_state(self, chat_id: int, message_id: int, user_id: int,
                       state: str, data: dict | None = None) -> None:
        """
        Устанавливает состояние для пользователя.

        :param chat_id: id чата.
        :param message_id: id сообщения, после которого устанавливается данное состояние.
        :param user_id: id пользователя.
        :param state: состояние.
        :param data: доп. данные.
        """
        if chat_id not in self.user_states:
            self.user_states[chat_id] = {}
        if user_id not in self.user_states[chat_id]:
            self.user_states[chat_id][user_id] = {}
        if self.user_states[chat_id][user_id].get("state") is None and state is None:
            return None
        self.user_states[chat_id][user_id] = {"state": state, "msg_id": message_id, "data": data or {}}

    def clear_state(self, chat_id: int, user_id: int, del_msg: bool = False) -> int | None:
        """
        Очищает состояние пользователя.

        :param chat_id: id чата.
        :param user_id: id пользователя.
        :param del_msg: удалять ли сообщение, после которого было обозначено текущее состояние.

        :return: ID сообщения | None, если состояние уже было пустое.
        """
        if chat_id not in self.user_states or user_id not in self.user_states[chat_id] or \
                not self.user_states[chat_id][user_id].get("state"):
            return None

        msg_id = self.user_states[chat_id][user_id]["msg_id"]
        self.user_states[chat_id][user_id] = {"state": None, "msg_id": None, "data": {}}
        if del_msg:
            self.bot.delete_message(chat_id, msg_id)
        return msg_id

    def check_state(self, chat_id: int, user_id: int, state: str) -> bool:
        """
        Проверяет, является ли состояние указанным.

        :param chat_id: id чата.
        :param user_id: id пользователя.
        :param state: состояние.

        :return: True / False
        """
        if chat_id not in self.user_states or user_id not in self.user_states[chat_id]:
            return False
        return self.user_states[chat_id][user_id].get("state") == state

    # Notification settings
    def is_notification_enabled(self, chat_id: int, notification_type: str) -> bool:
        """
        Включен ли указанный тип уведомлений в указанном чате?

        :param chat_id: ID Telegram чата.
        :param notification_type: тип уведомлений.
        """
        chat_id = str(chat_id)
        if chat_id not in self.notification_settings:
            result = False
        else:
            result = bool(self.notification_settings[chat_id].get(notification_type))
        if notification_type in [utils.NotificationTypes.announcement, utils.NotificationTypes.ad]:
            result = not result
        return result

    def toggle_notification(self, chat_id: int, notification_type: str) -> bool:
        """
        Переключает указанный тип уведомлений в указанном чате и сохраняет настройки уведомлений.

        :param chat_id: ID Telegram чата.
        :param notification_type: тип уведомлений.
        """
        chat_id = str(chat_id)
        if chat_id not in self.notification_settings:
            self.notification_settings[chat_id] = {}

        if notification_type in [utils.NotificationTypes.announcement, utils.NotificationTypes.ad]:
            self.notification_settings[chat_id][notification_type] = self.is_notification_enabled(int(chat_id),
                                                                                                  notification_type)
        else:
            self.notification_settings[chat_id][notification_type] = not self.is_notification_enabled(int(chat_id),
                                                                                                      notification_type)
        utils.save_notifications_settings(self.notification_settings)
        return self.notification_settings[chat_id][notification_type]

    # handler binders
    def file_handler(self, state, handler):
        self.file_handlers[state] = handler

    def run_file_handlers(self, m: types.Message):
        if (state := self.get_user_state(m.chat.id, m.from_user.id)) is None \
                or state["state"] not in list(self.file_handlers.keys()):
            return
        try:
            self.file_handlers[state["state"]](m)
        except:
            logger.error("Произошла ошибка при выполнении хэндлера Telegram бота.")
            logger.debug("TRACEBACK", exc_info=True)

    def msg_handler(self, handler, **kwargs):
        """
        Регистрирует хэндлер, срабатывающий при новом сообщении.

        :param handler: хэндлер.
        :param kwargs: аргументы для хэндлера.
        """
        bot_instance = self.bot

        @bot_instance.message_handler(**kwargs)
        def run_handler(message: types.Message):
            try:
                handler(message)
            except:
                logger.error("Произошла ошибка при выполнении хэндлера Telegram бота.")
                logger.debug("TRACEBACK", exc_info=True)

    def cbq_handler(self, handler, func, **kwargs):
        """
        Регистрирует хэндлер, срабатывающий при новом callback'е.

        :param handler: хэндлер.
        :param func: функция-фильтр.
        :param kwargs: аргументы для хэндлера.
        """
        bot_instance = self.bot

        @bot_instance.callback_query_handler(func, **kwargs)
        def run_handler(call: types.CallbackQuery):
            try:
                handler(call)
            except:
                logger.error("Произошла ошибка при выполнении хэндлера Telegram бота.")
                logger.debug("TRACEBACK", exc_info=True)

    # Система свой-чужой 0_0
    def reg_admin(self, message: types.Message):
        """
        Проверяет, есть ли пользователь в списке пользователей с доступом к ПУ TG.
        """
        if message.chat.type != "private":
            return
        if message.text == self.cardinal.MAIN_CFG["Telegram"]["secretKey"]:
            self.authorized_users.append(message.from_user.id)
            utils.save_authorized_users(self.authorized_users)
            text = f"🔓 Доступ к ПУ предоставлен!\n\n" \
                   f"🔕 Учти, что сейчас я <b><u>не отправляю никакие уведомления в этот чат</u></b>.\n\n" \
                   f"🔔 Ты можешь настроить уведомления для <b><u>этого чата</u></b> в меню настроек.\n\n" \
                   f"⚙️ Чтобы открыть меню настроек <i>FunPay Cardinal</i>, введи команду /menu."
            logger.warning(f"Пользователь $MAGENTA@{message.from_user.username} (id: {message.from_user.id})$RESET "
                           "ПОЛУЧИЛ ДОСТУП К TELEGRAM ПУ!")
        else:
            text = f"👋 Привет, <b><i>{message.from_user.username}</i></b>!\n\n" \
                   f"❌ Ты неавторизованный пользователь.\n\n🔑 Отправь мне <u><b>секретный пароль</b></u>, " \
                   f"который ты вводил при первичной настройке, чтобы начать работу."
            logger.warning(f"Пользователь $MAGENTA@{message.from_user.username} (id: {message.from_user.id})$RESET "
                           f"попытался получить доступ к Telegram ПУ. Сдерживаю его как могу!")
        self.bot.send_message(message.chat.id, text)

    @staticmethod
    def ignore_unauthorized_users(call: types.CallbackQuery):
        """
        Игнорирует callback'и от не авторизированных пользователей.
        """
        logger.warning(f"Пользователь $MAGENTA@{call.from_user.username} (id {call.from_user.id})$RESET "
                       f"жмет кнопки ПУ в чате $MAGENTA@{call.message.chat.username}"
                       f" (id {call.message.chat.id})$RESET. Сдерживаю его как могу!")
        return

    def param_disabled(self, call: types.CallbackQuery):
        """
        Отправляет сообщение о том, что параметр отключен в глобальных переключателях.
        """
        self.bot.answer_callback_query(call.id, "Данный параметр отключен глобально и не может быть изменен "
                                                "для этого лота.", show_alert=True)

    # Команды
    def send_settings_menu(self, message: types.Message):
        """
        Отправляет основное меню настроек (новым сообщением).
        """
        self.bot.send_message(message.chat.id, "Добро пожаловать в панель управления. Выберите категорию настроек.",
                              reply_markup=skb.SETTINGS_SECTIONS)

    def send_profile(self, message: types.Message):
        """
        Отправляет статистику аккаунта.
        """
        self.bot.send_message(message.chat.id, utils.generate_profile_text(self.cardinal.account),
                              reply_markup=skb.UPDATE_PROFILE_BTN)

    def update_profile(self, call: types.CallbackQuery):
        new_msg = self.bot.send_message(call.message.chat.id,
                                        "Обновляю статистику аккаунта (это может занять некоторое время)...")
        try:
            self.cardinal.account.get()
        except:
            self.bot.edit_message_text("❌ Не удалось обновить статистику аккаунта.", new_msg.chat.id, new_msg.id)
            logger.debug("TRACEBACK", exc_info=True)
            self.bot.answer_callback_query(call.id)
            return

        self.bot.delete_message(new_msg.chat.id, new_msg.id)
        self.bot.edit_message_text(utils.generate_profile_text(self.cardinal.account), call.message.chat.id,
                                   call.message.id, reply_markup=skb.UPDATE_PROFILE_BTN)

    def act_manual_delivery_test(self, message: types.Message):
        """
        Активирует режим ввода названия лота для ручной генерации ключа теста автовыдачи.
        """
        result = self.bot.send_message(message.chat.id, "Введите название лота, тест автовыдачи которого вы хотите "
                                                        "провести.",
                                       reply_markup=skb.CLEAR_STATE_BTN)
        self.set_user_state(message.chat.id, result.id, message.from_user.id, CBT.MANUAL_AD_TEST)

    def manual_delivery_text(self, message: types.Message):
        """
        Генерирует ключ теста автовыдачи (ручной режим).
        """
        self.clear_state(message.chat.id, message.from_user.id, True)
        lot_name = message.text.strip()
        key = "".join(random.sample(string.ascii_letters + string.digits, 50))
        self.cardinal.delivery_tests[key] = lot_name

        logger.info(
            f"Пользователь $MAGENTA@{message.from_user.username} (id: {message.from_user.id})$RESET создал "
            f"одноразовый ключ для автовыдачи лота $YELLOW[{lot_name}]$RESET: $CYAN{key}$RESET.")

        self.bot.send_message(message.chat.id,
                              f"✅ Одноразовый ключ для теста автовыдачи лота "
                              f"<code>{utils.escape(lot_name)}</code> успешно создан. \n\n"
                              f"Для теста автовыдачи введите команду снизу в любой чат FunPay (ЛС)."
                              f"\n\n<code>!автовыдача {key}</code>")

    def act_ban(self, message: types.Message):
        """
        Активирует режим ввода никнейма пользователя, которого нужно добавить в ЧС.
        """
        result = self.bot.send_message(message.chat.id, "Введите имя пользователя, которого хотите внести в ЧС.",
                                       reply_markup=skb.CLEAR_STATE_BTN)
        self.set_user_state(message.chat.id, result.id, message.from_user.id, CBT.BAN)

    def ban(self, message: types.Message):
        """
        Добавляет пользователя в ЧС.
        """
        self.clear_state(message.chat.id, message.from_user.id, True)
        nickname = message.text.strip()

        if nickname in self.cardinal.block_list:
            self.bot.send_message(message.chat.id, f"❌ Пользователь <code>{nickname}</code> уже находится в ЧС.")
            return
        self.cardinal.block_list.append(nickname)
        cardinal_tools.cache_block_list(self.cardinal.block_list)
        logger.info(f"Пользователь $MAGENTA@{message.from_user.username} (id: {message.from_user.id})$RESET "
                    f"добавил пользователя $YELLOW{nickname}$RESET в ЧС.")
        self.bot.send_message(message.chat.id, f"✅ Пользователь <code>{nickname}</code> добавлен в ЧС.")

    def act_unban(self, message: types.Message):
        """
        Активирует режим ввода никнейма пользователя, которого нужно удалить из ЧС.
        """
        result = self.bot.send_message(message.chat.id, "Введите имя пользователя, которого хотите удалить в ЧС.",
                                       reply_markup=skb.CLEAR_STATE_BTN)
        self.set_user_state(message.chat.id, result.id, message.from_user.id, CBT.UNBAN)

    def unban(self, message: types.Message):
        """
        Удаляет пользователя из ЧС.
        """
        self.clear_state(message.chat.id, message.from_user.id, True)
        nickname = message.text.strip()
        if nickname not in self.cardinal.block_list:
            self.bot.send_message(message.chat.id, f"❌ Пользователя <code>{nickname}</code> нет в ЧС.")
            return
        self.cardinal.block_list.remove(nickname)
        cardinal_tools.cache_block_list(self.cardinal.block_list)
        logger.info(f"Пользователь $MAGENTA@{message.from_user.username} (id: {message.from_user.id})$RESET "
                    f"удалил пользователя $YELLOW{nickname}$RESET из ЧС.")
        self.bot.send_message(message.chat.id, f"✅ Пользователь <code>{nickname}</code> удален из ЧС.")

    def send_ban_list(self, message: types.Message):
        """
        Отправляет ЧС.
        """
        if not self.cardinal.block_list:
            self.bot.send_message(message.chat.id, "❌ Черный список пуст.")
            return
        block_list = ", ".join(f"<code>{i}</code>" for i in self.cardinal.block_list)
        self.bot.send_message(message.chat.id, block_list)

    def act_edit_watermark(self, message: types.Message):
        """
        Активирует режим ввода вотемарки сообщений.
        """
        result = self.bot.send_message(message.chat.id, "Введите новый текст вотемарки.\nЕсли вы хотите удалить "
                                                        "вотемарку, отправьте <code>-</code>",
                                       reply_markup=skb.CLEAR_STATE_BTN)
        self.set_user_state(message.chat.id, result.id, message.from_user.id, CBT.EDIT_WATERMARK)

    def edit_watermark(self, message: types.Message):
        self.clear_state(message.chat.id, message.from_user.id, True)
        watermark = message.text if message.text != "-" else ""
        if re.fullmatch(r"\[[a-zA-Z]+]", watermark):
            self.bot.reply_to(message, "❌ Неверный формат вотемарки.")
            return

        self.cardinal.MAIN_CFG["Other"]["watermark"] = watermark
        self.cardinal.save_config(self.cardinal.MAIN_CFG, "configs/_main.cfg")
        if watermark:
            logger.info(f"Пользователь $MAGENTA@{message.from_user.username} (id: {message.from_user.id})$RESET "
                        f"изменил вотемарку сообщений на $YELLOW{watermark}$RESET.")
            self.bot.reply_to(message, f"✅ Вотемарка сообщений изменена на\n<code>{watermark}</code>")
        else:
            logger.info(f"Пользователь $MAGENTA@{message.from_user.username} (id: {message.from_user.id})$RESET "
                        f"удалил вотемарку сообщений.")
            self.bot.reply_to(message, "✅ Вотемарка сообщений удалена.")

    def send_logs(self, message: types.Message):
        """
        Отправляет файл логов.
        """
        if not os.path.exists("logs/log.log"):
            self.bot.send_message(message.chat.id, "❌ Лог-файл не обнаружен.")
        else:
            self.bot.send_message(message.chat.id, "Выгружаю лог-файл (это может занять какое-то время)...")
            try:
                with open("logs/log.log", "r", encoding="utf-8") as f:
                    self.bot.send_document(message.chat.id, f)
            except:
                self.bot.send_message(message.chat.id, "❌ Не удалось выгрузить лог-файл.")
                logger.debug("TRACEBACK", exc_info=True)

    def del_logs(self, message: types.Message):
        """
        Удаляет старые лог-файлы.
        """
        deleted = 0
        for file in os.listdir("logs"):
            if not file.endswith(".log"):
                try:
                    os.remove(f"logs/{file}")
                    deleted += 1
                except:
                    continue
        self.bot.send_message(message.chat.id, f"🗑️ Удалено {deleted} лог-файл(-а, -ов).")

    def about(self, message: types.Message):
        """
        Отправляет информацию о текущей версии бота.
        """
        self.bot.send_message(message.chat.id, f"<b>🐦 FunPay Cardinal 🐦 v{self.cardinal.VERSION}</b>\n\n"
                                               f"<i>Telegram чат:</i> @funpay_cardinal\n"
                                               f"<i>Разработчик:</i> @woopertail")

    def check_updates(self, message: types.Message):
        curr_tag = f"v{self.cardinal.VERSION}"
        try:
            tags = update_checker.get_tags()
        except:
            self.bot.send_message(message.chat.id, "❌ Не удалось получить список версий. Попробуйте позже.")
            logger.debug("TRACEBACK", exc_info=True)
            return
        if not tags:
            self.bot.send_message(message.chat.id, "❌ Не удалось получить список версий. Попробуйте позже.")
            logger.debug("TRACEBACK", exc_info=True)
            return

        new_tag = update_checker.get_next_tag(tags, curr_tag)
        if not new_tag:
            self.bot.send_message(message.chat.id, f"✅ У вас стоит последняя версия FunPayCardinal {curr_tag}!")
            return
        try:
            release = update_checker.get_release(new_tag)
        except:
            self.bot.send_message(message.chat.id, "❌ Не удалось получить информацию о новой версии. "
                                                   "Попробуйте позже.")
            logger.debug("TRACEBACK", exc_info=True)
            return
        self.bot.send_message(message.chat.id, f"<b><u>ДОСТУПНА НОВАЯ ВЕРСИЯ!</u></b>\n{release.name}\n\n"
                                               f"{release.description}")
        self.bot.send_message(message.chat.id, "Для того, чтобы обновиться, введите команду /update")

    def update(self, message: types.Message):
        curr_tag = f"v{self.cardinal.VERSION}"
        try:
            tags = update_checker.get_tags()
        except:
            self.bot.send_message(message.chat.id, "❌ Не удалось получить список версий. Попробуйте позже.")
            logger.debug("TRACEBACK", exc_info=True)
            return
        if not tags:
            self.bot.send_message(message.chat.id, "❌ Не удалось получить список версий. Попробуйте позже.")
            logger.debug("TRACEBACK", exc_info=True)
            return

        new_tag = update_checker.get_next_tag(tags, curr_tag)
        if not new_tag:
            self.bot.send_message(message.chat.id, f"✅ У вас стоит последняя версия FunPayCardinal {curr_tag}!")
            return
        try:
            release = update_checker.get_release(new_tag)
        except:
            self.bot.send_message(message.chat.id, "❌ Не удалось получить информацию о новой версии. "
                                                   "Попробуйте позже.")
            logger.debug("TRACEBACK", exc_info=True)
            return

        try:
            update_checker.create_backup()
            self.bot.send_message(message.chat.id,
                                  "✅ Создал резервную копию конфигов и хранилища <code>backup.zip</code>")
        except:
            self.bot.send_message(message.chat.id, "❌ Не удалось создать бэкап конфигов и хранилища.")
            logger.debug("TRACEBACK", exc_info=True)
            return

        try:
            if getattr(sys, 'frozen', False):
                update_checker.download_update(release.exe_link)
            else:
                update_checker.download_update(release.sources_link)
            update_folder = update_checker.extract()
            self.bot.send_message(message.chat.id, "✅ Загрузил обновление. Устанавливаю ...")
        except:
            self.bot.send_message(message.chat.id, "❌ Произошла ошибка при загрузке обновления.")
            logger.debug("TRACEBACK", exc_info=True)
            return

        try:
            update_checker.update(update_folder)
            if getattr(sys, 'frozen', False):
                self.bot.send_message(message.chat.id,
                                      "✅ Установил обновление! Новый <code>FPC.exe</code> находится в папке "
                                      "<code>update</code>. Выключите бота, перенесите новый <code>FPC.exe</code> "
                                      "на место старого и запустите его.")
            else:
                self.bot.send_message(message.chat.id,
                                      "✅ Установил обновление! Перезапустите бота с помощью команды /restart")
        except:
            self.bot.send_message(message.chat.id, "❌ Произошла ошибка при установке обновления.")
            logger.debug("TRACEBACK", exc_info=True)
            return

    def send_system_info(self, msg: types.Message):
        """
        Отправляет информацию о нагрузке на систему.
        """
        current_time = int(time.time())
        run_time = current_time - self.cardinal.start_time

        ram = psutil.virtual_memory()
        cpu_usage = "\n".join(
            f"    CPU {i}:  <code>{l}%</code>" for i, l in enumerate(psutil.cpu_percent(percpu=True)))
        self.bot.send_message(msg.chat.id, f"""<b><u>Сводка данных</u></b>

<b>ЦП:</b>
{cpu_usage}
    Используется ботом: <code>{psutil.Process().cpu_percent()}%</code>

<b>ОЗУ:</b>
    Всего:  <code>{ram.total // 1048576} MB</code>
    Использовано:  <code>{ram.used // 1048576} MB</code>
    Свободно:  <code>{ram.free // 1048576} MB</code>
    Используется ботом:  <code>{psutil.Process().memory_info().rss // 1048576} MB</code>

<b>Бот:</b>
    Аптайм:  <code>{cardinal_tools.time_to_str(run_time)}</code>
    Чат:  <code>{msg.chat.id}</code>""")

    def restart_cardinal(self, msg: types.Message):
        """
        Перезапускает кардинал.
        """
        self.bot.send_message(msg.chat.id, "Перезагружаюсь...")
        cardinal_tools.restart_program()

    def ask_power_off(self, msg: types.Message):
        """
        Просит подтверждение на отключение FPC.
        """
        self.bot.send_message(msg.chat.id, """<b><u>Вы уверены, что хотите выключить меня?</u></b>\n
Включить меня через <i>Telegram</i>-ПУ <b><u>не получится!</u></b>""",
                              reply_markup=kb.power_off(self.cardinal.instance_id, 0))

    def cancel_power_off(self, call: types.CallbackQuery):
        """
        Отменяет выключение (удаляет клавиатуру с кнопками подтверждения).
        """
        self.bot.edit_message_text("Выключение отменено.", call.message.chat.id, call.message.id)
        self.bot.answer_callback_query(call.id)

    def power_off(self, call: types.CallbackQuery):
        """
        Отключает FPC.
        """
        split = call.data.split(":")
        state = int(split[1])
        instance_id = int(split[2])

        if instance_id != self.cardinal.instance_id:
            self.bot.edit_message_text("❌ Данная кнопка не принадлежит этому запуску.\nВызовите это меню снова.",
                                       call.message.chat.id, call.message.id)
            self.bot.answer_callback_query(call.id)
            return

        if state == 6:
            self.bot.edit_message_text("Ладно, ладно, выключаюсь...", call.message.chat.id, call.message.id)
            self.bot.answer_callback_query(call.id)
            cardinal_tools.shut_down()
            return

        texts = ["На всякий случай спрошу еще раз.\n\n<b><u>Вы точно уверены?</u></b>",

                 """Просто для протокола:\n             
вам придется заходить на ваш сервер или подходить к компьютеру (ну или где я там у вас) и запускать меня вручную!""",

                 """Не то чтобы я навязываюсь, но если вы хотите применить изменения основного конфига, вы можете 
просто перезапустить меня командой /restart.""",

                 """Вы вообще читаете мои сообщения? Проверим ка вас на внимательность: да = нет, нет = да. """ +
                 """Уверен, вы даже не читаете мои сообщения, а ведь важную инфу тут пишу.""",

                 "Ну то есть твердо и четко, дэ?"]

        self.bot.edit_message_text(texts[state - 1], call.message.chat.id, call.message.id,
                                   reply_markup=kb.power_off(instance_id, state))
        self.bot.answer_callback_query(call.id)

    # Чат FunPay
    def act_send_funpay_message(self, call: types.CallbackQuery):
        """
        Активирует режим ввода ссобщения для отправки его в чат FunPay.
        """
        split = call.data.split(":")
        node_id = int(split[1])
        try:
            username = split[2]
        except IndexError:
            username = None
        result = self.bot.send_message(call.message.chat.id, "Введите текст сообщения.",
                                       reply_markup=skb.CLEAR_STATE_BTN)
        self.set_user_state(call.message.chat.id, result.id, call.from_user.id,
                            CBT.SEND_FP_MESSAGE, {"node_id": node_id, "username": username})
        self.bot.answer_callback_query(call.id)

    def send_funpay_message(self, message: types.Message):
        """
        Отправляет сообщение в чат FunPay.
        """
        data = self.get_user_state(message.chat.id, message.from_user.id)["data"]
        node_id, username = data["node_id"], data["username"]
        self.clear_state(message.chat.id, message.from_user.id, True)
        response_text = message.text.strip()
        result = self.cardinal.send_message(node_id, response_text, username)
        if result:
            self.bot.reply_to(message, f'✅ Сообщение отправлено в переписку '
                                       f'<a href="https://funpay.com/chat/?node={node_id}">{username}</a>.',
                              reply_markup=kb.reply(node_id, username, again=True, extend=True))
        else:
            self.bot.reply_to(message, f'❌ Не удалось отправить сообщение в переписку '
                                       f'<a href="https://funpay.com/chat/?node={node_id}">{username}</a>. '
                                       f'Подробнее в файле <code>logs/log.log</code>',
                              reply_markup=kb.reply(node_id, username, again=True, extend=True))

    def act_upload_image(self, m: types.Message):
        """
        Активирует режим ожидания изображения для последующей выгрузки на FunPay.
        """
        result = self.bot.send_message(m.chat.id, "Отправьте изображение.",
                                       reply_markup=skb.CLEAR_STATE_BTN)
        self.set_user_state(m.chat.id, result.id, m.from_user.id, CBT.UPLOAD_IMAGE)

    def act_edit_greetings_text(self, c: types.CallbackQuery):
        result = self.bot.send_message(c.message.chat.id,
                                       "Введите текст приветственного сообщения."
                                       "\n\nСписок переменных:"
                                       "\n<code>$full_date_text</code> - текущая дата в формате <i>01.01.2001</i>."
                                       "\n<code>$date_text</code> - текущая дата в формате <i>1 января</i>."
                                       "\n<code>$date</code> - текущая дата в формате <i>1 января 2001 года</i>."
                                       "\n<code>$time</code> - текущее время в формате <i>ЧЧ:ММ</i>."
                                       "\n<code>$full_time</code> - текущее время в формате <i>ЧЧ:ММ:СС</i>."
                                       "\n<code>$username</code> - никнейм написавшего пользователя."
                                       "\n<code>$message_text</code> - текст сообщения, которое ввел пользователь."
                                       "\n<code>$chat_id</code> - ID чата."
                                       "\n<code>$photo=PHOTO ID</code> - фотография (вместо <code>PHOTO ID</code> "
                                       "впишите ID фотографии, полученный с помощью команды /upload_img)",
                                       reply_markup=skb.CLEAR_STATE_BTN)
        self.set_user_state(c.message.chat.id, result.id, c.from_user.id, CBT.EDIT_GREETINGS_TEXT)
        self.bot.answer_callback_query(c.id)

    def edit_greetings_text(self, m: types.Message):
        self.clear_state(m.chat.id, m.from_user.id, True)
        self.cardinal.MAIN_CFG["Greetings"]["greetingsText"] = m.text
        logger.info(f"Пользователь $MAGENTA@{m.from_user.username} (id: {m.from_user.id})$RESET изменил текст "
                    f"приветствия на $YELLOW{m.text}$RESET.")
        self.cardinal.save_config(self.cardinal.MAIN_CFG, "configs/_main.cfg")
        keyboard = types.InlineKeyboardMarkup() \
            .row(types.InlineKeyboardButton("◀️ Назад", callback_data=f"{CBT.CATEGORY}:greetings"),
                 types.InlineKeyboardButton("✏️ Изменить", callback_data=CBT.EDIT_GREETINGS_TEXT))
        self.bot.reply_to(m, "✅ Текст приветствия изменен!", reply_markup=keyboard)

    def act_edit_order_confirm_reply_text(self, c: types.CallbackQuery):
        result = self.bot.send_message(c.message.chat.id,
                                       "Введите текст ответа на подтверждение заказа."
                                       "\n\nСписок переменных:"
                                       "\n<code>$full_date_text</code> - текущая дата в формате <i>01.01.2001</i>."
                                       "\n<code>$date_text</code> - текущая дата в формате <i>1 января</i>."
                                       "\n<code>$date</code> - текущая дата в формате <i>1 января 2001 года</i>."
                                       "\n<code>$time</code> - текущее время в формате <i>ЧЧ:ММ</i>."
                                       "\n<code>$full_time</code> - текущее время в формате <i>ЧЧ:ММ:СС</i>."
                                       "\n<code>$username</code> - никнейм написавшего пользователя."
                                       "\n<code>$order_title</code> - краткое описание заказа (лот, кол-во, сервер и т.д.)."
                                       "\n<code>$order_id</code> - ID заказа (без #)"
                                       "\n<code>$photo=PHOTO ID</code> - фотография (вместо <code>PHOTO ID</code> "
                                       "впишите ID фотографии, полученный с помощью команды /upload_img)",
                                       reply_markup=skb.CLEAR_STATE_BTN)
        self.set_user_state(c.message.chat.id, result.id, c.from_user.id, CBT.EDIT_ORDER_CONFIRM_REPLY_TEXT)
        self.bot.answer_callback_query(c.id)

    def edit_order_confirm_reply_text(self, m: types.Message):
        self.clear_state(m.chat.id, m.from_user.id, True)
        self.cardinal.MAIN_CFG["OrderConfirm"]["replyText"] = m.text
        logger.info(f"Пользователь $MAGENTA@{m.from_user.username} (id: {m.from_user.id})$RESET изменил текст "
                    f"ответа на подтверждение заказа на $YELLOW{m.text}$RESET.")
        self.cardinal.save_config(self.cardinal.MAIN_CFG, "configs/_main.cfg")
        keyboard = types.InlineKeyboardMarkup() \
            .row(types.InlineKeyboardButton("◀️ Назад", callback_data=f"{CBT.CATEGORY}:orderConfirm"),
                 types.InlineKeyboardButton("✏️ Изменить", callback_data=CBT.EDIT_ORDER_CONFIRM_REPLY_TEXT))
        self.bot.reply_to(m, "✅ Текст ответа на подтверждение заказа изменен!", reply_markup=keyboard)

    def act_edit_review_reply_text(self, c: types.CallbackQuery):
        stars = int(c.data.split(":")[1])
        result = self.bot.send_message(c.message.chat.id,
                                       f"Введите текст ответа отзыв с {'⭐'*stars}."
                                       "\n\nСписок переменных:"
                                       "\n<code>$full_date_text</code> - текущая дата в формате <i>01.01.2001</i>."
                                       "\n<code>$date_text</code> - текущая дата в формате <i>1 января</i>."
                                       "\n<code>$date</code> - текущая дата в формате <i>1 января 2001 года</i>."
                                       "\n<code>$time</code> - текущее время в формате <i>ЧЧ:ММ</i>."
                                       "\n<code>$full_time</code> - текущее время в формате <i>ЧЧ:ММ:СС</i>."
                                       "\n<code>$username</code> - никнейм написавшего пользователя."
                                       "Если товарный файл не привязан - не будет подменяться."
                                       "\n<code>$order_title</code> - название лота."
                                       "\n<code>$order_id</code> - ID заказа (без #)"
                                       "\n<code>$photo=PHOTO ID</code> - фотография (вместо <code>PHOTO ID</code> "
                                       "впишите ID фотографии, полученный с помощью команды /upload_img)",
                                       reply_markup=skb.CLEAR_STATE_BTN)
        self.set_user_state(c.message.chat.id, result.id, c.from_user.id, CBT.EDIT_REVIEW_REPLY_TEXT, {"stars": stars})
        self.bot.answer_callback_query(c.id)

    def edit_review_reply_text(self, m: types.Message):
        stars = self.get_user_state(m.chat.id, m.from_user.id)["data"]["stars"]
        self.clear_state(m.chat.id, m.from_user.id, True)
        self.cardinal.MAIN_CFG["ReviewReply"][f"star{stars}ReplyText"] = m.text
        logger.info(f"Пользователь $MAGENTA@{m.from_user.username} (id: {m.from_user.id})$RESET изменил текст "
                    f"ответа на отзыв с {stars} зв. на $YELLOW{m.text}$RESET.")
        self.cardinal.save_config(self.cardinal.MAIN_CFG, "configs/_main.cfg")
        keyboard = types.InlineKeyboardMarkup() \
            .row(types.InlineKeyboardButton("◀️ Назад", callback_data=f"{CBT.CATEGORY}:reviewReply"),
                 types.InlineKeyboardButton("✏️ Изменить", callback_data=f"{CBT.EDIT_REVIEW_REPLY_TEXT}:{stars}"))
        self.bot.reply_to(m, f"✅ Текст ответа отзыв с {'⭐'*stars} изменен!", reply_markup=keyboard)

    def open_reply_menu(self, c: types.CallbackQuery):
        """
        Открывает меню ответа на сообщение (callback используется в кнопках "назад").
        """
        split = c.data.split(":")
        node_id, username, again = int(split[1]), split[2], int(split[3])
        extend = True if len(split) > 4 and int(split[4]) else False
        self.bot.edit_message_reply_markup(c.message.chat.id, c.message.id,
                                           reply_markup=kb.reply(node_id, username, bool(again), extend))

    def extend_new_message_notification(self, c: types.CallbackQuery):
        """
        "Расширяет" уведомление о новом сообщении.
        """
        chat_id, username = c.data.split(":")[1:]
        try:
            chat = self.cardinal.account.get_chat(int(chat_id))
        except:
            self.bot.answer_callback_query(c.id)
            self.bot.send_message(c.message.chat.id, "❌ Не удалось получить данные о чате.")
            return

        text = ""
        if chat.looking_link:
            text += f"<b><i>Смотрит:</i></b>\n<a href=\"{chat.looking_link}\">{chat.looking_text}</a>\n\n"

        messages = chat.messages[-10:]
        last_message_author_id = -1
        for i in messages:
            if i.author_id == last_message_author_id:
                author = ""
            elif i.author_id == self.cardinal.account.id:
                author = "<i><b>🫵 Вы:</b></i> "
            elif i.author_id == 0:
                author = f"<i><b>🔵 {i.author}: </b></i>"
            elif i.author == i.chat_name:
                author = f"<i><b>👤 {i.author}: </b></i>"
            else:
                author = f"<i><b>🆘 {i.author} (тех. поддержка): </b></i>"
            msg_text = f"<code>{i.text}</code>" if i.text else f"<a href=\"{i.image_link}\">Фотография</a>"
            text += f"{author}{msg_text}\n\n"
            last_message_author_id = i.author_id

        self.bot.edit_message_text(text, c.message.chat.id, c.message.id,
                                   reply_markup=kb.reply(int(chat_id), username, False, False))

    # Ордер
    def ask_confirm_refund(self, call: types.CallbackQuery):
        """
        Просит подтвердить возврат денег.
        """
        split = call.data.split(":")
        order_id, node_id, username = split[1], int(split[2]), split[3]
        keyboard = kb.new_order(order_id, username, node_id, confirmation=True)
        self.bot.edit_message_reply_markup(call.message.chat.id, call.message.id, reply_markup=keyboard)
        self.bot.answer_callback_query(call.id)

    def cancel_refund(self, call: types.CallbackQuery):
        """
        Отменяет возврат.
        """
        split = call.data.split(":")
        order_id, node_id, username = split[1], int(split[2]), split[3]
        keyboard = kb.new_order(order_id, username, node_id)
        self.bot.edit_message_reply_markup(call.message.chat.id, call.message.id, reply_markup=keyboard)
        self.bot.answer_callback_query(call.id)

    def refund(self, call: types.CallbackQuery):
        """
        Оформляет возврат за заказ.
        """
        split = call.data.split(":")
        order_id, node_id, username = split[1], int(split[2]), split[3]
        new_msg = None
        attempts = 3
        while attempts:
            try:
                self.cardinal.account.refund(order_id)
                break
            except:
                if not new_msg:
                    new_msg = self.bot.send_message(call.message.chat.id,
                                                    f"❌ Не удалось вернуть средства по заказу <code>#{order_id}</code>."
                                                    f"\nОсталось попыток: <code>{attempts}</code>.")
                else:
                    self.bot.edit_message_text(f"❌ Не удалось вернуть средства по заказу <code>#{order_id}</code>."
                                               f"\nОсталось попыток: <code>{attempts}</code>.",
                                               new_msg.chat.id, new_msg.id)
                attempts -= 1
                time.sleep(1)

        else:
            self.bot.edit_message_text(f"❌ Не удалось вернуть средства по заказу <code>#{order_id}</code>.",
                                       new_msg.chat.id, new_msg.id)

            keyboard = kb.new_order(order_id, username, node_id)
            self.bot.edit_message_reply_markup(call.message.chat.id, call.message.id, reply_markup=keyboard)
            self.bot.answer_callback_query(call.id)
            return

        if not new_msg:
            self.bot.send_message(call.message.chat.id,
                                  f"✅ Средства по заказу <code>#{order_id}</code> возвращены.")
        else:
            self.bot.edit_message_text(f"✅ Средства по заказу <code>#{order_id}</code> возвращены.",
                                       new_msg.chat.id, new_msg.id)

        keyboard = kb.new_order(order_id, username, node_id, no_refund=True)
        self.bot.edit_message_reply_markup(call.message.chat.id, call.message.id, reply_markup=keyboard)
        self.bot.answer_callback_query(call.id)

    def open_order_menu(self, c: types.CallbackQuery):
        split = c.data.split(":")
        node_id, username, order_id, no_refund = int(split[1]), split[2], split[3], bool(int(split[4]))
        self.bot.edit_message_reply_markup(c.message.chat.id, c.message.id,
                                           reply_markup=kb.new_order(order_id, username, node_id, no_refund=no_refund))

    # Панель управления
    def open_cp(self, call: types.CallbackQuery):
        """
        Открывает основное меню настроек (редактирует сообщение).
        """
        self.bot.edit_message_text("Добро пожаловать в панель управления. Выберите категорию настроек.",
                                   call.message.chat.id, call.message.id, reply_markup=skb.SETTINGS_SECTIONS)
        self.bot.answer_callback_query(call.id)

    def open_cp2(self, call: types.CallbackQuery):
        """
        Открывает 2 страницу основного меню настроек (редактирует сообщение).
        """
        self.bot.edit_message_text("Добро пожаловать в панель управления. Выберите категорию настроек.",
                                   call.message.chat.id, call.message.id, reply_markup=skb.SETTINGS_SECTIONS_2)
        self.bot.answer_callback_query(call.id)

    def switch_param(self, call: types.CallbackQuery):
        """
        Переключает переключаемые настройки FPC.
        """
        split = call.data.split(":")
        section, option = split[1], split[2]
        self.cardinal.MAIN_CFG[section][option] = str(int(not int(self.cardinal.MAIN_CFG[section][option])))
        self.cardinal.save_config(self.cardinal.MAIN_CFG, "configs/_main.cfg")

        sections = {
            "FunPay": kb.main_settings,
            "BlockList": kb.block_list_settings,
            "NewMessageView": kb.new_message_view_settings,
            "Greetings": kb.old_users_settings,
            "OrderConfirm": kb.order_confirm_reply_settings,
            "ReviewReply": kb.review_reply_settings
        }
        self.bot.edit_message_reply_markup(call.message.chat.id, call.message.id,
                                           reply_markup=sections[section](self.cardinal))
        logger.info(f"Пользователь $MAGENTA@{call.from_user.username} (id: {call.from_user.id})$RESET изменил параметр "
                    f"$CYAN{option}$RESET секции $YELLOW[{section}]$RESET "
                    f"основного конфига на $YELLOW{self.cardinal.MAIN_CFG[section][option]}$RESET.")
        self.bot.answer_callback_query(call.id)

    def switch_chat_notification(self, call: types.CallbackQuery):
        split = call.data.split(":")
        chat_id, notification_type = int(split[1]), split[2]

        result = self.toggle_notification(chat_id, notification_type)

        logger.info(f"Пользователь $MAGENTA@{call.from_user.username} (id: {call.from_user.id})$RESET переключил "
                    f"уведомления $YELLOW{notification_type}$RESET для чата $YELLOW{call.message.chat.id}$RESET на "
                    f"$CYAN{result}$RESET.")
        keyboard = kb.announcements_settings if notification_type in [utils.NotificationTypes.announcement,
                                                                      utils.NotificationTypes.ad] \
            else kb.notifications_settings
        self.bot.edit_message_reply_markup(call.message.chat.id, call.message.id,
                                           reply_markup=keyboard(self.cardinal, call.message.chat.id))
        self.bot.answer_callback_query(call.id)

    def open_settings_section(self, call: types.CallbackQuery):
        """
        Открывает выбранную категорию настроек.
        """
        section = call.data.split(":")[1]
        sections = {
            "main": {"text": "Здесь вы можете включить и отключать основные функции FPC.",
                     "kb": kb.main_settings, "args": [self.cardinal]},

            "telegram": {"text": f"Здесь вы можете настроить Telegram-уведомления.\n\n"
                                 f"<b><u>Настройки для каждого чата свои!</u></b>\n\n"
                                 f"ID чата: <code>{call.message.chat.id}</code>",
                         "kb": kb.notifications_settings, "args": [self.cardinal, call.message.chat.id]},

            "blockList": {"text": f"Здесь вы можете изменить настройки черного списка. "
                                  f"Все ограничения, представленные ниже, применяются только к пользователям из ЧС.",
                          "kb": kb.block_list_settings, "args": [self.cardinal]},

            "autoResponse": {"text": f"В данном разделе вы можете изменить существующие команды или добавить новые.",
                             "kb": skb.AR_SETTINGS, "no_func": True},

            "autoDelivery": {"text": f"В данном разделе вы можете изменить настройки автовыдачи, "
                                     f"загрузить файлы с товарами и т.д.",
                             "kb": skb.AD_SETTINGS, "no_func": True},

            "newMessageView": {"text": f"В данном разделе вы можете настроить уведомления о новых сообщениях.",
                               "kb": kb.new_message_view_settings, "args": [self.cardinal]},

            "greetings": {"text": f"В данном разделе вы можете настроить приветствие новых пользователей.\n\n"
                                  f"<b>Текущий текст приветствия:</b>\n"
                                  f"<code>{utils.escape(self.cardinal.MAIN_CFG['Greetings']['greetingsText'])}</code>",
                          "kb": kb.old_users_settings, "args": [self.cardinal]},

            "orderConfirm": {"text": f"В данном разделе вы можете настроить сообщение на подтверждение заказа.\n\n"
                                     f"<b>Текущий текст сообщения:</b>\n"
                                     f"<code>{utils.escape(self.cardinal.MAIN_CFG['OrderConfirm']['replyText'])}</code>",
                             "kb": kb.order_confirm_reply_settings, "args": [self.cardinal]},

            "reviewReply": {"text": f"В данном разделе вы можете настроить текста ответа на отзывы.",
                            "kb": kb.review_reply_settings, "args": [self.cardinal]}
        }

        curr = sections[section]
        self.bot.edit_message_text(curr["text"], call.message.chat.id, call.message.id,
                                   reply_markup=curr["kb"](*curr["args"]) if not curr.get("no_func") else curr["kb"])
        self.bot.answer_callback_query(call.id)

    # Прочее
    def cancel_action(self, call: types.CallbackQuery):
        """
        Обнуляет состояние пользователя, удаляет сообщение, являющийся источником состояния.
        """
        result = self.clear_state(call.message.chat.id, call.from_user.id)
        if result is None:
            self.bot.answer_callback_query(call.id)
            return
        else:
            self.bot.delete_message(call.message.chat.id, call.message.id)
            self.bot.answer_callback_query(call.id)

    def send_announcements_kb(self, m: types.Message):
        """
        Отправляет сообщение с клавиатурой управления уведомлениями о новых объявлениях.
        """
        self.bot.send_message(m.chat.id, """В данном меню вы можете настроить уведомления о новостях.\n
Новости поделены на 2 категории:
<b><i>Объявления</i></b> - новости о грядущих обновлениях, важные сообщения и т.д.
<b><i>Реклама</i></b> - реклама различных проектов. Если вы хотите купить рекламное объявление, пишите в ЛС @woopertail.
""", reply_markup=kb.announcements_settings(self.cardinal, m.chat.id))

    def send_review_reply_text(self, c: types.CallbackQuery):
        stars = int(c.data.split(":")[1])
        text = self.cardinal.MAIN_CFG["ReviewReply"][f"star{stars}ReplyText"]
        keyboard = types.InlineKeyboardMarkup() \
            .row(types.InlineKeyboardButton("◀️ Назад", callback_data=f"{CBT.CATEGORY}:reviewReply"),
                 types.InlineKeyboardButton(f"✏️Изменить", callback_data=f"{CBT.EDIT_REVIEW_REPLY_TEXT}:{stars}"))
        if not text:
            self.bot.send_message(c.message.chat.id, f"❌ Ответ на отзыв с {'⭐' * stars} не установлен.",
                                  reply_markup=keyboard)
        else:
            self.bot.send_message(c.message.chat.id,
                                  f"Ответ на отзыв с {'⭐' * stars}:\n"
                                  f"<code>{self.cardinal.MAIN_CFG['ReviewReply'][f'star{stars}ReplyText']}</code>",
                                  reply_markup=keyboard)
        self.bot.answer_callback_query(c.id)

    def __init_commands(self):
        """
        Регистрирует хэндлеры всех команд.
        """
        self.msg_handler(self.reg_admin, func=lambda msg: msg.from_user.id not in self.authorized_users)
        self.cbq_handler(self.ignore_unauthorized_users,
                         lambda call: call.from_user.id not in self.authorized_users)
        self.cbq_handler(self.param_disabled, lambda c: c.data.startswith(CBT.PARAM_DISABLED))
        self.msg_handler(self.run_file_handlers, content_types=["document", "photo"])

        self.msg_handler(self.send_settings_menu, commands=["menu"])
        self.msg_handler(self.send_profile, commands=["profile"])
        self.cbq_handler(self.update_profile, lambda c: c.data == CBT.UPDATE_PROFILE)
        self.msg_handler(self.act_manual_delivery_test, commands=["test_lot"])
        self.msg_handler(self.act_upload_image, commands=["upload_img"])
        self.cbq_handler(self.act_edit_greetings_text, lambda c: c.data == CBT.EDIT_GREETINGS_TEXT)
        self.msg_handler(self.edit_greetings_text,
                         func=lambda m: self.check_state(m.chat.id, m.from_user.id, CBT.EDIT_GREETINGS_TEXT))
        self.cbq_handler(self.act_edit_order_confirm_reply_text, lambda c: c.data == CBT.EDIT_ORDER_CONFIRM_REPLY_TEXT)
        self.msg_handler(self.edit_order_confirm_reply_text,
                         func=lambda m: self.check_state(m.chat.id, m.from_user.id, CBT.EDIT_ORDER_CONFIRM_REPLY_TEXT))
        self.cbq_handler(self.act_edit_review_reply_text, lambda c: c.data.startswith(f"{CBT.EDIT_REVIEW_REPLY_TEXT}:"))
        self.msg_handler(self.edit_review_reply_text,
                         func=lambda m: self.check_state(m.chat.id, m.from_user.id, CBT.EDIT_REVIEW_REPLY_TEXT))
        self.msg_handler(self.manual_delivery_text,
                         func=lambda m: self.check_state(m.chat.id, m.from_user.id, CBT.MANUAL_AD_TEST))
        self.msg_handler(self.act_ban, commands=["ban"])
        self.msg_handler(self.ban, func=lambda m: self.check_state(m.chat.id, m.from_user.id, CBT.BAN))
        self.msg_handler(self.act_unban, commands=["unban"])
        self.msg_handler(self.unban, func=lambda m: self.check_state(m.chat.id, m.from_user.id, CBT.UNBAN))
        self.msg_handler(self.send_ban_list, commands=["block_list"])
        self.msg_handler(self.act_edit_watermark, commands=["watermark"])
        self.msg_handler(self.edit_watermark,
                         func=lambda m: self.check_state(m.chat.id, m.from_user.id, CBT.EDIT_WATERMARK))
        self.msg_handler(self.send_logs, commands=["logs"])
        self.msg_handler(self.del_logs, commands=["del_logs"])
        self.msg_handler(self.about, commands=["about"])
        self.msg_handler(self.check_updates, commands=["check_updates"])
        self.msg_handler(self.update, commands=["update"])
        self.msg_handler(self.send_system_info, commands=["sys"])
        self.msg_handler(self.restart_cardinal, commands=["restart"])
        self.msg_handler(self.ask_power_off, commands=["power_off"])
        self.msg_handler(self.send_announcements_kb, commands=["announcements"])
        self.cbq_handler(self.send_review_reply_text, lambda c: c.data.startswith(f"{CBT.SEND_REVIEW_REPLY_TEXT}:"))

        self.cbq_handler(self.act_send_funpay_message, lambda c: c.data.startswith(f"{CBT.SEND_FP_MESSAGE}:"))
        self.cbq_handler(self.open_reply_menu, lambda c: c.data.startswith(f"{CBT.BACK_TO_REPLY_KB}:"))
        self.cbq_handler(self.extend_new_message_notification, lambda c: c.data.startswith(f"{CBT.EXTEND_CHAT}:"))
        self.msg_handler(self.send_funpay_message,
                         func=lambda m: self.check_state(m.chat.id, m.from_user.id, CBT.SEND_FP_MESSAGE))
        self.cbq_handler(self.ask_confirm_refund, lambda call: call.data.startswith(f"{CBT.REQUEST_REFUND}:"))
        self.cbq_handler(self.cancel_refund, lambda call: call.data.startswith(f"{CBT.REFUND_CANCELLED}:"))
        self.cbq_handler(self.refund, lambda call: call.data.startswith(f"{CBT.REFUND_CONFIRMED}:"))
        self.cbq_handler(self.open_order_menu, lambda call: call.data.startswith(f"{CBT.BACK_TO_ORDER_KB}:"))
        self.cbq_handler(self.open_cp, lambda call: call.data == CBT.MAIN)
        self.cbq_handler(self.open_cp2, lambda call: call.data == CBT.MAIN2)
        self.cbq_handler(self.open_settings_section, lambda call: call.data.startswith(f"{CBT.CATEGORY}:"))
        self.cbq_handler(self.switch_param, lambda call: call.data.startswith(f"{CBT.SWITCH}:"))
        self.cbq_handler(self.switch_chat_notification, lambda call: call.data.startswith(f"{CBT.SWITCH_TG_NOTIFICATIONS}:"))
        self.cbq_handler(self.power_off, lambda call: call.data.startswith(f"{CBT.SHUT_DOWN}:"))
        self.cbq_handler(self.cancel_power_off, lambda call: call.data == CBT.CANCEL_SHUTTING_DOWN)
        self.cbq_handler(self.cancel_action, lambda c: c.data == CBT.CLEAR_USER_STATE)

    def send_notification(self, text: str | None, keyboard=None,
                          notification_type: str = utils.NotificationTypes.other, photo: bytes | None = None):
        """
        Отправляет сообщение во все чаты для уведомлений из self.notification_settings.

        :param text: текст уведомления.
        :param keyboard: экземпляр клавиатуры.
        :param notification_type: тип уведомления.
        :param photo: фотография (если нужна).
        """
        kwargs = {}
        if keyboard is not None:
            kwargs["reply_markup"] = keyboard

        for chat_id in self.notification_settings:
            if not self.is_notification_enabled(chat_id, notification_type):
                continue
            try:
                if photo:
                    new_msg = self.bot.send_photo(chat_id, photo, text, **kwargs)
                else:
                    new_msg = self.bot.send_message(chat_id, text, **kwargs)
                if notification_type == utils.NotificationTypes.bot_start:
                    self.init_messages.append((new_msg.chat.id, new_msg.id))
            except:
                logger.error("Произошла ошибка при отправке уведомления в Telegram.")
                logger.debug("TRACEBACK", exc_info=True)
                continue

    def add_command_to_menu(self, command: str, help_text: str) -> None:
        """
        Добавляет команду в список команд (в кнопке menu).

        :param command: текст команды.

        :param help_text: текст справки.
        """
        self.commands[command] = help_text

    def setup_commands(self):
        """
        Устанавливает меню команд.
        """
        commands = [types.BotCommand(f"/{i}", self.commands[i]) for i in self.commands]
        self.bot.set_my_commands(commands)

    def init(self):
        self.__init_commands()
        logger.info("$MAGENTATelegram бот инициализирован.")

    def run(self):
        """
        Запускает поллинг.
        """
        self.send_notification("""✅ Telegram-бот запущен!

✅ Сейчас вы уже <b><u>можете настраивать конфиги</u></b> и полностью <b><u>использовать функционал <i>Telegram</i>-бота</u></b>.

❌ Учтите, что <i>FunPay Cardinal</i> еще <b><u>не инициализирован</u></b> и <b><u>никакие функции не работают</u></b>.

🔃 Как только <i>FunPay Cardinal</i> инициализируется - данное сообщение изменится.

📋 Если <i>FPC</i> долго не инициализируется - проверьте логи с помощью команды /logs""",
                               notification_type=utils.NotificationTypes.bot_start)
        try:
            logger.info(f"$CYANTelegram бот $YELLOW@{self.bot.user.username} $CYANзапущен.")
            self.bot.infinity_polling(logger_level=logging.DEBUG)
        except:
            logger.error("Произошла ошибка при получении обновлений Telegram (введен некорректный токен?).")
            logger.debug("TRACEBACK", exc_info=True)
