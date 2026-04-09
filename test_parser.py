import sys
import re
import fitz
from collections import defaultdict

sys.path.insert(0, "C:/vent_app/project_root")

RECT_RE = re.compile(r'(\d{2,4})\s*[xхХ×]\s*(\d{2,4})')
ROUND_RE = re.compile(r'[ØøДд]\s*(\d{2,4})')
THICK_RE = re.compile(r's=(\d+[.,]\d*)\s*мм', re.IGNORECASE)
TRIPLE_RE = re.compile(r'(\d{2,4})\s*[xхХ×]\s*(\d{2,4})\s*[xхХ×]\s*(\d{2,4})')
TRANSITION_RE = re.compile(
    r'(\d{2,4})\s*[xхХ×]\s*(\d{2,4})\s*[-–]\s*(\d{2,4})\s*[xхХ×]\s*(\d{2,4})'
)
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
    "с.1.494", "с.5.904", "теплоизоляция",
    "решетка", "клапан", "зонт", "лючок",
    "вентилятор", "глушитель", "утепленная",
    "наружные", "приточная", "вытяжная", "kern", "ursa",
    "санвент", "увк", "u=220", "м³", "система", "серия",
    "крепление", "рения", "чество", "вентиляция",
]


def is_duct_header(line):
    line_l = line.lower()
    return any(kw in line_l for kw in DUCT_KEYWORDS)


def is_garbage(line):
    if re.match(r'^\d{1,2}$', line.strip()): return True
    if re.match(r'^[.\s]+$', line.strip()): return True
    if is_duct_header(line): return False
    line_l = line.lower()
    return any(g in line_l for g in GARBAGE)


def get_thickness_by_size(w=None, h=None, d=None):
    sizes = [s for s in [w, h, d] if s is not None]
    if not sizes: return 0.5
    return 0.5 if max(sizes) < 400 else 0.7


def calc_area(duct_type, w, h, d, qty, unit):
    if qty is None: return None

    if "воздуховод" in duct_type or "труба" in duct_type:
        if unit and unit.lower() not in ["м", "m"]: return None
        if d: perimeter = d / 1000 * 3.14
        elif w and h: perimeter = (w + h) / 1000 * 2
        else: return None
        return round(perimeter * 1.10 * qty, 2)

    if "отвод" in duct_type or "переход" in duct_type or "тройник" in duct_type:
        if d: perimeter = d / 1000 * 3.14
        elif w and h: perimeter = (w + h) / 1000 * 2
        else: return None
        return round((perimeter * 1.10) * 0.6 * qty, 2)

    return None


def extract_sizes(full_text, duct_type):
    """
    Извлекает размеры в зависимости от типа элемента.
    Возвращает (w, h, d) — уже с учётом логики выбора большего.
    """
    text_l = full_text.lower()

    # --- Тройник: три числа (350х350х350) → берём два наибольших ---
    if "тройник" in duct_type:
        m = TRIPLE_RE.search(full_text)
        if m:
            nums = sorted([int(m.group(1)), int(m.group(2)), int(m.group(3))],
                          reverse=True)
            return nums[0], nums[1], None
        # круглый тройник
        rnd = ROUND_RE.search(full_text)
        if rnd:
            d = int(rnd.group(1))
            return None, None, d

    # --- Переход: два размера через дефис (150х200-300х300) → берём больший ---
    if "переход" in duct_type:
        m = TRANSITION_RE.search(full_text)
        if m:
            w1, h1 = int(m.group(1)), int(m.group(2))
            w2, h2 = int(m.group(3)), int(m.group(4))
            # берём тот у которого периметр больше
            if (w1 + h1) >= (w2 + h2):
                return w1, h1, None
            else:
                return w2, h2, None
        # круглый переход: Д200/Д150 → берём больший
        rounds = ROUND_RE.findall(full_text)
        if len(rounds) >= 2:
            d = max(int(rounds[0]), int(rounds[1]))
            return None, None, d
        if len(rounds) == 1:
            return None, None, int(rounds[0])

    # --- Воздуховод и отвод: один размер ---
    rect = RECT_RE.search(full_text)
    if rect:
        return int(rect.group(1)), int(rect.group(2)), None

    rnd = ROUND_RE.search(full_text)
    if rnd:
        return None, None, int(rnd.group(1))

    return None, None, None


def parse_pdf(path):
    doc = fitz.open(path)
    items = []
    current_type = "воздуховод"

    for page_num, page in enumerate(doc, start=1):
        words = page.get_text("words")

        name_rows = []
        unit_rows = []
        qty_rows = []

        for wrd in words:
            x0, y0, text = wrd[0], wrd[1], wrd[4].strip()
            if not text: continue
            y_key = round(y0)

            if x0 >= 1900:
                if QTY_RE.match(text):
                    qty_rows.append({"text": text, "y": y_key})
            elif x0 >= 1700:
                if UNIT_RE.match(text):
                    unit_rows.append({"text": text, "y": y_key})
            else:
                if not is_garbage(text):
                    name_rows.append({"text": text, "y": y_key, "x": x0})

        y_groups = defaultdict(list)
        for r in name_rows:
            y_key = round(r["y"] / 8) * 8
            y_groups[y_key].append(r)

        for y_key in sorted(y_groups.keys()):
            group = sorted(y_groups[y_key], key=lambda r: r["x"])
            full_text = " ".join(r["text"] for r in group)

            if is_duct_header(full_text):
                for kw in DUCT_KEYWORDS:
                    if kw in full_text.lower():
                        current_type = kw
                        break
                continue  # ← заголовок не парсим как позицию

            w, h, d = extract_sizes(full_text, current_type)
            if w is None and h is None and d is None:
                continue

            thick_m = THICK_RE.search(full_text)
            thickness = (float(thick_m.group(1).replace(",", "."))
                         if thick_m else get_thickness_by_size(w, h, d))

            # ближайшая единица по Y (допуск ±30px)
            unit = None
            best = 30
            for ur in unit_rows:
                dy = abs(ur["y"] - y_key)
                if dy < best:
                    best = dy
                    unit = ur["text"]

            # ближайшее количество по Y (допуск ±30px)
            qty = None
            best = 30
            for qr in qty_rows:
                dy = abs(qr["y"] - y_key)
                if dy < best and QTY_RE.match(qr["text"]):
                    best = dy
                    qty = float(qr["text"].replace(",", "."))

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
        if item["area_m2"] is None: continue
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