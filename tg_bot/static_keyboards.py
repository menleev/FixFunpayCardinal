from telebot.types import InlineKeyboardMarkup as K, InlineKeyboardButton as B
from tg_bot import CBT


CLEAR_STATE_BTN = K().add(B("❌ Отмена", callback_data=CBT.CLEAR_USER_STATE))


UPDATE_PROFILE_BTN = K().add(B("🔄 Обновить", callback_data=CBT.UPDATE_PROFILE))


SETTINGS_SECTIONS = K() \
        .add(B("⚙️ Глобальные переключатели", callback_data=f"{CBT.CATEGORY}:main")) \
        .add(B("🔔 Настройки уведомлений", callback_data=f"{CBT.CATEGORY}:telegram")) \
        .add(B("🤖 Настройки автоответа", callback_data=f"{CBT.CATEGORY}:autoResponse")) \
        .add(B("📦 Настройки автовыдачи", callback_data=f"{CBT.CATEGORY}:autoDelivery")) \
        .add(B("🚫 Настройки черного списка",  callback_data=f"{CBT.CATEGORY}:blockList")) \
        .add(B("📝 Заготовки ответов", callback_data=f"{CBT.TMPLT_LIST}:0")) \
        .add(B("▶️ Еще", callback_data=CBT.MAIN2))


SETTINGS_SECTIONS_2 = K() \
        .add(B("👋 Приветственное сообщение", callback_data=f"{CBT.CATEGORY}:greetings")) \
        .add(B("✅ Ответ на подтверждение заказа", callback_data=f"{CBT.CATEGORY}:orderConfirm")) \
        .add(B("⭐ Ответ на отзывы", callback_data=f"{CBT.CATEGORY}:reviewReply")) \
        .add(B("✉️ Вид увед. о новых сообщениях", callback_data=f"{CBT.CATEGORY}:newMessageView")) \
        .add(B("🧩 Управление плагинами", callback_data=f"{CBT.PLUGINS_LIST}:0")) \
        .add(B("📁 Управление конфиг-файлами", callback_data="config_loader")) \
        .add(B("◀️ Назад", callback_data=CBT.MAIN))


AR_SETTINGS = K() \
        .add(B("✏️ Редактировать существующие команды", callback_data=f"{CBT.CMD_LIST}:0")) \
        .add(B("➕ Добавить команду / сет команд", callback_data=CBT.ADD_CMD)) \
        .add(B("◀️ Назад", callback_data=CBT.MAIN))


AD_SETTINGS = K() \
        .add(B("🗳️ Редактировать автовыдачу лотов", callback_data=f"{CBT.AD_LOTS_LIST}:0")) \
        .add(B("➕ Добавить автовыдачу лоту", callback_data=f"{CBT.FP_LOTS_LIST}:0"))\
        .add(B("📋 Редактировать товарные файлы", callback_data=f"{CBT.PRODUCTS_FILES_LIST}:0"))\
        .row(B("⤴️ Выгрузить товарный файл", callback_data=CBT.UPLOAD_PRODUCTS_FILE),
             B("➕ Новый товарный файл", callback_data=CBT.CREATE_PRODUCTS_FILE))\
        .add(B("◀️ Назад", callback_data=CBT.MAIN))


CONFIGS_UPLOADER = K() \
        .add(B("⤵️ Загрузить основной конфиг", callback_data=f"{CBT.DOWNLOAD_CFG}:main")) \
        .add(B("⤵️ Загрузить конфиг автоответа", callback_data=f"{CBT.DOWNLOAD_CFG}:autoResponse")) \
        .add(B("⤵️ Загрузить конфиг автовыдачи", callback_data=f"{CBT.DOWNLOAD_CFG}:autoDelivery")) \
        .add(B("⤴️ Выгрузить основной конфиг", callback_data="upload_main_config")) \
        .add(B("⤴️ Выгрузить конфиг автоответа", callback_data="upload_auto_response_config")) \
        .add(B("⤴️ Выгрузить конфиг автовыдачи", callback_data="upload_auto_delivery_config")) \
        .add(B("◀️ Назад", callback_data=CBT.MAIN2))
