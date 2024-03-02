# eBook GPT Translator Setup Guide

This guide provides a step-by-step process for setting up the eBook Translator for converting English ebooks into Chinese.

## Prerequisites
- poetry: Install using `pip install poetry`.
- Python 3

## Repository Clone and Dependency Installation

Clone the repository and install the necessary dependencies:

```bash
# It is recommended to create a new virtual environment before installing the dependencies.
git clone https://github.com/ShenSheiBot/ebook-gpt-translator.git
cd ebook-gpt-translator
poetry env use python3.11
poetry install --no-root
```

## English to Chinese Translation Setup

1. Place the book file in the `output/[Chinese Book Name]/` directory and rename it to `input.docx` or `input.epub`.

2. Rename the file `.env.example` to `.env` and update it with the following configurations:

```bash
CN_TITLE=[Chinese Book Name]
JP_TITLE=[English Book Name]
TRANSLATION_TITLE_RETRY_COUNT=[Retry Count for Batch Translation of EPUB Titles]
```

3. Rename `translation.yaml.example` to `translation.yaml` and populate it with your [Gemini API keys](https://aistudio.google.com/app/u/0/apikey?pli=1) and [Poe API keys](https://poe.com/api_key).

```yaml
{
    "Gemini-Pro-api": {
        "name": "gemini-pro",
        "type": "api",
        "retry_count": 3,
        "key": "[Your Gemini API Key]"
    },
    "Poe-api": {
        "name": "Gemini-Pro",
        "type": "api",
        "retry_count": 1,
        "key": "[Your Poe API Key]"
    }
}
```

4. Ensure the book file is in the `output/[Chinese Book Name]/` directory, renamed accordingly to `input.epub` or `input.docx`.

5. Execute the following command to start the translation process:


```bash
poetry run python docxloader.py  # For DOCX files
# or
poetry run python epubloader.py  # For EPUB files
```

The translation process can be paused and resumed. If interrupted, simply rerun the command to continue. Upon completion, the translated book will be available in both Chinese and bilingual (English + Chinese) formats in the `output/[Chinese Book Name]/` directory.

## Support the Developer

Consider subscribing to the Zhihu literary critic [甚谁](https://www.zhihu.com/people/sakuraayane_justice) for his insightful content.
