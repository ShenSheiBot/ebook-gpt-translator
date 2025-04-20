# eBook GPT Translator Guide

**[中文](./README_CN.md) | English**

This guide provides a step-by-step process for setting up the eBook Translator for converting ebooks of other languages into Chinese.

Supported formats: EPUB, DOCX, SRT (subtitles).
PDF format is not supported. It is recommended to convert PDF files to EPUB or DOCX format using Adobe Acrobat or similar tools before translation.

## [Recommended] Running as Github Action

Github actions can be used to automate the translation process if your book is short and can be translated within the 6-hour time limit.

1. Fork this repository.
2. Go to the `Settings` tab of your forked repository.
3. Go to the `Secrets and variables - Actions` tab.
4. (Optional, if you have a US credit card) If you don't have a S3 bucket, you can get free 10GB storage at [Cloudflare](https://developers.cloudflare.com/r2/). Go to R2 - Manage R2 API Tokens - Create API Token. Allow read and write. Take note of the access key, secret key, and endpoint (full URL, including https://). Create a S3 bucket named `book`.
5. (Optional, recommended) If you don't have a US credit card, you can also get free 10GB storage at [Backblaze](https://www.backblaze.com/). After registering an account, first enable B2 cloud storage in [My Settings](https://secure.backblaze.com/account_settings.htm), then generate a new master application key in [Application Keys](https://secure.backblaze.com/app_keys.htm) (you can record the keyID and applicationKey, but they won't be used). Create a S3 bucket named `translator`, and note down the Endpoint. Add "https://" in front of it to get the S3_ENDPOINT you'll need later. Then add a new application key, select allow access to all buckets, and record the keyID (your future access key) and applicationKey (your future secret key).
6. Add the following Repository secrets:
   - `GOOGLE_API_KEY`: Your [Gemini API keys](https://aistudio.google.com/app/u/0/apikey?pli=1).
   - `POE_API_KEY`: (Optional) Your [Poe API keys](https://poe.com/api_key).
   - `TRANSLATION_CONFIG`: (Optional) For more advanced configuration, you can provide a JSON config similar to the example `translation.yaml.example` file to use models other than `gemini-1.5-flash`*.
   - `S3_ACCESS_KEY`: Your S3 access key. 
   - `S3_SECRET_KEY`: Your S3 secret key.
   - `S3_ENDPOINT`: Your S3 bucket endpoint.
7. Go to the `Variables` tab and add the following Repository variables:
   - `CN_TITLE`: The Chinese name of the book.
   - `JP_TITLE`: The Foreign name of the book.
   - `TRANSLATION_TITLE_RETRY_COUNT`: The number of times to retry the batch translation of multiple lines. Recommended 5 times (at least 3 times). 
   - `DRYRUN`: If set to `True`, the translation process will be simulated, with all content translated to "To be translated". This is also useful if you've translated half of the book and don't want to translate the rest.
   - `PROMPT`: (Optional) Defaults to "将下面的外文文本翻译为中文："
   - `BILLING`: (Optional) If billing is enabled (set to True), translation will not wait exponentially for a certain time when translation fails.
8. Create a local folder with the name matching your `CN_TITLE` variable, and place the book file in the folder. Rename the file to `input.docx`, `input.epub`, or `input.srt`. Upload the folder to your S3 bucket.
9. Go to the `Actions` tab and manually trigger the workflow.
10. The translated book will be available in both Chinese and bilingual formats in your S3 bucket.

* The `TRANSLATION_CONFIG` supports all google models (make sure your config entry name contains "Gemini"), all poe models (make sure your config entry name contains "Poe"), and all other models supported by [LiteLLM](https://docs.litellm.ai/docs/providers). Note that the `gemini-1.5-flash` **does not** need to be prefixed as `gemini/gemini-1.5-flash` as in LiteLLM, unless you don't include "Gemini" in the name.


## Running Locally

### Prerequisites
- poetry: Install using `pip install poetry`.
- Python 3

### Repository Clone and Dependency Installation

Clone the repository and install the necessary dependencies:

```bash
# It is recommended to create a new virtual environment before installing the dependencies.
git clone https://github.com/ShenSheiBot/ebook-gpt-translator.git
cd ebook-gpt-translator
poetry env use python3.11
poetry install --no-root
```

### Translation Setup

1. Place the book file in the `output/[Chinese Book Name]/` directory and rename it to `input.docx`, `input.epub` or `input.srt`

2. Rename the file `.env.example` to `.env` and update it with the following configurations:

```bash
CN_TITLE=[Chinese Book Name]
JP_TITLE=[Original Book Name]
TRANSLATION_TITLE_RETRY_COUNT=[Retry Count for Batch Translation of EPUB Titles or SRT Lines]
DRYRUN=[True/False, Simulate Translation]
PROMPT=[Optional, Default Prompt]
BILLING=[Optional, Enable Billing]
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

4. Ensure the book file is in the `output/[Chinese Book Name]/` directory and renamed accordingly.

5. Execute the following command to start the translation process:


```bash
poetry run python docxloader.py  # For DOCX files
# or
poetry run python epubloader.py  # For EPUB files
# or
poetry run python srtloader.py  # For SRT files
```

The translation process can be paused and resumed. If interrupted, simply rerun the command to continue. Upon completion, the translated book will be available in both Chinese and bilingual formats in the `output/[Chinese Book Name]/` directory.

## Support the Developer

Consider subscribing to the Zhihu literary critic [甚谁](https://www.zhihu.com/people/sakuraayane_justice) for his insightful content.
