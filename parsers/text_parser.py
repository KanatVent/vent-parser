import pdfplumber
from .base_parser import BaseParser


class TextParser(BaseParser):

    def parse(self, file_path: str) -> str:
        full_text = []

        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text.append(text)

        return "\n".join(full_text)