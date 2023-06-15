"""
Проверка на обновления.
"""
import requests
import os
import zipfile
import shutil
import json


HEADERS = {
    "accept": "application/vnd.github+json"
}


class Release:
    def __init__(self, name: str, description: str, sources_link: str, exe_link: str):
        self.name = name
        self.description = description
        self.sources_link = sources_link
        self.exe_link = exe_link


def get_tags() -> list[str] | None:
    """
    Получает все теги с GitHub репозитория.

    :return: список тегов.
    """
    response = requests.get("/tags", headers=HEADERS)
    if not response.status_code == 200:
        return None
    json_response = response.json()
    tags = [i.get("name") for i in json_response]
    return tags


def get_next_tag(tags: list[str], current_tag: str):
    """
    Ищет след. тег после переданного.
    Если не находит текущий тег - возвращает первый.
    Если текущий тег последний - возвращает None.

    :param tags: список тегов.
    :param current_tag: текущий тег.

    :return: след. тег / первый тег / None
    """
    try:
        curr_index = tags.index(current_tag)
    except ValueError:
        return tags[len(tags)-1]

    if curr_index == 0:
        return None
    return tags[curr_index-1]


def get_release(tag: str) -> Release | None:
    """
    Получает данные о релизе.

    :param tag: тег релиза.

    :return: данные релиза.
    """
    response = requests.get(f"tags/{tag}",
                            headers=HEADERS)
    if not response.status_code == 200:
        return None
    json_response = response.json()
    name = json_response.get("name")
    description = json_response.get("body")
    sources = json_response.get("zipball_url")
    assets = json_response.get("assets")
    exe = assets[0].get("browser_download_url")
    return Release(name, description, sources, exe)


def download_update(url: str):
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open("storage/cache/update.zip", 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)


def extract() -> str:
    """
    Разархивирует update.zip.

    :return: название папки внутри storage/cache/update
    """
    if os.path.exists("storage/cache/update/"):
        shutil.rmtree("storage/cache/update/", ignore_errors=True)

    os.makedirs("storage/cache/update")

    with zipfile.ZipFile("storage/cache/update.zip", "r") as zip:
        folder_name = zip.filelist[0].filename
        zip.extractall("storage/cache/update/")
    return folder_name


def zipdir(path, zip_obj):
    for root, dirs, files in os.walk(path):
        for file in files:
            zip_obj.write(os.path.join(root, file),
                          os.path.relpath(os.path.join(root, file),
                                          os.path.join(path, '..')))


def create_backup():
    """
    Создает бэкап с папками configs и storage.
    """
    with zipfile.ZipFile("backup.zip", "w") as zip:
        zipdir("storage", zip)
        zipdir("configs", zip)


def update(folder_name: str):
    update_path = os.path.join("storage/cache/update", folder_name)
    if not os.path.exists(update_path):
        return None

    if os.path.exists(os.path.join(update_path, "delete.json")):
        with open(os.path.join(update_path, "delete.json"), "r", encoding="utf-8") as f:
            data = json.loads(f.read())
            for i in data:
                if not os.path.exists(i):
                    continue
                if os.path.isfile(i):
                    os.remove(i)
                else:
                    shutil.rmtree(i, ignore_errors=True)

    for i in os.listdir(update_path):
        if i == "delete.json":
            continue

        source = os.path.join(update_path, i)

        if source.endswith(".exe"):
            if not os.path.exists("update"):
                os.mkdir("update")
            shutil.copy2(source, os.path.join("update", i))
            continue

        if os.path.isfile(source):
            shutil.copy2(source, i)
        else:
            shutil.copytree(source, os.path.join(".", i), dirs_exist_ok=True)
