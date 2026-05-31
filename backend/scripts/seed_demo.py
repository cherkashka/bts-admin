"""Однократное наполнение БД демонстрационными данными.

Чистит всё кроме админа и его категорий, затем генерирует реалистичный
набор сотрудников, активов, задач, заметок и записей аудита за период
от двух месяцев назад до двух недель вперёд.

Запуск на сервере:
    cd /opt/bts-admin && .venv/bin/python -m backend.scripts.seed_demo
"""
import random
import re
import string
import sys
from datetime import datetime, timedelta, timezone

import bcrypt
from pymongo import MongoClient

DB_NAME = sys.argv[1] if len(sys.argv) > 1 else "it_admin_db"

NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
START = NOW - timedelta(days=61)      # два месяца назад
FUTURE = NOW + timedelta(days=14)     # две недели вперёд

DEMO_PASSWORD = "Demo1234"

# ─── транслитерация (копия backend/core/transliterate) ────────────────
_TABLE = str.maketrans({
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
})


def translit(full_name):
    parts = full_name.strip().lower().split()
    result = '_'.join(p.translate(_TABLE) for p in parts)
    result = re.sub(r'[^a-z0-9_]', '', result)
    result = re.sub(r'_+', '_', result).strip('_')
    return result or 'user'


def hash_pw(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def rnd_dt(start, end):
    """Случайный datetime в диапазоне [start, end]."""
    delta = (end - start).total_seconds()
    return start + timedelta(seconds=random.uniform(0, delta))


def at_hour(dt, lo=8, hi=18):
    return dt.replace(hour=random.randint(lo, hi), minute=random.choice([0, 15, 30, 45]),
                      second=0, microsecond=0)


# ─── исходные данные ──────────────────────────────────────────────────
FIRST_M = ["Александр", "Дмитрий", "Сергей", "Андрей", "Алексей", "Иван",
           "Максим", "Павел", "Николай", "Артём", "Владимир", "Егор"]
FIRST_F = ["Елена", "Ольга", "Анна", "Татьяна", "Наталья", "Ирина",
           "Мария", "Екатерина", "Светлана", "Юлия"]
LAST_M = ["Иванов", "Петров", "Сидоров", "Ковалёв", "Новиков", "Морозов",
          "Волков", "Лебедев", "Козлов", "Соколов", "Кузнецов", "Бондаренко",
          "Шевченко", "Романюк", "Гаврилов"]
LAST_F = ["Иванова", "Петрова", "Ковалёва", "Новикова", "Морозова",
          "Волкова", "Лебедева", "Козлова", "Соколова", "Кузнецова"]
DEPARTMENTS = ["Бухгалтерия", "Отдел продаж", "ИТ-отдел", "Склад", "Логистика",
               "Отдел кадров", "Юридический отдел", "Производство"]

ASSET_TEMPLATES = {
    "laptop": ["Lenovo ThinkPad E15", "HP ProBook 450", "Dell Latitude 5520",
               "ASUS ExpertBook B1", "Acer TravelMate P2", "MacBook Air M2"],
    "desktop": ["HP EliteDesk 800", "Dell OptiPlex 7090", "Lenovo ThinkCentre M70",
                "ASUS ExpertCenter D5"],
    "monitor": ["Dell P2422H 24\"", "LG 24MK430H", "Samsung S24R350",
                "Philips 243V7", "AOC 24B2XH"],
    "printer": ["HP LaserJet Pro M404", "Canon i-SENSYS LBP223", "Kyocera ECOSYS P2040",
                "Brother HL-L2370", "Xerox B210"],
    "peripheral": ["Logitech MK270 (клав+мышь)", "Logitech C920 веб-камера",
                   "Jabra Evolve 20 гарнитура", "Defender USB-хаб",
                   "APC Back-UPS 650"],
    "mobile": ["Samsung Galaxy A54", "Xiaomi Redmi Note 12", "iPhone SE 2022"],
    "other": ["Cisco SG350 коммутатор", "MikroTik hAP ac2 роутер",
              "Zebra GK420d принтер этикеток", "Сканер ШК Honeywell 1450g"],
}
NETWORK_TYPES = {"other", "printer"}  # которым присваиваем MAC
LOCATIONS = ["Каб. 101", "Каб. 204", "Каб. 305", "Серверная", "Склад А",
             "Приёмная", "Каб. 112", "Переговорная", "Каб. 210"]

TASK_TITLES = [
    "Установка ОС и ПО на новый ноутбук", "Замена картриджа в принтере",
    "Настройка VPN-доступа для сотрудника", "Чистка системного блока от пыли",
    "Обновление антивируса на рабочих станциях", "Замена SSD-накопителя",
    "Настройка корпоративной почты", "Подключение нового МФУ к сети",
    "Восстановление данных с повреждённого диска", "Замена блока питания",
    "Настройка резервного копирования", "Диагностика неисправности монитора",
    "Перенос данных на новый компьютер", "Обновление прошивки роутера",
    "Установка лицензии Office", "Настройка прав доступа к папкам",
    "Ремонт клавиатуры ноутбука", "Профилактика сервера", "Замена ОЗУ на сервере",
    "Подключение IP-телефонии", "Настройка двухфакторной аутентификации",
    "Инвентаризация техники в отделе", "Замена термопасты в ноутбуке",
    "Настройка сетевого принтера", "Устранение сбоя сети в кабинете",
    "Обновление Windows до актуальной версии", "Создание учётной записи в домене",
    "Подготовка рабочего места для нового сотрудника", "Замена жёсткого диска",
    "Настройка удалённого рабочего стола",
]
TASK_DESCS = [
    "Поставить 32GB DDR4. Заменить два модуля по 8GB.",
    "Проверить совместимость комплектующих перед заказом.",
    "Согласовать время с пользователем, не мешать рабочему процессу.",
    "После выполнения проверить работоспособность и отчитаться.",
    "Заявка от руководителя отдела, приоритет повышенный.",
    "Требуется выезд в удалённый филиал.",
    "", "",
]

NOTE_TITLES = [
    "Плановое обслуживание сервера", "Закупка расходных материалов",
    "Совещание ИТ-отдела", "Истекает гарантия на партию ноутбуков",
    "Резервное копирование (еженедельно)", "Аудит лицензий ПО",
    "Подготовка отчёта по технике", "Обновление парка мониторов",
    "День рождения коллеги", "Инвентаризация склада",
    "Продление договора с провайдером", "Тестирование нового ПО",
]


def main():
    client = MongoClient("mongodb://127.0.0.1:27017")
    db = client[DB_NAME]

    admin = db.users.find_one({"role": "admin"})
    if not admin:
        raise SystemExit("Админ не найден — прерываю.")
    admin_id = admin["_id"]
    admin_name = admin["username"]
    actor = {"id": str(admin_id), "username": admin_name}

    # ─── очистка ──────────────────────────────────────────────────────
    db.users.delete_many({"_id": {"$ne": admin_id}})
    db.assets.delete_many({})
    db.tasks.delete_many({})
    db.notes.delete_many({})
    db.audit_log.delete_many({})

    categories = list(db.categories.find({}))
    cat_ids = [c["_id"] for c in categories]

    audit_rows = []

    def audit(action, entity_type, entity_id, label, ts):
        audit_rows.append({
            "timestamp": ts,
            "actor_id": str(admin_id),
            "actor_name": admin_name,
            "action": action,
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "entity_label": label,
            "before": None,
            "after": None,
        })

    # ─── пользователи (~15) ───────────────────────────────────────────
    full_perms = {r: {"create": True, "read": True, "update": True, "delete": True}
                  for r in ("assets", "tasks", "notes", "categories")}
    read_perms = {r: {"create": False, "read": True, "update": r == "tasks", "delete": False}
                  for r in ("assets", "tasks", "notes", "categories")}

    used_usernames = {admin_name}
    users = []
    for i in range(15):
        female = random.random() < 0.4
        first = random.choice(FIRST_F if female else FIRST_M)
        last = random.choice(LAST_F if female else LAST_M)
        full_name = f"{last} {first}"

        base = translit(full_name)
        username = base
        n = 2
        while username in used_usernames:
            username = f"{base}_{n}"
            n += 1
        used_usernames.add(username)

        created = rnd_dt(START, NOW - timedelta(days=2))
        # 2 «приглашённых, не активированных», остальные работают
        pending = i >= 13
        users.append({
            "username": username,
            "hashed_password": hash_pw(DEMO_PASSWORD),
            "full_name": full_name,
            "email": f"{username}@bts-company.by",
            "phone": f"+375 (29) {random.randint(100,999)}-{random.randint(10,99)}-{random.randint(10,99)}",
            "role": "user",
            "is_active": True,
            "is_activated": not pending,
            "password_change_required": pending,
            "permissions": read_perms if i % 3 else full_perms,
            "created_at": created,
        })

    res = db.users.insert_many(users)
    for uid, u in zip(res.inserted_ids, users):
        u["_id"] = uid
        audit("create", "user", uid, u["full_name"], u["created_at"])

    active_users = [u for u in users if u["is_activated"]]

    # ─── активы (~50) ─────────────────────────────────────────────────
    assets = []
    inv_seq = 1
    serial_seen = set()
    for _ in range(50):
        atype = random.choice(list(ASSET_TEMPLATES.keys()))
        name = random.choice(ASSET_TEMPLATES[atype])
        inv = f"INV-2026-{inv_seq:04d}"
        inv_seq += 1

        serial = f"SN{random.randint(100000, 999999)}{random.choice(string.ascii_uppercase)}{random.randint(10,99)}"
        while serial in serial_seen:
            serial = f"SN{random.randint(100000, 999999)}{random.choice(string.ascii_uppercase)}{random.randint(10,99)}"
        serial_seen.add(serial)

        commission = rnd_dt(NOW - timedelta(days=720), NOW - timedelta(days=5))
        warranty_months = random.choice([12, 24, 36])
        warranty_end = commission + timedelta(days=warranty_months * 30)
        # часть активов — с истекающей в ближайшие 2 недели гарантией (для календаря)
        if random.random() < 0.18:
            warranty_end = rnd_dt(NOW, FUTURE)

        status = random.choices(
            ["in_use", "installed", "repair", "retired"],
            weights=[58, 18, 14, 10],
        )[0]

        mol = random.choice(active_users) if status != "retired" and random.random() < 0.8 else None
        doc = {
            "name": name,
            "inventory_number": inv,
            "asset_type": atype,
            "serial_number": serial,
            "mol_user_id": str(mol["_id"]) if mol else None,
            "mol_name": mol["full_name"] if mol else None,
            "commission_date": commission,
            "warranty_months": warranty_months,
            "warranty_end_date": warranty_end,
            "status": status,
            "comments": random.choice(["", "", "Требует обновления ПО", "Замена по гарантии",
                                       "Закреплён за отделом"]) or None,
            "location": random.choice(LOCATIONS),
            "created_at": commission,
            "updated_at": commission,
        }
        if atype in NETWORK_TYPES:
            doc["mac_address"] = ":".join(f"{random.randint(0,255):02X}" for _ in range(6))
        assets.append(doc)

    res = db.assets.insert_many(assets)
    for aid, a in zip(res.inserted_ids, assets):
        a["_id"] = aid
        ts = rnd_dt(START, NOW)
        audit("create", "asset", aid, a["name"], ts)

    # ─── задачи (~80) ─────────────────────────────────────────────────
    tasks = []
    for _ in range(80):
        title = random.choice(TASK_TITLES)
        start = rnd_dt(START, FUTURE)
        # большинство создано за последние 30 дней — для графика активности
        created = rnd_dt(NOW - timedelta(days=30), NOW) if random.random() < 0.7 \
            else rnd_dt(START, NOW)
        due = start + timedelta(days=random.randint(1, 10))
        assignee = random.choice(active_users) if random.random() < 0.85 else None

        if start > NOW:
            status = "pending"
        elif due < NOW:
            status = random.choices(["completed", "cancelled", "in_progress"],
                                    weights=[72, 10, 18])[0]
        else:
            status = random.choices(["in_progress", "pending", "completed"],
                                    weights=[55, 25, 20])[0]

        updated = created
        if status == "completed":
            updated = rnd_dt(max(created, start), min(due + timedelta(days=2), NOW)) \
                if min(due + timedelta(days=2), NOW) > max(created, start) else NOW

        related_asset = random.choice(assets) if random.random() < 0.45 else None

        doc = {
            "title": title,
            "description": random.choice(TASK_DESCS) or None,
            "start_date": at_hour(start),
            "due_date": at_hour(due),
            "priority": random.choices(["low", "medium", "high", "critical"],
                                       weights=[20, 45, 25, 10])[0],
            "status": status,
            "task_type": "admin",
            "created_by": str(admin_id),
            "updated_by": str(admin_id),
            "created_at": created,
            "updated_at": updated,
        }
        if assignee:
            doc["assigned_to"] = str(assignee["_id"])
            doc["assigned_to_name"] = assignee["full_name"]
        if related_asset:
            doc["related_asset_id"] = str(related_asset["_id"])
        tasks.append(doc)

    res = db.tasks.insert_many(tasks)
    for tid, t in zip(res.inserted_ids, tasks):
        audit("create", "task", tid, t["title"], t["created_at"])
        if t["status"] == "completed":
            audit("update", "task", tid, t["title"], t["updated_at"])

    # ─── заметки (~18) ────────────────────────────────────────────────
    notes = []
    for _ in range(18):
        title = random.choice(NOTE_TITLES)
        ev_start = at_hour(rnd_dt(START, FUTURE), 9, 17)
        period = random.random() < 0.3
        ev_end = ev_start + timedelta(days=random.randint(1, 3)) if period else ev_start
        created = min(ev_start, NOW) - timedelta(days=random.randint(0, 5))
        notes.append({
            "title": title,
            "content": random.choice(["Не забыть согласовать с руководителем.",
                                      "Проверить наличие на складе.",
                                      "Уведомить заинтересованных сотрудников.", ""]) or None,
            "event_start": ev_start,
            "event_end": ev_end,
            "category_id": random.choice(cat_ids) if cat_ids and random.random() < 0.8 else None,
            "related_asset_id": None,
            "related_user_id": None,
            "created_by": admin_id,
            "created_at": created if created.tzinfo else created.replace(tzinfo=timezone.utc),
            "updated_at": created if created.tzinfo else created.replace(tzinfo=timezone.utc),
        })

    res = db.notes.insert_many(notes)
    for nid, n in zip(res.inserted_ids, notes):
        audit("create", "note", nid, n["title"], n["created_at"])

    # ─── запись аудита ────────────────────────────────────────────────
    audit_rows.sort(key=lambda r: r["timestamp"])
    db.audit_log.insert_many(audit_rows)

    print(f"users:  {db.users.count_documents({})} (вкл. админа)")
    print(f"assets: {db.assets.count_documents({})}")
    print(f"tasks:  {db.tasks.count_documents({})}")
    print(f"notes:  {db.notes.count_documents({})}")
    print(f"audit:  {db.audit_log.count_documents({})}")
    print(f"\nБаза: {DB_NAME}")
    print(f"Пароль всех сотрудников: {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
