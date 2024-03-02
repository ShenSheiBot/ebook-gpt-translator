
## Environment Setup

Requirements: poetry (`pip install poetry`), python 3.11

```bash
git clone https://github.com/ShenSheiBot/gemini-ebook-translator.git
cd gemini-ebook-translator
poetry install
```

## Translate a Chinese book

Move the book to the `output/[中文书名]/` directory, rename the book to `input.docx` or `input.epub`. Create a .env file under the root folder with the following content:

```bash
CN_TITLE=[中文书名]
TRANSLATION_TITLE_RETRY_COUNT=[批量翻译epub标题时失败重试次数]
```

```bash
