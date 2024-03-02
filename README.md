
## Environment Setup

Requirements: poetry (`pip install poetry`), python 3.11

```bash
git clone https://github.com/ShenSheiBot/gemini-ebook-translator.git
cd gemini-ebook-translator
poetry install
```

## Translate a Chinese book

Move the book to the `output/[中文书名]/` directory, rename the book to `input.docx` or `input.epub`. Rename `.env.example` to `.env` and fill in the following values:

```bash
CN_TITLE=[中文书名]
JP_TITLE=[英文书名]
TRANSLATION_TITLE_RETRY_COUNT=[批量翻译epub标题时失败重试次数]
```

Rename `translation.yaml.example` to `translation.yaml` and fill in the [Gemini API keys](https://aistudio.google.com/app/u/0/apikey?pli=1) and [Poe API keys](https://poe.com/api_key).

```yaml
{
    "Gemini-Pro-api": {  # 可自定义名称，只要包含Gemini即可
        "name": "gemini-pro",  # 模型名称，不建议修改
        "type": "api",
        "retry_count": 3,  # 失败重试次数 （若翻译长度明显错误或API无法访问，详见`validate`)
        "key": ""
    },
    "Poe-api": {  # 可自定义名称，只要包含Poe即可
        "name": "Gemini-Pro",  # 模型名称，支持任意Poe模型
        "type": "api",
        "retry_count": 1,
        "key": ""
    }
}
```

Then copy the book to `output/中文书名/`, rename to `input.epub` or `input.docx`. Run the following command:

```bash
python docxloader.py  # or ...
python epubloader.py
```

The translation process is resumable. If the translation process is interrupted, run the command again. It will generate both a Chinese and an English version of the book in the `output/[中文书名]/` directory.

## Support Me

Please subscribe Zhihu literary critic [甚谁](https://www.zhihu.com/people/sakuraayane_justice)
