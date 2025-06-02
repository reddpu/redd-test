import fitz 
from googletrans import Translator
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import simpleSplit
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Pool
import functools

# --- Font Setup ---
try:
    from reportlab.pdfbase import pdfdoc
    pdfdoc.Font2Type1Font.defaultFontMapping['SimSun'] = 'SimSun'
    pdfmetrics.registerFont(TTFont('SimSun', 'SimSun.ttf'))  # Ensure SimSun.ttf exists locally
except Exception as e:
    print("SimSun font not found. Falling back to system fonts.")

# --- Functions ---

def translate_text(text, target_lang='en'):
    try:
        translator = Translator()
        result = translator.translate(text, dest=target_lang)
        return result.text if result else text
    except Exception as e:
        print(f"Translation error: {e}")
        return text


def extract_page(page_num, input_pdf):
    """Extracts all text blocks with metadata from one page"""
    doc = fitz.open(input_pdf)
    page = doc.load_page(page_num)
    return page.get_text("dict")["blocks"]


def process_page(args):
    """Translate a single page in parallel"""
    page_num, blocks, translator = args
    translated_blocks = []

    for block in blocks:
        if "lines" not in block:
            continue
        translated_block = {
            "lines": []
        }

        for line in block["lines"]:
            translated_line = {
                "spans": []
            }

            for span in line["spans"]:
                x0, y0, x1, y1 = span["bbox"]
                text = span["text"]
                font_size = span["size"]

                translated_text = translate_text(text, 'en')

                translated_span = {
                    "bbox": (x0, y0, x1, y1),
                    "text": translated_text,
                    "font_size": font_size
                }
                translated_line["spans"].append(translated_span)

            translated_block["lines"].append(translated_line)

        translated_blocks.append(translated_block)

    return page_num, translated_blocks


def translate_pdf_parallel(input_pdf, output_pdf, update_status):
    doc = fitz.open(input_pdf)
    total_pages = len(doc)
    update_status(f"Step 1 of 3: Extracting text from all pages...")

    # Step 1: Extract All Pages in Parallel
    with Pool() as pool:
        results = pool.map(functools.partial(extract_page, input_pdf=input_pdf), range(total_pages))
        all_blocks = results

    update_status(f"Step 2 of 3: Translating text in parallel...")
    translator = Translator()

    # Step 2: Translate Text Blocks in Parallel
    translated_data = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []

        for page_num, blocks in enumerate(all_blocks):
            futures.append(executor.submit(process_page, (page_num, blocks, translator)))

        for future in futures:
            translated_data.append(future.result())

    # Step 3: Rebuild PDF Sequentially
    update_status(f"Step 3 of 3: Rebuilding final PDF ({len(translated_data)} pages)...")

    first_page = doc.load_page(0)
    page_width = first_page.rect.width
    page_height = first_page.rect.height
    c = canvas.Canvas(output_pdf, pagesize=(page_width, page_height))

    for page_num, translated_blocks in sorted(translated_data, key=lambda x: x[0]):
        c.setFont("Helvetica", 10)

        for block in translated_blocks:
            for line in block["lines"]:
                for span in line["spans"]:
                    x0, y0, x1, y1 = span["bbox"]
                    translated_text = span["text"]
                    font_size = span["font_size"]

                    font_name = "SimSun" if any("\u4e00" <= c <= "\u9fff" for c in translated_text) else "Helvetica"
                    try:
                        c.setFont(font_name, font_size)
                    except:
                        c.setFont("Helvetica", font_size)

                    c.drawString(x0, page_height - y1, translated_text)

        c.showPage()

    c.save()
    update_status(f"✅ PDF generated successfully: {output_pdf}")
    messagebox.showinfo("Success", f"Translated PDF saved as:\n{output_pdf}")


# --- Tkinter GUI ---

def select_and_translate():
    input_pdf = filedialog.askopenfilename(title="Select PDF File", filetypes=[("PDF Files", "*.pdf")])
    if not input_pdf:
        return

    output_pdf = "FR_translated_fast.pdf"

    # Run in background thread
    threading.Thread(target=translate_pdf_parallel, args=(input_pdf, output_pdf, update_status), daemon=True).start()


def update_status(message):
    status_bar.config(text=message)
    root.update_idletasks()


# --- GUI Setup ---
root = tk.Tk()
root.title("PDF Translator")
root.geometry("800x600")

title_label = tk.Label(root, text="PDF Translator (Chinese to English)", font=("Helvetica", 18))
title_label.pack(pady=20)

instruction_label = tk.Label(root, text="Click below to select a PDF and start translation.", font=("Helvetica", 14))
instruction_label.pack(pady=10)

upload_button = tk.Button(root, text="Upload & Translate PDF", width=25, height=2, command=select_and_translate)
upload_button.pack(pady=20)

status_bar = tk.Label(root, text="Ready", bd=1, relief=tk.SUNKEN, anchor=tk.W, font=("Helvetica", 10))
status_bar.pack(side=tk.BOTTOM, fill=tk.X)

# Start GUI loop
root.mainloop()