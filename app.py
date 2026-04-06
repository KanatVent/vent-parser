import os
from parser_manager import ParserManager
from project_storage import (
    make_project_folder,
    save_source_pdf,
    save_raw_text,
    save_parsed_json
)
from services.position_parser import parse_positions
from pdf_splitter import split_pdf


def resolve_pdf_path(user_input: str) -> str | None:
    user_input = user_input.strip().strip('"')

    possible_paths = [
        user_input,
        os.path.abspath(user_input),
        os.path.abspath(os.path.join("..", "uploads", user_input)),
        os.path.abspath(os.path.join("..", user_input)),
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return path

    return None


def clean_lines(text: str) -> list:
    lines = text.splitlines()
    cleaned = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if len(line) < 2:
            continue
        cleaned.append(line)

    return cleaned


def to_simple_positions(lines: list) -> list:
    positions = []

    for line in lines:
        positions.append({
            "raw_line": line,
            "name": line,
            "unit": None,
            "qty": None,
            "thickness": None,
        })

    return positions


def main():
    pdf_input = input("Введи путь к PDF или имя файла: ").strip()
    project_name = input("Введи название проекта: ").strip()

    pdf_path = resolve_pdf_path(pdf_input)

    if not pdf_path:
        print("Файл не найден")
        print("Ты ввел:", pdf_input)
        print("Текущая папка программы:", os.getcwd())
        return

    # 🔥 НОВОЕ: спрашиваем про разделение PDF
    use_split = input("Разделить PDF? (y/n): ").strip().lower()

    if use_split == "y":
        try:
            page_range = input("Введите диапазон страниц (например 10-35): ").strip()
            start_page, end_page = map(int, page_range.split("-"))

            split_path = os.path.join("uploads", f"split_{os.path.basename(pdf_path)}")

            split_pdf(
                input_path=pdf_path,
                start_page=start_page,
                end_page=end_page,
                output_path=split_path
            )

            print(f"PDF разделен: {split_path}")

            # 👉 теперь работаем с новым файлом
            pdf_path = split_path

        except Exception as e:
            print("Ошибка при разделении PDF:", e)
            return

    # дальше всё как было
    project_path = make_project_folder(project_name)
    save_source_pdf(pdf_path, project_path)

    parser = ParserManager()
    raw_text = parser.parse_pdf(pdf_path)

    if not raw_text.strip():
        print("Текст из PDF не извлекся. Этот файл оставим на OCR позже.")
        return

    save_raw_text(raw_text, project_path)

    lines = clean_lines(raw_text)
    parsed_positions = to_simple_positions(lines)
    save_parsed_json(parsed_positions, project_path)

    print(f"Готово. Проект сохранен в: {project_path}")


if __name__ == "__main__":
    main()