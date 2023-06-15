"""
В данном модуле описаны все кастомные исключения, которые райзятся при валидации конфигов.
"""


class ParamNotFoundError(Exception):
    """
    Исключение, которое райзится, если при обработке конфига не был найден искомый параметр.
    """
    def __init__(self, param_name: str):
        """
        :param param_name: название параметра.
        """
        self.param_name = param_name

    def __str__(self):
        return f"Параметр \"{self.param_name}\" не найден."


class EmptyValueError(Exception):
    """
    Исключение, которое райзится, если при обработке конфига было найдено пустое значение.
    """
    def __init__(self, param_name: str):
        """
        :param param_name: название параметра.
        """
        self.param_name = param_name

    def __str__(self):
        return f"Значение параметра \"{self.param_name}\" не может быть пустым."


class ValueNotValidError(Exception):
    """
    Исключение, которое райзится, если при обработке конфига было найдено недопустимое значение.
    """
    def __init__(self, param_name: str, current_value: str, valid_values: list[str | None]):
        """
        :param param_name: название параметра.
        :param current_value: текущее значение.
        :param valid_values: допустимые значения.
        """
        self.param_name = param_name
        self.current_value = current_value
        self.valid_values = valid_values

    def __str__(self):
        return f"Недопустимое значение параметра \"{self.param_name}\". Допустимые значения: {self.valid_values}. " \
               f"Текущее значение: \"{self.current_value}\"."


class ProductsFileNotFoundError(Exception):
    """
    Исключение, которое райзится, если при обработке конфига автовыдачи не был найден указанный файл с товарами.
    """
    def __init__(self, products_file_path: str):
        self.products_file_path = products_file_path

    def __str__(self):
        return f"Указанный файл с товарами {self.products_file_path} не найден."


class NoProductsError(Exception):
    """
    Исключение, которое райзится, если в товарном файле, указанном в конфиге автовыдачи, нет товаров.
    """
    def __init__(self, products_file_path: str):
        self.products_file_path = products_file_path

    def __str__(self):
        return f"В файле {self.products_file_path} отсутствуют товары."


class NotEnoughProductsError(Exception):
    """
    Исключение, которое райзится, если запрошено больше товаров, чем есть в товарном файле.
    """
    def __init__(self, products_file_path: str, products_amount: int, request_amount: int):
        """
        :param products_file_path: путь до товарного файла.
        :param products_amount: кол-во товаров в файле.
        :param request_amount: кол-во запрошенного товара.
        """
        self.products_file_path = products_file_path
        self.products_amount = products_amount
        self.request_amount = request_amount

    def __str__(self):
        return f"В файле {self.products_file_path} недостаточно товаров. Запрошено {self.request_amount}, " \
               f"в наличии {self.products_amount}."


class NoProductVarError(Exception):
    """
    Исключение, которое райзится, если в конфиге автовыдачи указан файл с товарами, но в параметре response нет
    ни одной переменной $product.
    """
    def __init__(self):
        pass

    def __str__(self):
        return "Указан \"productsFileName\", но в параметре \"response\" отсутствует переменная $product."


class SectionNotFoundError(Exception):
    """
    Исключение, которое райзится, если при обработке конфига не была найдена обязательная секция.
    """
    def __init__(self):
        pass

    def __str__(self):
        return f"Секция отсутствует."


class SubCommandAlreadyExists(Exception):
    """
    Исключение, которое райзится, если при обработке конфига автоответчика был найден дубликат суб-команды.
    """
    def __init__(self, command: str):
        self.command = command

    def __str__(self):
        return f"Команда или суб-команда \"{self.command}\" уже существует."


class DuplicateSectionErrorWrapper(Exception):
    """
    Исключение, которое райзится, если при обработке конфига было словлено configparser.DuplicateSectionError
    """
    def __init__(self):
        pass

    def __str__(self):
        return f"Обнаружен дубликат секции."


class ConfigParseError(Exception):
    """
    Исключение, которое райзится, если при обработке конфига произошла одна из ошибок, описанных выше.
    """
    def __init__(self, config_path: str, section_name: str, exception: Exception):
        self.config_path = config_path
        self.section_name = section_name
        self.exception = exception

    def __str__(self):
        return f"Ошибка в конфиге {self.config_path}, в секции [{self.section_name}]: {self.exception}"


class FieldNotExistsError(Exception):
    """
    Исключение, которое райзится, если при загрузке плагина не было обнаружено переданное поле.
    """
    def __init__(self, field_name: str, plugin_file_name: str):
        self.field_name = field_name
        self.plugin_file_name = plugin_file_name

    def __str__(self):
        return f"Не удалось загрузить плагин {self.plugin_file_name}: отсутствует обязательное поле " \
               f"\"{self.field_name}\"."
