import re
import fitz

# ============================================================
# ПАТТЕРНЫ
# ============================================================
CODE_RE = re.compile(r'^\d{3}-\d{3}-\d{4}')
UNIT_RE = re.compile(r'^(шт\.?|м\.?|к-т|компл\.?)$', re.IGNORECASE)
QTY_RE = re.compile(r'^\d+([.,]\d+)?$')
RECT_RE = re.compile(r'(\d{2,4})\s*[xхХ×]\s*(\d{2,4})')
ROUND_RE = re.compile(r'[ØøОо][\s]?(\d{2,4})')
THICK_RE = re.compile(r'[бbsδ]=?\s*(\d+[.,]?\d*)\s*мм', re.IGNORECASE)

GARBAGE_WORDS = [
    "инв.", "подл.", "подпись и дата", "взам.",
    "тип, марка", "завод-", "единица", "коли-",
    "масса", "оборудования,", "позиция", "наименование",
    "документа,", "материала", "изготовитель", "измере-",
    "чество", "единицы", "примечание", "ния", "кг.",
    "стадия", "разработал", "проверил", "н. контроль",
    "изм.", "кол.уч.", "формат", "строительство",
    "казахстан", "гостиничный", "республика", "костанай",
    "заболотная", "кулешов", "baimura", "тоо ", "ооо ",
]

DUCT_KEYWORDS = ["воздуховод", "отвод", "переход", "труба"]

# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def is_code(line):
    return bool(CODE_RE.match(line))

def is_unit(line):
    return bool(UNIT_RE.match(line.strip()))

def is_qty(line):
    return bool(QTY_RE.match(line.strip()))

def is_garbage(line):
    if re.match(r'^\d$', line.strip()):
        return True
    if re.match(r'^[.\s]+$', line.strip()):
        return True
    line_l = line.lower()
    return any(g in line_l for g in GARBAGE_WORDS)

def is_duct(line):
    line_l = line.lower()
    return any(kw in line_l for kw in DUCT_KEYWORDS)

def extract_rect_size(text):
    m = RECT_RE.search(text)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None

def extract_round_size(text):
    m = ROUND_RE.search(text)
    if m:
        return int(m.group(1))
    return None

def extract_thickness(text):
    m = THICK_RE.search(text)
    if m:
        return float(m.group(1).replace(",", "."))
    return None

def get_thickness_by_size(w=None, h=None, d=None):
    """Определяет толщину по размеру если не указана явно"""
    if d is not None:
        return 0.5 if d < 400 else 0.7
    if w is not None and h is not None:
        return 0.5 if w < 400 and h < 400 else 0.7
    return 0.5

# ============================================================
# ФОРМУЛЫ РАСЧЁТА ПЛОЩАДИ
# ============================================================

def calc_area(item):
    name = item["name"].lower()
    qty = item["qty"]
    w, h = item["w"], item["h"]
    d = item["d"]

    if qty is None:
        return None

    # Отвод или переход — коэффициент 0.6
    if "отвод" in name or "переход" in name:
        if d:
            perimeter = d / 1000 * 3.14
        elif w and h:
            # для перехода берём большую сторону
            if "переход" in name:
                w2, h2 = item.get("w2"), item.get("h2")
                d2 = item.get("d2")
                if w2 and h2:
                    w = max(w, w2)
                    h = max(h, h2)
                elif d2:
                    d = max(d or 0, d2)
            perimeter = (w + h) / 1000 * 2
        else:
            return None
        area = (perimeter + perimeter * 0.10) * 0.6
        return round(area * qty, 2)

    # Воздуховод или труба — на длину
    if "воздуховод" in name or "труба" in name:
        if d:
            perimeter = d / 1000 * 3.14
        elif w and h:
            perimeter = (w + h) / 1000 * 2
        else:
            return None
        area = (perimeter + perimeter * 0.10) * qty
        return round(area, 2)

    return None

# ============================================================
# ПАРСЕР PDF
# ============================================================

def parse_spec_pdf(path):
    doc = fitz.open(path)
    items = []

    for page_num, page in enumerate(doc, start=1):
        lines = page.get_text("text").splitlines()
        lines = [l.strip() for l in lines if l.strip()]

        i = 0
        while i < len(lines):
            line = lines[i]

            if is_garbage(line) or is_code(line) or is_unit(line) or is_qty(line):
                i += 1
                continue

            if not is_duct(line):
                i += 1
                continue

            # Нашли воздуховод/отвод/переход — собираем блок
            name_parts = [line]
            i += 1

            while i < len(lines):
                next_line = lines[i]
                if is_code(next_line) or is_unit(next_line) or is_qty(next_line):
                    break
                if is_duct(next_line) or is_garbage(next_line):
                    break
                name_parts.append(next_line)
                i += 1

            name = " ".join(name_parts)

            # код, единица, количество
            code = unit = qty = None
            if i < len(lines) and is_code(lines[i]):
                code = lines[i]; i += 1
            if i < len(lines) and is_unit(lines[i]):
                unit = lines[i]; i += 1
            if i < len(lines) and is_qty(lines[i]):
                qty = float(lines[i].replace(",", ".")); i += 1

            # размеры
            w, h = extract_rect_size(name)
            d = extract_round_size(name)
            thickness = extract_thickness(name)

            # для перехода ищем второй размер
            w2 = h2 = d2 = None
            if "переход" in name.lower():
                sizes = RECT_RE.findall(name)
                if len(sizes) >= 2:
                    w2, h2 = int(sizes[1][0]), int(sizes[1][1])
                rounds = ROUND_RE.findall(name)
                if len(rounds) >= 2:
                    d2 = int(rounds[1])

            if thickness is None:
                thickness = get_thickness_by_size(w, h, d)

            item = {
                "name": name,
                "code": code,
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

# ============================================================
# ИТОГ ПО ТОЛЩИНАМ
# ============================================================

def summarize(items):
    summary = {}
    for item in items:
        if item["area_m2"] is None:
            continue
        t = item["thickness"]
        summary[t] = round(summary.get(t, 0) + item["area_m2"], 2)
    return dict(sorted(summary.items()))

# ============================================================
# ЗАПУСК
# ============================================================

if __name__ == "__main__":
    path = input("Путь к PDF: ").strip().strip('"')
    items = parse_spec_pdf(path)

    print(f"\nНайдено позиций: {len(items)}\n")
    for item in items:
        size = f"{item['w']}x{item['h']}" if item['w'] else f"Ø{item['d']}" if item['d'] else "?"
        print(f"  {item['name'][:60]}")
        print(f"    размер={size} | толщ={item['thickness']}мм | "
              f"{item['qty']} {item['unit']} | площадь={item['area_m2']} м2")

    print("\n" + "="*40)
    print("ИТОГ ПО ТОЛЩИНАМ МЕТАЛЛА:")
    print("="*40)
    for thickness, total in summarize(items).items():
        print(f"  {thickness}мм  →  {total} м2")