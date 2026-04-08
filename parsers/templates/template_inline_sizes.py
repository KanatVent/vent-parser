"""
Шаблон: Размеры inline — всё в одной строке
Признаки:
- нет кодов вида XXX-XXX-XXXX
- размер, толщина, единица, количество в одной строке
- пример: 150х100, s=0,5мм ГОСТ 14918-80 м 20,0
- названия "Воздуховод", "Отвод", "Переход" идут как заголовки
"""

import re
import fitz

TEMPLATE_ID = "inline_sizes"
TEMPLATE_NAME = "Размеры inline (150х100, s=0,5мм ... м ... 20,0)"

RECT_RE = re.compile(r'(\d{2,4})\s*[xхХ×]\s*(\d{2,4})')
ROUND_RE = re.compile(r'[ØøДд][\s]?(\d{2,4})')
THICK_RE = re.compile(r's=(\d+[.,]\d*)\s*мм', re.IGNORECASE)
QTY_RE = re.compile(r'\b(\d+[.,]?\d*)\s*$')
UNIT_RE = re.compile(r'\b(м|шт\.?|компл\.?|кг)\b', re.IGNORECASE)

DUCT_HEADERS = [
    "воздуховод", "отвод", "переход", "труба", "тройник"
]

GARBAGE_WORDS = [
    "формат", "примечание", "количество", "единица", "изме-",
    "рения", "код", "оборудования", "изделия", "материала",
    "завод", "изготовитель", "тип, марка", "обозначение",
    "опорного листа", "масса", "единицы", "позиция",
    "наименование", "техническая характеристика",
    "изм.", "кол.уч", "лист", "подп.", "дата", "взам.",
    "инв.", "подпись", "согласовано",
    "гр. вк", "гр. эл", "гр. ас", "абдулрахманов",
    "курманбаев", "жаманкулов", "мип-", "серия 5,904",
    "серия 1,494", "с.1.494", "с.5.904",
    "крепление воздуховодов", "теплоизоляция",
    "решетка", "клапан", "лючок", "зонт", "вентилятор",
    "глушитель", "утепленная", "наружные", "приточная",
    "вытяжная", "kern", "ursa", "санвент",
]


def is_garbage(line):
    if re.match(r'^\d$', line.strip()):
        return True
    if re.match(r'^[.\s]+$', line.strip()):
        return True
    line_l = line.lower()
    return any(g in line_l for g in GARBAGE_WORDS)


def is_duct_header(line):
    line_l = line.lower()
    return any(kw in line_l for kw in DUCT_HEADERS)


def is_size_line(line):
    """Строка содержит размер и единицу — это позиция"""
    has_size = bool(RECT_RE.search(line)) or bool(ROUND_RE.search(line))
    has_unit = bool(UNIT_RE.search(line))
    return has_size and has_unit


def extract_rect_size(text):
    matches = RECT_RE.findall(text)
    if matches:
        return int(matches[0][0]), int(matches[0][1])
    return None, None


def extract_round_size(text):
    m = ROUND_RE.search(text)
    return int(m.group(1)) if m else None


def extract_thickness(text):
    m = THICK_RE.search(text)
    if m:
        return float(m.group(1).replace(",", "."))
    return None


def get_thickness_by_size(w=None, h=None, d=None):
    if d:
        return 0.5 if d < 400 else 0.7
    if w and h:
        return 0.5 if w < 400 and h < 400 else 0.7
    return 0.5


def extract_unit(text):
    m = UNIT_RE.search(text)
    return m.group(1).lower() if m else None


def extract_qty(text):
    m = QTY_RE.search(text)
    if m:
        try:
            return float(m.group(1).replace(",", "."))
        except:
            return None
    return None


def calc_area(item):
    name = item["duct_type"]
    qty = item["qty"]
    unit = item["unit"]
    w, h, d = item["w"], item["h"], item["d"]

    if qty is None:
        return None

    if "отвод" in name or "переход" in name:
        if d:
            perimeter = d / 1000 * 3.14
        elif w and h:
            if "переход" in name:
                w2, h2 = item.get("w2"), item.get("h2")
                d2 = item.get("d2")
                if w2 and h2:
                    w, h = max(w, w2), max(h, h2)
                elif d2:
                    d = max(d or 0, d2)
            perimeter = (w + h) / 1000 * 2
        else:
            return None
        return round((perimeter * 1.10) * 0.6 * qty, 2)

    if "воздуховод" in name or "труба" in name:
        if unit not in ["м", "m"]:
            return None
        if d:
            perimeter = d / 1000 * 3.14
        elif w and h:
            perimeter = (w + h) / 1000 * 2
        else:
            return None
        return round(perimeter * 1.10 * qty, 2)

    return None


def can_handle(lines: list) -> bool:
    """
    Признак: есть строки с размером + единицей в одной строке
    и нет кодов вида XXX-XXX-XXXX
    """
    CODE_RE = re.compile(r'^\d{3}-\d{3}-\d{4}')
    has_codes = any(CODE_RE.match(l.strip()) for l in lines)
    if has_codes:
        return False

    size_unit_count = sum(1 for l in lines if is_size_line(l))
    return size_unit_count >= 3


def parse(path: str) -> list:
    doc = fitz.open(path)
    items = []
    current_duct_type = "воздуховод"

    for page_num, page in enumerate(doc, start=1):
        lines = page.get_text("text").splitlines()
        lines = [l.strip() for l in lines if l.strip()]

        for line in lines:
            if is_garbage(line):
                continue

            # определяем тип элемента (воздуховод/отвод/переход)
            if is_duct_header(line):
                line_l = line.lower()
                for kw in DUCT_HEADERS:
                    if kw in line_l:
                        current_duct_type = kw
                        break
                continue

            # строка с размером — это позиция
            if not is_size_line(line):
                continue

            w, h = extract_rect_size(line)
            d = extract_round_size(line)
            thickness = extract_thickness(line)

            if thickness is None:
                thickness = get_thickness_by_size(w, h, d)

            unit = extract_unit(line)
            qty = extract_qty(line)

            # для перехода — два размера
            w2 = h2 = d2 = None
            if "переход" in current_duct_type:
                matches = RECT_RE.findall(line)
                if len(matches) >= 2:
                    w2, h2 = int(matches[1][0]), int(matches[1][1])
                rounds = ROUND_RE.findall(line)
                if len(rounds) >= 2:
                    d2 = int(rounds[1])

            item = {
                "name": line,
                "duct_type": current_duct_type,
                "unit": unit,
                "qty": qty,
                "w": w, "h": h, "d": d,
                "w2": w2, "h2": h2, "d2": d2,
                "thickness": thickness,
                "page": page_num
            }
            item["area_m2"] = calc_area(item)
            items.append(item)

    doc.close()
    return items


def summarize(items: list) -> dict:
    summary = {}
    for item in items:
        if item["area_m2"] is None:
            continue
        t = item["thickness"]
        summary[t] = round(summary.get(t, 0) + item["area_m2"], 2)
    return dict(sorted(summary.items()))