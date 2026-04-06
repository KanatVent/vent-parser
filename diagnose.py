import re
import fitz


CODE_RE = re.compile(r'^\d{3}-\d{3}-\d{4}')
UNIT_RE = re.compile(r'^(шт\.?|м\.?|к-т|компл\.?)$', re.IGNORECASE)
QTY_RE = re.compile(r'^\d+([.,]\d+)?$')


def is_code(line):
    return bool(CODE_RE.match(line))

def is_unit(line):
    return bool(UNIT_RE.match(line.strip()))

def is_qty(line):
    return bool(QTY_RE.match(line.strip()))

def is_header_or_garbage(line):
    garbage = [
        "инв.", "подл.", "подпись", "дата", "взам.",
        "тип, марка", "код", "обозначение", "завод-",
        "единица", "коли-", "масса", "оборудования",
        "позиция", "наименование", "документа", "материала",
        "изготовитель", "измере-", "чество", "единицы",
        "примечание", "ния", "кг.", "лист", "стадия",
        "разработал", "проверил", "н. контроль", "гип",
        "изм.", "кол.уч.", "формат", "бм-", "строительство",
        "казахстан", "гостиничный", "ооо", "тоо", "гсл"
    ]
    line_l = line.lower()
    # цифра-столбец типа "1", "2" ... "9"
    if re.match(r'^\d$', line.strip()):
        return True
    return any(g in line_l for g in garbage)


def parse_spec_pdf(path):
    doc = fitz.open(path)
    items = []

    for page_num, page in enumerate(doc, start=1):
        lines = page.get_text("text").splitlines()
        lines = [l.strip() for l in lines if l.strip()]

        i = 0
        while i < len(lines):
            line = lines[i]

            # пропускаем мусор и заголовки
            if is_header_or_garbage(line):
                i += 1
                continue

            # пропускаем коды
            if is_code(line):
                i += 1
                continue

            # пропускаем единицы и количества отдельно
            if is_unit(line) or is_qty(line):
                i += 1
                continue

            # Нашли начало позиции — собираем блок
            name_parts = [line]
            i += 1

            # склеиваем продолжение названия
            while i < len(lines):
                next_line = lines[i]
                if is_code(next_line) or is_unit(next_line) or is_header_or_garbage(next_line):
                    break
                if is_qty(next_line):
                    break
                name_parts.append(next_line)
                i += 1

            name = " ".join(name_parts)

            # ищем код, единицу, количество после названия
            code = unit = qty = None

            if i < len(lines) and is_code(lines[i]):
                code = lines[i]
                i += 1

            if i < len(lines) and is_unit(lines[i]):
                unit = lines[i]
                i += 1

            if i < len(lines) and is_qty(lines[i]):
                qty = lines[i]
                i += 1

            if name and (unit or qty):
                items.append({
                    "name": name,
                    "code": code,
                    "unit": unit,
                    "qty": qty,
                    "page": page_num
                })

    doc.close()
    return items


if __name__ == "__main__":
    path = input("Путь к PDF: ").strip().strip('"')
    items = parse_spec_pdf(path)

    print(f"\nНайдено позиций: {len(items)}\n")
    for item in items:
        print(f"  {item['name']}")
        print(f"    код={item['code']} | ед={item['unit']} | кол={item['qty']}")
        print()