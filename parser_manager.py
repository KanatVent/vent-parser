import pdfplumber


class ParserManager:

    def parse_pdf(self, pdf_path: str) -> str:
        """
        Читает текст из PDF и возвращает одной строкой.
        """

        all_text = []

        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()

                if text:
                    all_text.append(text)

        return "\n".join(all_text)