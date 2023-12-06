from __future__ import annotations
from typing import TYPE_CHECKING, Literal, Any, Optional
if TYPE_CHECKING:
    from .updater.runner import Runner

from requests_toolbelt import MultipartEncoder
from bs4 import BeautifulSoup
import requests
import logging
import random
import string
import json
import time

from . import types
from .common import exceptions, utils


logger = logging.getLogger("FunPayAPI.account")


class Account:
    """
    Класс для управления аккаунтом FunPay.
    """
    def __init__(self, golden_key: str, user_agent: str | None = None,
                 requests_timeout: int | float = 10, proxy: Optional[dict] = None):
        """
        :param golden_key: токен аккаунта.
        :type golden_key: str

        :param user_agent: user-agent браузера, с которого был произведен вход в аккаунт.
        :type user_agent: str

        :param requests_timeout: тайм-аут ожидания ответа на запросы.
        :type requests_timeout: int or float

        :param proxy: прокси для запросов.
        :type proxy: dict[str, str] or None
        """
        self.golden_key: str = golden_key
        """Токен (golden_key) аккаунта."""
        self.user_agent: str | None = user_agent
        """User-agent браузера, с которого был произведен вход в аккаунт."""
        self.requests_timeout: int | float = requests_timeout
        """Тайм-аут ожидания ответа на запросы."""
        self.proxy = proxy

        self.html: str | None = None
        """HTML основной страницы FunPay."""
        self.app_data: dict | None = None
        """Appdata"""
        self.id: int | None = None
        """ID аккаунта"""
        self.username: str | None = None
        """Никнейм аккаунта."""
        self.balance: int | None = None
        """Баланс аккаунта."""
        self.currency: str | None = None
        """Валюта аккаунта."""
        self.active_sales: int | None = None
        """Активные продажи."""
        self.active_purchases: int | None = None
        """Активные покупки."""

        self.csrf_token: str | None = None
        """CSRF токен."""
        self.phpsessid: str | None = None
        """PHPSESSID."""
        self.last_update: int | None = None
        """Последнее время обновления."""

        self.__initiated: bool = False

        self.__saved_chats: dict[int, types.ChatShortcut] = {}
        self.runner: Runner | None = None
        """Объект Runner'а."""

        self.__categories: list[types.Category] = []
        self.__sorted_categories: dict[int, types.Category] = {}

        self.__subcategories: list[types.SubCategory] = []
        self.__sorted_subcategories: dict[types.SubCategoryTypes, dict[int, types.SubCategory]] = {
            types.SubCategoryTypes.COMMON: {},
            types.SubCategoryTypes.CURRENCY: {}
        }

    def method(self, request_method: Literal["post", "get"], api_method: str, headers: dict, payload: Any,
               exclude_phpsessid: bool = False, raise_not_200: bool = False) -> requests.Response:
        """
        Отправляет запрос к FunPay. Добавляет в заголовки запроса user_agent и куки.

        :param request_method: метод запроса ("get" / "post").
        :type request_method: Literal["post", "get"]

        :param api_method: метод API / полная ссылка.
        :type api_method: str

        :param headers: заголовки запроса.
        :type headers: dict

        :param payload: полезная нагрузка.
        :type payload: dict

        :param exclude_phpsessid: исключить ли PHPSESSID из добавляемых куки?
        :type exclude_phpsessid: bool

        :param raise_not_200: возбуждать ли исключение, если статус код ответа != 200?
        :type raise_not_200: bool

        :return: объект ответа.
        :rtype: requests.Response
        """
        headers["cookie"] = f"golden_key={self.golden_key}"
        headers["cookie"] += f"; PHPSESSID={self.phpsessid}" if self.phpsessid and not exclude_phpsessid else ""
        if self.user_agent:
            headers["user-agent"] = self.user_agent
        link = api_method if api_method.startswith("https://funpay.com") else "https://funpay.com/" + api_method
        response = getattr(requests, request_method)(link, headers=headers, data=payload, timeout=self.requests_timeout,
                                                     proxies=self.proxy or {})

        if response.status_code == 403:
            raise exceptions.UnauthorizedError(response)
        elif response.status_code != 200 and raise_not_200:
            raise exceptions.RequestFailedError(response)
        return response

    def get(self, update_phpsessid: bool = False) -> Account:
        """
        Получает / обновляет данные об аккаунте.

        :param update_phpsessid: обновить self.phpsessid или использовать старый.
        """
        response = self.method("get", "https://funpay.com", {}, {}, update_phpsessid, raise_not_200=True)

        html_response = response.content.decode()
        parser = BeautifulSoup(html_response, "html.parser")

        username = parser.find("div", {"class": "user-link-name"})
        if not username:
            raise exceptions.UnauthorizedError(response)

        self.username = username.text
        self.app_data = json.loads(parser.find("body").get("data-app-data"))
        self.id = self.app_data["userId"]
        self.csrf_token = self.app_data["csrf-token"]

        active_sales = parser.find("span", {"class": "badge badge-trade"})
        self.active_sales = int(active_sales.text) if active_sales else 0

        active_purchases = parser.find("span", {"class": "badge badge-orders"})
        self.active_purchases = int(active_purchases.text) if active_purchases else 0

        balance_badge = parser.find("span", {"class": "badge badge-balance"})
        self.balance = float("".join(balance_badge.text.split(" ")[:-1])) if balance_badge else 0
        self.currency = balance_badge.text.split(" ")[-1] if balance_badge else ""

        cookies = response.cookies.get_dict()
        if update_phpsessid or not self.phpsessid:
            self.phpsessid = cookies["PHPSESSID"]

        if not self.is_initiated():
            self.__setup_categories(html_response)

        self.last_update = int(time.time())
        self.html = html_response
        self.__initiated = True
        return self

    def get_chat_history(self, chat_id: int | str, last_message_id: int = 99999999999999999999999,
                         interlocutor_username: str | None = None, from_id: int = 0) -> list[types.Message]:
        """
        Получает историю сообщений чата (до 100 сообщений).

        :param chat_id: ID чата (или его текстовое обозначение).
        :param last_message_id: ID сообщения, с которого начинать историю (для запроса к FunPay).
        :param interlocutor_username: никнейм собеседника. Если указан данный аргумент, отключена логика поиска автора
            сообщения, если ID не совпадает с 0 | self.id.
        :param from_id: все сообщения с ID < переданного не попадут в возвращаемый список сообщений.

        :return: список сообщений.
        """
        if not self.is_initiated():
            raise exceptions.AccountNotInitiatedError()

        headers = {
            "accept": "*/*",
            "x-requested-with": "XMLHttpRequest"
        }
        payload = {
            "node": chat_id,
            "last_message": last_message_id
        }
        response = self.method("get", f"https://funpay.com/chat/history?node={chat_id}&last_message={last_message_id}",
                               headers, payload, raise_not_200=True)

        json_response = response.json()
        if not json_response.get("chat") or not json_response["chat"].get("messages"):
            return []
        interlocutor_id = int(json_response["chat"]["node"]["name"].split("-")[2])
        return self.__parse_messages(json_response["chat"]["messages"], chat_id, interlocutor_id,
                                     interlocutor_username, from_id)

    def get_chats_histories(self, chats_data: dict[int, str | None]) -> dict[int, list[types.Message]]:
        """
        Получает историю сообщений сразу нескольких чатов (ЛС чатов!) (до 100 сообщений на 1 чат).

        :param chats_data: ID чатов и никнеймы собеседников (None, если никнейм неизвестен)
            Например: {48392847: "SLLMK", 58392098: "Amongus", 38948728: None}

        :return: словарь с историями чатов в формате {ID чата: [список сообщений]}
        """
        headers = {
            "accept": "*/*",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-requested-with": "XMLHttpRequest"
        }
        objects = [{"type": "chat_node", "id": i, "tag": "00000000",
                    "data": {"node": i, "last_message": -1, "content": ""}} for i in chats_data]
        payload = {
            "objects": json.dumps(objects),
            "request": False,
            "csrf_token": self.csrf_token
        }
        response = self.method("post", "https://funpay.com/runner/", headers, payload, raise_not_200=True)
        json_response = response.json()

        result = {}
        for i in json_response["objects"]:
            if not i.get("data"):
                result[i.get("id")] = []
                continue
            interlocutor_id = int(i["data"]["node"]["name"].split("-")[2])
            messages = self.__parse_messages(i["data"]["messages"], i.get("id"), interlocutor_id,
                                             chats_data[i.get("id")])
            result[i.get("id")] = messages
        return result

    def upload_image(self, image: str | bytes) -> int:
        """
        Выгружает изображение на сервер FunPay для дальнейшей отправки в качестве сообщения.

        :param image: путь до изображения или изображение в виде байтов.

        :return: ID изображения на FunPay.
        """
        if not self.is_initiated():
            raise exceptions.AccountNotInitiatedError()

        if isinstance(image, str):
            with open(image, "rb") as f:
                img = f.read()
        else:
            img = image

        fields = {
            'file': ("funpay_cardinal_image.png", img, "image/png"),
            'file_id': "0"
        }
        boundary = '----WebKitFormBoundary' \
                   + ''.join(random.sample(string.ascii_letters + string.digits, 16))
        m = MultipartEncoder(fields=fields, boundary=boundary)

        headers = {
            "accept": "*/*",
            "x-requested-with": "XMLHttpRequest",
            "content-type": m.content_type,
        }

        link = "https://funpay.com/file/addChatImage"
        response = self.method("post", link, headers, m)

        if response.status_code == 400:
            try:
                json_response = response.json()
                message = json_response.get("msg")
                raise exceptions.ImageUploadError(response, message)
            except requests.exceptions.JSONDecodeError:
                raise exceptions.ImageUploadError(response, None)
        elif response.status_code != 200:
            raise exceptions.RequestFailedError(response)

        if not (document_id := response.json().get("fileId")):
            raise exceptions.ImageUploadError(response, None)
        return int(document_id)

    def send_message(self, chat_id: int, text: str | None, chat_name: str | None = None,
                     image_id: int | None = None, add_to_ignore_list: bool = True,
                     update_last_saved_message: bool = False) -> types.Message:
        """
        Отправляет сообщение в чат.

        :param chat_id: ID чата.
        :param text: текст сообщения.
        :param chat_name: название чата (для возвращаемого объекта сообщения).
        :param image_id: ID изображения.
        :param add_to_ignore_list: добавлять ли ID отправленного сообщения в игнорируемый список Runner'а?
        :param update_last_saved_message: обновлять ли последнее сохраненное сообщение на отправленное в Runner'е?

        :return: экземпляр сообщения.
        """
        if not self.is_initiated():
            raise exceptions.AccountNotInitiatedError()

        headers = {
            "accept": "*/*",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-requested-with": "XMLHttpRequest"
        }
        request = {
            "action": "chat_message",
            "data": {"node": chat_id, "last_message": -1, "content": text}
        }

        if image_id is not None:
            request["data"]["image_id"] = image_id
            request["data"]["content"] = ""
        else:
            request["data"]["content"] = text

        objects = [
            {
                "type": "chat_node",
                "id": chat_id,
                "tag": "00000000",
                "data": {"node": chat_id, "last_message": -1, "content": ""}
            }
        ]
        payload = {
            "objects": json.dumps(objects),
            "request": json.dumps(request),
            "csrf_token": self.csrf_token
        }

        link = "https://funpay.com/runner/"
        response = self.method("post", link, headers, payload, raise_not_200=True)

        json_response = response.json()

        if json_response.get("response"):
            if json_response.get("response").get("error") is not None:
                raise exceptions.MessageNotDeliveredError(response, json_response.get("error"), chat_id)

            mes = json_response["objects"][0]["data"]["messages"][-1]
            parser = BeautifulSoup(mes["html"], "html.parser")
            try:
                if image_link := parser.find("a", {"class": "chat-img-link"}):
                    image_link = image_link.get("href")
                    message_text = None
                else:
                    message_text = parser.find("div", {"class": "chat-msg-text"}).text
            except Exception as e:
                logger.debug("SEND_MESSAGE RESPONSE")
                logger.debug(response.content.decode())
                raise e

            message_obj = types.Message(int(mes["id"]), message_text, chat_id, chat_name,
                                        self.username, self.id, mes["html"], image_link)
            if self.runner:
                if add_to_ignore_list:
                    self.runner.mark_as_by_bot(chat_id, message_obj.id)
                if update_last_saved_message:
                    self.runner.update_last_message(chat_id, message_text)
            return message_obj
        else:
            raise exceptions.MessageNotDeliveredError(response, None, chat_id)

    def send_review(self, order_id: str, text: str, rating: int) -> str:
        """
        Отправляет отзыв / ответ на отзыв.

        :param order_id: ID заказа.
        :param text: текст отзыва.
        :param rating: рейтинг (от 1 до 5).

        :return: ответ FunPay (HTML-код блока отзыва).
        """
        if not self.is_initiated():
            raise exceptions.AccountNotInitiatedError()

        headers = {
            "accept": "*/*",
            "x-requested-with": "XMLHttpRequest"
        }
        payload = {
            "authorId": self.id,
            "text": text,
            "rating": rating,
            "csrf_token": self.csrf_token,
            "orderId": order_id
        }

        response = self.method("post", "https://funpay.com/orders/review", headers, payload)
        if response.status_code == 400:
            json_response = response.json()
            msg = json_response.get("msg")
            raise exceptions.FeedbackEditingError(response, msg, order_id)
        elif response.status_code != 200:
            raise exceptions.RequestFailedError(response)

        return response.json().get("content")

    def delete_review(self, order_id: str) -> str:
        """
        Удаляет отзыв / ответ на отзыв.

        :param order_id: ID заказа.

        :return: ответ FunPay (HTML-код блока отзыва).
        """
        if not self.is_initiated():
            raise exceptions.AccountNotInitiatedError()

        headers = {
            "accept": "*/*",
            "x-requested-with": "XMLHttpRequest"
        }
        payload = {
            "authorId": self.id,
            "csrf_token": self.csrf_token,
            "orderId": order_id
        }

        response = self.method("post", "https://funpay.com/orders/reviewDelete", headers, payload)

        if response.status_code == 400:
            json_response = response.json()
            msg = json_response.get("msg")
            raise exceptions.FeedbackEditingError(response, msg, order_id)
        elif response.status_code != 200:
            raise exceptions.RequestFailedError(response)

        return response.json().get("content")

    def refund(self, order_id):
        """
        Оформляет возврат средств за заказ.

        :param order_id: ID заказа.
        """
        if not self.is_initiated():
            raise exceptions.AccountNotInitiatedError()

        headers = {
            "accept": "*/*",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-requested-with": "XMLHttpRequest",
        }

        payload = {
            "id": order_id,
            "csrf_token": self.csrf_token
        }

        response = self.method("post", "https://funpay.com/orders/refund", headers, payload, raise_not_200=True)

        if response.json().get("error"):
            raise exceptions.RefundError(response, response.json().get("msg"), order_id)

    def get_raise_modal(self, category_id: int, subcategory_id: int) -> dict:
        """
        Отправляет запрос на получение modal-формы для поднятия лотов категории (игры).
        !ВНИМАНИЕ! Если на аккаунте только 1 подкатегория, относящаяся переданной категории (игре),
        то FunPay поднимет лоты данной подкатегории без отправления modal-формы с выбором других подкатегорий.

        :param category_id: ID категории (игры).
        :param subcategory_id: ID любой подкатегории, относящейся к переданной категории.

        :return: ответ FunPay.
        """
        if not self.is_initiated():
            raise exceptions.AccountNotInitiatedError()
        headers = {
            "accept": "*/*",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-requested-with": "XMLHttpRequest"
        }
        payload = {
            "game_id": category_id,
            "node_id": subcategory_id
        }
        response = self.method("post", "https://funpay.com/lots/raise", headers, payload, raise_not_200=True)
        json_response = response.json()
        return json_response

    def raise_subcategories(self, category_id: int, subcategory_id: int, exclude: list[int] | None = None) \
            -> types.RaiseResponse:
        """
        Поднимает все лоты всех подкатегорий переданной категории (игры).

        :param category_id: ID категории (игры).
        :param subcategory_id: ID любой подкатегории, относящейся к переданной категории.
        :param exclude: ID подкатегорий, которые не нужно поднимать.

        :return: ответ FunPay.
        """
        if not self.is_initiated():
            raise exceptions.AccountNotInitiatedError()
        check = self.get_raise_modal(category_id, subcategory_id)

        if check.get("error") and check.get("msg") and "Подождите" in check.get("msg"):
            wait_time = utils.parse_wait_time(check.get("msg"))
            return types.RaiseResponse(False, wait_time, [], check)
        elif check.get("error"):
            # Если вернулся ответ с ошибкой и это не "Подождите n времени" - значит творится какая-то дичь.
            return types.RaiseResponse(False, 10, [], check)
        elif check.get("error") is not None and not check.get("error"):
            # Если была всего 1 категория и FunPay ее поднял без отправки modal-окна
            return types.RaiseResponse(True, 3600,
                                       [self.get_subcategory(types.SubCategoryTypes.COMMON, subcategory_id)], check)
        elif check.get("modal"):
            # Если же появилась модалка,
            # парсим все чекбоксы и отправляем запрос на поднятие всех категорий, кроме тех,
            # которые в exclude.
            parser = BeautifulSoup(check.get("modal"), "html.parser")
            subcategories = []
            checkboxes = parser.find_all("div", {"class": "checkbox"})
            for cb in checkboxes:
                subcategory_id = int(cb.find("input")["value"])
                if exclude is None or subcategory_id not in exclude:
                    subcategories.append(self.get_subcategory(types.SubCategoryTypes.COMMON, subcategory_id))

            headers = {
                "accept": "*/*",
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                "x-requested-with": "XMLHttpRequest"
            }
            payload = {
                "game_id": category_id,
                "node_id": subcategory_id,
                "node_ids[]": [i.id for i in subcategories]
            }

            response = self.method("post", "https://funpay.com/lots/raise", headers, payload, raise_not_200=True)
            json_response = response.json()
            logger.debug(f"Ответ FunPay (поднятие категорий): {json_response}.")
            if not json_response.get("error"):
                return types.RaiseResponse(True, 3600, subcategories, json_response)
            else:
                return types.RaiseResponse(False, 10, [], json_response)

    def get_user(self, user_id: int) -> types.UserProfile:
        """
        Парсит страницу пользователя.

        :param user_id: ID пользователя.

        :return: объект профиля пользователя.
        """
        if not self.is_initiated():
            raise exceptions.AccountNotInitiatedError()

        headers = {
            "accept": "*/*"
        }

        response = self.method("get", f"https://funpay.com/users/{user_id}/", headers, {}, raise_not_200=True)
        html_response = response.content.decode()
        parser = BeautifulSoup(html_response, "html.parser")

        username = parser.find("div", {"class": "user-link-name"})
        if not username:
            raise exceptions.UnauthorizedError(response)

        username = parser.find("span", {"class": "mr4"}).text
        user_status = parser.find("span", {"class": "media-user-status"})
        user_status = user_status.text if user_status else ""
        avatar_link = parser.find("div", {"class": "avatar-photo"}).get("style").split("(")[1].split(")")[0]
        avatar_link = avatar_link if avatar_link.startswith("https") else f"https://funpay.com{avatar_link}"
        banned = bool(parser.find("span", {"class": "label label-danger"}))
        user_obj = types.UserProfile(user_id, username, avatar_link, "Онлайн" in user_status, banned, html_response)

        subcategories_divs = parser.find_all("div", {"class": "offer-list-title-container"})

        if not subcategories_divs:
            return user_obj

        for i in subcategories_divs:
            subcategory_link = i.find("h3").find("a").get("href")
            subcategory_id = int(subcategory_link.split("/")[-2])
            subcategory_type = types.SubCategoryTypes.CURRENCY if "chips" in subcategory_link else \
                types.SubCategoryTypes.COMMON
            subcategory_obj = self.get_subcategory(subcategory_type, subcategory_id)
            if not subcategory_obj:
                continue

            offers = i.parent.find_all("a", {"class": "tc-item"})
            for j in offers:
                offer_id = j["href"].split("id=")[1]
                description = j.find("div", {"class": "tc-desc-text"})
                description = description.text if description else None
                server = j.find("div", {"class": "tc-server hidden-xxs"})
                if not server:
                    server = j.find("div", {"class": "tc-server hidden-xs"})
                server = server.text if server else None

                if subcategory_obj.type is types.SubCategoryTypes.COMMON:
                    price = float(j.find("div", {"class": "tc-price"})["data-s"])
                else:
                    price = float(j.find("div", {"class": "tc-price"}).find("div").text.split(" ")[0])

                lot_obj = types.LotShortcut(offer_id, server, description, price, subcategory_obj, str(j))
                user_obj.add_lot(lot_obj)
        return user_obj

    def get_chat(self, chat_id: int) -> types.Chat:
        """
        Получает информацию о чате.
        :param chat_id: ID чата.
        :return: объект чата.
        """
        if not self.is_initiated():
            raise exceptions.AccountNotInitiatedError()
        headers = {
            "accept": "*/*"
        }
        response = self.method("get", f"https://funpay.com/chat/?node={chat_id}", headers, {}, raise_not_200=True)
        html_response = response.content.decode()
        parser = BeautifulSoup(html_response, "html.parser")
        if (name := parser.find("div", {"class": "chat-header"}).find("div", {"class": "media-user-name"}).find("a").text) == "Чат":
            raise Exception("chat not found")  # todo

        if not (chat_panel := parser.find("div", {"class": "param-item chat-panel"})):
            text, link = None, None
        else:
            a = chat_panel.find("a")
            text, link = a.text, a["href"]

        history = self.get_chat_history(chat_id, interlocutor_username=name)
        return types.Chat(chat_id, name, link, text, html_response, history)

    def get_order(self, order_id: str) -> types.Order:
        """
        Получает полную информацию о заказе.

        :param order_id: ID заказа.

        :return: объекст заказа.
        """
        if not self.is_initiated():
            raise exceptions.AccountNotInitiatedError()
        headers = {
            "accept": "*/*"
        }
        response = self.method("get", f"https://funpay.com/orders/{order_id}/", headers, {}, raise_not_200=True)
        html_response = response.content.decode()
        parser = BeautifulSoup(html_response, "html.parser")
        username = parser.find("div", {"class": "user-link-name"})
        if not username:
            raise exceptions.UnauthorizedError(response)

        if (span := parser.find("span", {"class": "text-warning"})) and span.text == "Возврат":
            status = types.OrderStatuses.REFUNDED
        elif (span := parser.find("span", {"class": "text-success"})) and span.text == "Закрыт":
            status = types.OrderStatuses.CLOSED
        else:
            status = types.OrderStatuses.PAID

        short_description = None
        full_description = None
        sum_ = None
        subcategory = None
        for div in parser.find_all("div", {"class": "param-item"}):
            if not (h := div.find("h5")):
                continue
            if h.text == "Краткое описание":
                short_description = div.find("div").text
            elif h.text == "Подробное описание":
                full_description = div.find("div").text
            elif h.text == "Сумма":
                sum_ = float(div.find("span").text)
            elif h.text == "Категория":
                subcategory_link = div.find("a").get("href")
                subcategory_split = subcategory_link.split("/")
                subcategory_id = int(subcategory_split[-2])
                subcategory_type = types.SubCategoryTypes.COMMON if "lots" in subcategory_link else \
                    types.SubCategoryTypes.CURRENCY
                subcategory = self.get_subcategory(subcategory_type, subcategory_id)

        chat = parser.find("div", {"class": "chat-header"})
        chat_link = chat.find("div", {"class": "media-user-name"}).find("a")
        interlocutor_name = chat_link.text
        interlocutor_id = int(chat_link.get("href").split("/")[-2])
        nav_bar = parser.find("ul", {"class": "nav navbar-nav navbar-right logged"})
        active_item = nav_bar.find("li", {"class": "active"})
        if "Продажи" in active_item.find("a").text.strip():
            buyer_id, buyer_username = interlocutor_id, interlocutor_name
            seller_id, seller_username = self.id, self.username
        else:
            buyer_id, buyer_username = self.id, self.username
            seller_id, seller_username = interlocutor_id, interlocutor_name

        review_obj = parser.find("div", {"class": "order-review"})
        if not (stars_obj := review_obj.find("div", {"class": "rating"})):
            stars, text,  = None, None
        else:
            stars = int(stars_obj.find("div").get("class")[0].split("rating")[1])
            text = review_obj.find("div", {"class": "review-item-text"}).text.strip()

        if not (reply_obj := review_obj.find("div", {"class": "review-item-answer review-compiled-reply"})):
            reply = None
        else:
            reply = reply_obj.find("div").text.strip()

        if all([not text, not reply]):
            review = None
        else:
            review = types.Review(stars, text, reply, False, str(reply_obj), order_id, buyer_username, buyer_id)

        order = types.Order(order_id, status, subcategory, short_description, full_description, sum_,
                            buyer_id, buyer_username, seller_id, seller_username, html_response, review)
        return order

    def get_sales(self, start_from: str | None = None, include_paid: bool = True, include_closed: bool = True,
                  include_refunded: bool = True, exclude_ids: list[str] | None = None,
                  **filters) -> tuple[str | None, list[types.OrderShortcut]]:
        """
        Получает и парсит список заказов со страницы https://funpay.com/orders/trade

        :param start_from: ID заказа, с которого начать список (ID заказа должен быть без '#'!).
        :param include_paid: включить ли в список заказы, ожидающие выполнения?
        :param include_closed: включить ли в список закрытые заказы?
        :param include_refunded: включить ли в список заказы, за которые запрошен возврат средств?
        :param exclude_ids: исключить заказы с ID из списка (ID заказа должен быть без '#'!).
        :param filters: фильтры FunPay:
            id: ID заказа.
            buyer: никнейм покупателя.
            state: состояние заказа:
                paid - оплачен и ожидает выполнения.
                closed - выполнен.
                refunded - запрошен возврат средств.
            game: ID игры.
            section: ID категории формата <тип лота>-<ID категории>.
                lot - стандартный лот (например: lot-256)
                chip - игровая валюта (например: chip-4471)
            server: ID сервера.
            side: ID стороны (платформы).

        :return: (ID след. заказа (для start_from), список заказов)
        """
        if not self.is_initiated():
            raise exceptions.AccountNotInitiatedError()

        exclude_ids = exclude_ids or []
        link = "https://funpay.com/orders/trade?"

        for name in filters:
            link += f"{name}={filters[name]}&"
        link = link[:-1]

        if start_from:
            filters["continue"] = start_from

        response = self.method("post" if start_from else "get", link, {}, filters, raise_not_200=True)
        html_response = response.content.decode()

        parser = BeautifulSoup(html_response, "html.parser")
        check_user = parser.find("div", {"class": "content-account content-account-login"})
        if check_user:
            raise exceptions.UnauthorizedError(response)

        next_order_id = parser.find("input", {"type": "hidden", "name": "continue"})
        if not next_order_id:
            next_order_id = None
        else:
            next_order_id = next_order_id.get("value")

        order_divs = parser.find_all("a", {"class": "tc-item"})
        if not order_divs:
            return None, []

        sells = []
        for div in order_divs:
            classname = div.get("class")
            if "warning" in classname:
                if not include_refunded:
                    continue
                order_status = types.OrderStatuses.REFUNDED
            elif "info" in classname:
                if not include_paid:
                    continue
                order_status = types.OrderStatuses.PAID
            else:
                if not include_closed:
                    continue
                order_status = types.OrderStatuses.CLOSED

            order_id = div.find("div", {"class": "tc-order"}).text[1:]
            if order_id in exclude_ids:
                continue

            description = div.find("div", {"class": "order-desc"}).find("div").text
            price = float(div.find("div", {"class": "tc-price"}).text.split(" ")[0])

            buyer_div = div.find("div", {"class": "media-user-name"}).find("span")
            buyer_username = buyer_div.text
            buyer_id = int(buyer_div.get("data-href")[:-1].split("https://funpay.com/users/")[1])

            order_obj = types.OrderShortcut(order_id, description, price, buyer_username, buyer_id, order_status,
                                            str(div))
            sells.append(order_obj)

        return next_order_id, sells

    def add_chats(self, chats: list[types.ChatShortcut]):
        """
        Сохраняет чаты.

        :param chats: объекты чатов.
        """
        for i in chats:
            self.__saved_chats[i.id] = i

    def request_chats(self) -> list[types.ChatShortcut]:
        """
        Запрашивает чаты и парсит их.

        :return: объекты чатов.
        """
        chats = {
            "type": "chat_bookmarks",
            "id": self.id,
            "tag": utils.random_tag(),
            "data": False
        }
        payload = {
            "objects": json.dumps([chats]),
            "request": False,
            "csrf_token": self.csrf_token
        }
        headers = {
            "accept": "*/*",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-requested-with": "XMLHttpRequest"
        }
        response = self.method("post", "https://funpay.com/runner/", headers, payload, raise_not_200=True)
        json_response = response.json()

        msgs = ""
        for obj in json_response["objects"]:
            if obj.get("type") != "chat_bookmarks":
                continue
            msgs = obj["data"]["html"]
        if not msgs:
            return []

        parser = BeautifulSoup(msgs, "html.parser")
        chats = parser.find_all("a", {"class": "contact-item"})
        chats_objs = []

        for msg in chats:
            chat_id = int(msg["data-id"])
            last_msg_text = msg.find("div", {"class": "contact-item-message"}).text
            unread = True if "unread" in msg.get("class") else False
            chat_with = msg.find("div", {"class": "media-user-name"}).text
            chat_obj = types.ChatShortcut(chat_id, chat_with, last_msg_text, unread, str(msg))
            chats_objs.append(chat_obj)
        return chats_objs

    def get_chats(self, update: bool = False) -> dict[int, types.ChatShortcut]:
        """
        Возвращает словарь с сохраненными чатами ({id: types.ChatShortcut})

        :param update: обновлять ли предварительно список чатов?
        """
        if not self.is_initiated():
            raise exceptions.AccountNotInitiatedError()
        if update:
            chats = self.request_chats()
            self.add_chats(chats)
        return self.__saved_chats

    def get_chat_by_name(self, name: str, make_request: bool = False) -> types.ChatShortcut | None:
        """
        Возвращает чат по его названию (если он сохранен).

        :param name: название чата.
        :param make_request: обновить ли сохраненные чаты, если чат не был найден?
        """
        if not self.is_initiated():
            raise exceptions.AccountNotInitiatedError()

        for i in self.__saved_chats:
            if self.__saved_chats[i].name == name:
                return self.__saved_chats[i]

        if make_request:
            self.add_chats(self.request_chats())
            return self.get_chat_by_name(name)
        else:
            return None

    def get_chat_by_id(self, chat_id: int, make_request: bool = False) -> types.ChatShortcut | None:
        """
        Возвращает чат по его ID (если он сохранен).

        :param chat_id: ID чата.
        :param make_request: обновить ли сохраненные чаты, если чат не был найден?
        """
        if not self.is_initiated():
            raise exceptions.AccountNotInitiatedError()

        if not make_request or chat_id in self.__saved_chats:
            return self.__saved_chats.get(chat_id)

        self.add_chats(self.request_chats())
        return self.get_chat_by_id(chat_id)

    def get_lot_fields(self, lot_id: int, subcategory_id: int) -> types.LotFields:
        """
        Получает все поля лота.

        :param lot_id: ID лота.
        :param subcategory_id: подкатегория лота.

        :return: экземпляр класса types.LotFields со всей информацией о лоте.
        """
        if not self.is_initiated():
            raise exceptions.AccountNotInitiatedError()
        headers = {
            "accept": "*/*",
            "content-type": "application/json",
            "x-requested-with": "XMLHttpRequest",
        }
        query = f"?tag={utils.random_tag()}&offer={lot_id}&node={subcategory_id}"
        response = self.method("get", f"https://funpay.com/lots/offerEdit{query}", headers, {}, raise_not_200=True)

        json_response = response.json()
        parser = BeautifulSoup(json_response["html"], "html.parser")

        input_fields = parser.find_all("input")
        text_fields = parser.find_all("textarea")
        selection_fields = parser.find_all("select")
        checkboxes = parser.find_all("input", {"type": "checkbox"}, checked=True)
        result = {}

        for field in input_fields:
            name = field["name"]
            if name in ["active", "deactivate_after_sale"]:
                continue
            else:
                result[name] = field.get("value") or ""

        for field in text_fields:
            name = field["name"]
            result[name] = field.text or ""

        for field in selection_fields:
            name = field["name"]
            result[name] = field.find("option", selected=True)["value"]

        for field in checkboxes:
            name = field["name"]
            if name == "active":
                result[name] = "on"
            elif name == "deactivate_after_sale":
                result["deactivate_after_sale[]"] = "on"

        if "deactivate_after_sale[]" not in result:
            result["deactivate_after_sale"] = ""

        return types.LotFields(lot_id, subcategory_id, result)

    def save_lot(self, lot_fields: types.LotFields):
        """
        Сохраняет лот на FunPay.

        :param lot_fields: экземпляр класса types.LotFileds, получаемый с помощью Account.get_lot_fields().
        """
        if not self.is_initiated():
            raise exceptions.AccountNotInitiatedError()
        headers = {
            "accept": "*/*",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-requested-with": "XMLHttpRequest",
        }
        fields = lot_fields.renew_fields().get_fields()
        fields["location"] = "trade"

        response = self.method("post", "https://funpay.com/lots/offerSave", headers, fields, raise_not_200=True)
        json_response = response.json()
        if json_response.get("error"):
            raise exceptions.LotSavingError(response, json_response.get("error"), lot_fields.lot_id,
                                            lot_fields.subcategory_id)

    def get_category(self, category_id: int) -> types.Category | None:
        """
        Возвращает объект категории (игры).

        :param category_id: ID категории (игры).
        """
        return self.__sorted_categories.get(category_id)

    def get_categories(self) -> list[types.Category]:
        """
        Возвращает все категории (игры) FunPay (парсятся при первом выполнении метода Account.get).
        """
        return self.__categories

    def get_sorted_categories(self) -> dict[int, types.Category]:
        """
        Возвращает все категории (игры) FunPay в виде словаря {ID: категория}
        (парсятся при первом выполнении метода Account.get).
        """
        return self.__sorted_categories

    def get_subcategory(self, subcategory_type: types.SubCategoryTypes,
                        subcategory_id: int) -> types.SubCategory | None:
        """
        Возвращает объект подкатегории.

        :param subcategory_type: тип подкатегории.
        :param subcategory_id: ID подкатегории.
        """
        return self.__sorted_subcategories[subcategory_type].get(subcategory_id)

    def get_subcategories(self) -> list[types.SubCategory]:
        """
        Возвращает все подкатегории FunPay (парсятся при первом выполнении метода Account.get).
        """
        return self.__subcategories

    def get_sorted_subcategories(self):
        """
        Возвращает все подкатегории FunPay в виде словаря {type: {ID: подкатегория}}
        (парсятся при первом выполнении метода Account.get).
        """
        return self.__sorted_subcategories

    def is_initiated(self) -> bool:
        """
        Инициализирован ли класс Account с помощью метода Account.get()?

        :return: True / False
        """
        return self.__initiated

    def __setup_categories(self, html: str):
        """
        Парсит категории и подкатегории с основной страницы и добавляет их в свойства класса.

        :param html: HTML страница.
        """
        parser = BeautifulSoup(html, "html.parser")
        games_table = parser.find_all("div", {"class": "promo-game-list"})
        if not games_table:
            return

        games_table = games_table[1] if len(games_table) > 1 else games_table[0]
        games_divs = games_table.find_all("div", {"class": "promo-game-item"})
        if not games_divs:
            return

        for i in games_divs:
            game_id = int(i.find("div", {"class": "game-title"}).get("data-id"))
            game_title = i.find("a").text
            game_obj = types.Category(game_id, game_title)
            subcategories_divs = i.find_all("li")

            for j in subcategories_divs:
                subcategory_name = j.find("a").text
                link = j.find("a").get("href")
                subcategory_type = types.SubCategoryTypes.CURRENCY if "chips" in link else types.SubCategoryTypes.COMMON
                subcategory_id = int(link.split("/")[-2])

                subcategory_obj = types.SubCategory(subcategory_id, subcategory_name, subcategory_type, game_obj)
                game_obj.add_subcategory(subcategory_obj)
                self.__subcategories.append(subcategory_obj)
                self.__sorted_subcategories[subcategory_type][subcategory_id] = subcategory_obj

            self.__categories.append(game_obj)
            self.__sorted_categories[game_id] = game_obj

    def __parse_messages(self, json_messages: dict, chat_id: int | str,
                         interlocutor_id: int, interlocutor_username: str | None,
                         from_id: int = 0) -> list[types.Message]:
        messages = []

        ids = {
            self.id: self.username,
            0: "FunPay",
            interlocutor_id: interlocutor_username
        }

        for i in json_messages:
            if i["id"] < from_id:
                continue
            author_id = i["author"]
            parser = BeautifulSoup(i["html"], "html.parser")
            # Если ник написавшего неизвестен, но он есть в HTML-коде сообщения
            if not ids.get(author_id) and (author_div := parser.find("div", {"class": "media-user-name"})):
                author = author_div.find("a").text.strip()
                ids[author_id] = author
                if author_id == interlocutor_id and not interlocutor_username:
                    interlocutor_username = author
                    ids[interlocutor_id] = interlocutor_username

            if image_link := parser.find("a", {"class": "chat-img-link"}):
                image_link = image_link.get("href")
                message_text = None
            else:
                if author_id == 0:
                    message_text = parser.find("div", {"class": "alert alert-with-icon alert-info"}).text.strip()
                else:
                    message_text = parser.find("div", {"class": "chat-msg-text"}).text

            message_obj = types.Message(i["id"], message_text, chat_id, interlocutor_username,
                                        None, author_id, i["html"], image_link, determine_msg_type=False)
            if author_id != 0:
                message_obj.type = types.MessageTypes.NON_SYSTEM
            else:
                message_obj.type = message_obj.get_message_type()
            messages.append(message_obj)

        # todo
        debug_text = ""
        for i in messages:
            i.author = ids.get(i.author_id)
            i.chat_name = interlocutor_username
            debug_text += f"{i.author} | {i.author_id} | {str(i)[:20]} /\\"
        logger.debug(debug_text)

        return messages
