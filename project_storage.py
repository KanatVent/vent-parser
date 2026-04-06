import json
import os
import shutil
from datetime import datetime


def make_project_folder(project_name: str) -> str:
    safe_name = project_name.strip().replace(" ", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"{safe_name}_{timestamp}"

    project_path = os.path.join("projects", folder_name)
    os.makedirs(project_path, exist_ok=True)
    return project_path


def save_source_pdf(source_file_path: str, project_path: str) -> str:
    target_path = os.path.join(project_path, "source.pdf")
    shutil.copy2(source_file_path, target_path)
    return target_path


def save_raw_text(raw_text: str, project_path: str) -> str:
    txt_path = os.path.join(project_path, "raw_text.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(raw_text)
    return txt_path


def save_parsed_json(parsed_data: list, project_path: str) -> str:
    json_path = os.path.join(project_path, "parsed.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(parsed_data, f, ensure_ascii=False, indent=2)
    return json_path