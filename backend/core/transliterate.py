"""Транслитерация ФИО → username (латиница + цифры + underscore)."""
import re

_TABLE = str.maketrans({
    'а': 'a',  'б': 'b',  'в': 'v',  'г': 'g',  'д': 'd',
    'е': 'e',  'ё': 'yo', 'ж': 'zh', 'з': 'z',  'и': 'i',
    'й': 'y',  'к': 'k',  'л': 'l',  'м': 'm',  'н': 'n',
    'о': 'o',  'п': 'p',  'р': 'r',  'с': 's',  'т': 't',
    'у': 'u',  'ф': 'f',  'х': 'kh', 'ц': 'ts', 'ч': 'ch',
    'ш': 'sh', 'щ': 'sch','ъ': '',   'ы': 'y',  'ь': '',
    'э': 'e',  'ю': 'yu', 'я': 'ya',
    'А': 'a',  'Б': 'b',  'В': 'v',  'Г': 'g',  'Д': 'd',
    'Е': 'e',  'Ё': 'yo', 'Ж': 'zh', 'З': 'z',  'И': 'i',
    'Й': 'y',  'К': 'k',  'Л': 'l',  'М': 'm',  'Н': 'n',
    'О': 'o',  'П': 'p',  'Р': 'r',  'С': 's',  'Т': 't',
    'У': 'u',  'Ф': 'f',  'Х': 'kh', 'Ц': 'ts', 'Ч': 'ch',
    'Ш': 'sh', 'Щ': 'sch','Ъ': '',   'Ы': 'y',  'Ь': '',
    'Э': 'e',  'Ю': 'yu', 'Я': 'ya',
})


def fio_to_username(full_name: str) -> str:
    """«Иванов Иван Иванович» → «ivanov_ivan_ivanovich»."""
    parts = full_name.strip().split()
    result = '_'.join(p.translate(_TABLE) for p in parts)
    # убираем всё кроме латиницы, цифр и underscore
    result = re.sub(r'[^a-z0-9_]', '', result.lower())
    result = re.sub(r'_+', '_', result).strip('_')
    return result or 'user'


async def unique_username(full_name: str, db) -> str:
    """Генерирует уникальный логин, добавляя суффикс _2, _3 при коллизии."""
    base = fio_to_username(full_name)
    candidate = base
    n = 2
    while await db.users.find_one({"username": candidate}):
        candidate = f"{base}_{n}"
        n += 1
    return candidate
