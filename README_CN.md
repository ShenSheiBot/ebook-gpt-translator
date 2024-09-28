# eBook GPT Translator 使用手册

本指南将逐步介绍如何设置eBook GPT Translator，将外语电子书转换成中文。

目前支持格式：EPUB、DOCX、SRT（字幕）。
PDF格式暂不支持，推荐由Adobe Acrobat或类似工具转换成EPUB或DOCX格式后翻译。

## [推荐] 以 Github Action 运行

如果您的书籍篇幅较短，可以在 6 小时时限内完成翻译，则可以使用 Github 操作来自动完成翻译过程。

1. Fork 本仓库.
2. 转到分叉仓库的 `Setting` 选项卡。
3. 转到 `Secrets and variables - Actions` 选项卡。
4. （可选）如果没有 S3 存储桶，可在 [Cloudflare](https://developers.cloudflare.com/r2/) 获取免费的 10GB 存储空间。转到 R2 - Manage R2 API Tokens - Create API Token。允许读写。记下access key、secret key和endpoint（完整的 URL，包括 https://）。
5. 添加下述Repository secrets:
   - `GOOGLE_API_KEY`: 你的 [Gemini API keys](https://aistudio.google.com/app/u/0/apikey?pli=1).
   - `POE_API_KEY`: (可选) 你的 [Poe API keys](https://poe.com/api_key).
   - `S3_ACCESS_KEY`: 你的 S3 access key. 
   - `S3_SECRET_KEY`: 你的 S3 secret key.
   - `S3_ENDPOINT`: 你的 S3 bucket endpoint.
6. 转到 `Variables` 选项卡并添加下述 Repository variables:
   - `CN_TITLE`: 该电子书中文译名
   - `JP_TITLE`: 该电子书外文原名
   - `TRANSLATION_TITLE_RETRY_COUNT`: 重试批量对齐翻译的次数，推荐5次（至少为3次）。 
   - `DRYRUN`: 如果设置为 `True`，则翻译过程将模拟进行，所有内容会被翻译为“待翻译”。如果您翻译了一半，不想翻译书籍的其余部分，这也是一个有用的选项。
   - `PROMPT`: (可选) 默认为"将下面的外文文本翻译为中文："
7. 创建一个名为 `CN_TITLE` 的本地文件夹，并将图书文件放入该文件夹。将文件重命名为`input.docx`，`input.epub`或`input.srt`。 
8. 创建一个 S3 存储桶 `book`。将文件夹上传到 Cloudflare S3 存储桶 `book`。 (**注意**: 保持文件夹结构，不要将文件直接上传到存储桶中)
9. 转到 `Action` 选项卡，手动触发工作流程。
10. 翻译后的书籍将以中文和双语两种格式出现在您的 S3 文件桶中。



## 本地运行

### 先决条件
- poetry: 运行命令 `pip install poetry`以安装。
- Python 3

### 仓库克隆与依赖安装

克隆本仓库并安装必要的依赖项：

```bash
# It is recommended to create a new virtual environment before installing the dependencies.
git clone https://github.com/ShenSheiBot/ebook-gpt-translator.git
cd ebook-gpt-translator
poetry env use python3.11
poetry install --no-root
```

### 翻译设置

1. 将电子书文件放置于 `output/[Chinese Book Name]/` 目录下，并将其重命名为 `input.docx`、`input.epub`或`input.srt`。

2. 将文件 `.env.example` 重命名为 `.env` 并更新下述配置：

```bash
CN_TITLE=[Chinese Book Name]
JP_TITLE=[English Book Name]
TRANSLATION_TITLE_RETRY_COUNT=[Retry Count for Batch Translation of EPUB Titles or SRT Lines]
```

3. 将文件 `translation.yaml.example` 重命名为 `translation.yaml` 并且填入你的 [Gemini API keys](https://aistudio.google.com/app/u/0/apikey?pli=1) 与 [Poe API keys](https://poe.com/api_key)。

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

1. 确保电子书文件已经位于 `output/[Chinese Book Name]/` 目录下，并且已经重命名。

2. 执行以下命令以启动翻译过程：


```bash
poetry run python docxloader.py  # For DOCX files
# or
poetry run python epubloader.py  # For EPUB files
# or
poetry run python srtloader.py  # For SRT files
```

翻译过程可以暂停和恢复。如果中断，只需重新运行命令即可继续。翻译完成后，译本将以中文和双语两种格式出现在 `output/[Chinese Book Name]/` 目录中。

## 支持开发者

![](ad.jpg)