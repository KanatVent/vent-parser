import sys
import re
import fitz

sys.path.insert(0, "C:/vent_app/project_root")

RECT_RE = re.compile(r'(\d{2,4})\s*[xхХ×]\s*(\d{2,4})')
ROUND_RE = re.compile(r'[ØøДд]\s*(\d{2,4})')
THICK_RE = re.compile(r's=(\d+[.,]\d*)\s*мм', re.IGNORECASE)
UNIT_RE = re.compile(r'^(м|шт\.?|компл\.?|кг)$', re.IGNORECASE)
QTY_RE = re.compile(r'^\d+[.,]?\d*$')

DUCT_KEYWORDS = ["воздуховод", "отвод", "переход", "тройник", "труба"]

GARBAGE = [
    "гост", "формат", "примечание", "единица", "изме-",
    "оборудования", "изделия", "материала", "завод",
    "изготовитель", "тип, марка", "обозначение", "опорного",
    "масса", "единицы", "позиция", "наименование", "техническая",
    "изм.", "кол.уч", "подп.", "взам.", "инв.", "подпись",
    "согласовано", "гр. вк", "гр. эл", "гр. ас", "мип-",
    "с.1.494", "с.5.904", "теплоизоляция", "решетка", "клапан",
    "лючок", "зонт", "вентилятор", "глушитель", "утепленная",
    "наружные", "приточная", "вытяжная", "kern", "ursa",
    "санвент", "увк", "u=220", "м³", "система", "серия",
    "крепление", "l=300", "рения", "чество", "лист",
    "вентиляция", "санtventsservis", "сантвент",
]


def is_duct_header(line):
    line_l = line.lower()
    return any(kw in line_l for kw in DUCT_KEYWORDS)


def is_garbage(line):
    if re.match(r'^\d{1,2}$', line.strip()):
        return True
    if re.match(r'^[.\s]+$', line.strip()):
        return True
    if is_duct_header(line):
        return False
    line_l = line.lower()
    return any(g in line_l for g in GARBAGE)


def get_thickness_by_size(w=None, h=None, d=None):
    if d: return 0.5 if d < 400 else 0.7
    if w and h: return 0.5 if w < 400 and h < 400 else 0.7
    return 0.5


def calc_area(duct_type, w, h, d, qty, unit):
    if qty is None: return None

    if "отвод" in duct_type or "переход" in duct_type:
        if d:
            perimeter = d / 1000 * 3.14
        elif w and h:
            perimeter = (w + h) / 1000 * 2
        else:
            return None
        return round((perimeter * 1.10) * 0.6 * qty, 2)

    if "воздуховод" in duct_type or "труба" in duct_type:
        if unit and unit.lower() not in ["м", "m"]:
            return None
        if d:
            perimeter = d / 1000 * 3.14
        elif w and h:
            perimeter = (w + h) / 1000 * 2
        else:
            return None
        return round(perimeter * 1.10 * qty, 2)

    return None


def parse_pdf(path):
    doc = fitz.open(path)
    items = []
    current_type = "воздуховод"

    for page_num, page in enumerate(doc, start=1):
        blocks = page.get_text("blocks")
        blocks = sorted(blocks, key=lambda b: (round(b[1] / 5), b[0]))

        # разбиваем строки по колонкам на основе X координат
        # x < 1500  → название/размер
        # x >= 1700 → единица
        # x >= 1900 → количество
        rows = []
        for block in blocks:
            x0, y0, text = block[0], block[1], block[4]
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                rows.append({"text": line, "x": x0, "y": y0})

        # группируем по Y — строки с одинаковым Y это одна строка таблицы
        from collections import defaultdict
        y_groups = defaultdict(list)
        for row in rows:
            y_key = round(row["y"] / 5) * 5
            y_groups[y_key].append(row)

        for y_key in sorted(y_groups.keys()):
            group = y_groups[y_key]

            name_parts = []
            unit = None
            qty = None

            for item in group:
                t = item["text"]
                x = item["x"]

                if x >= 1900:
                    # колонка количества
                    if QTY_RE.match(t.strip()):
                        qty = float(t.replace(",", "."))
                elif x >= 1700:
                    # колонка единицы
                    if UNIT_RE.match(t.strip()):
                        unit = t.strip()
                elif x < 1500:
                    # колонка названия/размера
                    if not is_garbage(t):
                        name_parts.append(t)

            if not name_parts:
                continue

            full_text = " ".join(name_parts)

            # обновляем тип элемента
            if is_duct_header(full_text):
                for kw in DUCT_KEYWORDS:
                    if kw in full_text.lower():
                        current_type = kw
                        break

            # ищем размер
            rect = RECT_RE.search(full_text)
            rnd = ROUND_RE.search(full_text)

            if not rect and not rnd:
                continue

            w = h = d = None
            if rect:
                w, h = int(rect.group(1)), int(rect.group(2))
            elif rnd:
                d = int(rnd.group(1))

            thick_m = THICK_RE.search(full_text)
            thickness = (float(thick_m.group(1).replace(",", "."))
                         if thick_m else get_thickness_by_size(w, h, d))

            area = calc_area(current_type, w, h, d, qty, unit)

            items.append({
                "name": full_text,
                "duct_type": current_type,
                "w": w, "h": h, "d": d,
                "thickness": thickness,
                "unit": unit,
                "qty": qty,
                "area_m2": area,
                "page": page_num
            })

    doc.close()
    return items


def summarize(items):
    summary = {}
    for item in items:
        if item["area_m2"] is None:
            continue
        t = item["thickness"]
        summary[t] = round(summary.get(t, 0) + item["area_m2"], 2)
    return dict(sorted(summary.items()))


if __name__ == "__main__":
    path = input("Путь к PDF: ").strip().strip('"')
    items = parse_pdf(path)

    print(f"\n{'='*40}")
    print(f"Найдено позиций: {len(items)}")
    print(f"{'='*40}\n")

    for item in items:
        size = (f"{item['w']}x{item['h']}" if item['w']
                else f"Д{item['d']}" if item['d'] else "?")
        print(f"  [{item['duct_type'][:8]}] {size} | "
              f"толщ={item['thickness']}мм | "
              f"{item['qty']} {item['unit']} | "
              f"площадь={item['area_m2']} м2")

    print("\n" + "="*40)
    print("ИТОГ ПО ТОЛЩИНАМ МЕТАЛЛА:")
    print("="*40)
    for thickness, total in summarize(items).items():
        print(f"  {thickness}мм  →  {total} м2")