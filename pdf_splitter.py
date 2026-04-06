from PyPDF2 import PdfReader, PdfWriter


def split_pdf(input_path, start_page, end_page, output_path):
    reader = PdfReader(input_path)
    writer = PdfWriter()

    for page_num in range(start_page - 1, end_page):
        writer.add_page(reader.pages[page_num])

    with open(output_path, "wb") as output_file:
        writer.write(output_file)