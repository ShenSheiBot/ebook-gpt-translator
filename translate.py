from apichat import LiteLLMChatApp, GoogleChatApp, PoeAPIChatApp, AnthropicChatApp, OpenAIChatApp, APITranslationFailure
from loguru import logger
import re
import yaml
import sqlite3
import time
from utils import split_string_by_length, get_leading_numbers, remove_leading_numbers, load_config, postprocess

with open("translation.yaml", "r") as f:
    translation_config = yaml.load(f, Loader=yaml.FullLoader)

config = load_config()
logger.add(f"output/{config['CN_TITLE']}/info.log", colorize=True, level="DEBUG")


def generate_prompt(jp_text):
    if 'PROMPT' not in config or config['PROMPT'] == '':
        config['PROMPT'] = "将下面的外文文本翻译为中文："
    return config['PROMPT'] + "\n" + jp_text


def validate(jp_text, cn_text):
    if "不需要翻译" in cn_text or "无需翻译" in cn_text:
        return False
    if jp_text.startswith("http"):
        return False
    # Check ratio of Chinese characters to English characters (avg 1.6)
    if "将下面的外文文本翻译为中文：" in cn_text:
        logger.warning(f"Validation failed: prompt detected in translation: {cn_text}")
        return False
    if len(cn_text) == 0:
        return True
    ratio = len(jp_text.strip()) / len(cn_text.strip())
    if ratio < 0.5 or ratio > 10:
        logger.warning(f"Validation failed: ratio of Chinese characters to English words: {ratio}")
        return False
    else:
        return True
    
    
def align_translate(text_list, buffer, dryrun=False):
    # Translate a aligned block of text
    # Concatenate the text list
    output = ''
    special_line = {}
    lines = set()
    i = 0
    for text in text_list:
        text_updated = text.replace('\n', '')
        if text_updated in lines:
            continue  # Skip duplicate titles
        else:
            if text_updated != text:
                special_line[text_updated] = text
            lines.add(text_updated)
            output += str(i) + " " + text_updated + "\n"
            i += 1
    blocks = split_string_by_length(output, 600)
        
    # Traverse the aggregated chapter titles
    for text in blocks:
        block_list = text.strip().split('\n')
        
        start_idx = get_leading_numbers(block_list[0])
        end_idx = get_leading_numbers(block_list[-1])
        
        if not all([remove_leading_numbers(line) in buffer for line in block_list]):
            cn_block_list = []
            retry_count = int(config['TRANSLATION_TITLE_RETRY_COUNT']) + 1
            
            while len(cn_block_list) != len(block_list) and retry_count > 0:
                ### Start translation
                if dryrun:
                    cn_text = text
                elif text in buffer:
                    cn_text = buffer[text]
                else:
                    cn_text = translate(text, mode="title_translation", dryrun=dryrun)
                ### Translation finished
                cn_text = postprocess(cn_text)
                
                ### Match translated line to the corresponding indices
                cn_block_list = cn_text.strip().split('\n')
                cn_block_list = [line for line in cn_block_list if line.strip()]  # Remove empty lines
                
                if len(cn_block_list) == len(block_list):
                    # If the number of lines matches, assign leading numbers from original block_list
                    cn_block_list = [
                        f"{get_leading_numbers(block_list[i])} {cn_block_list[i].lstrip('0123456789. ')}"
                        for i in range(len(block_list))
                    ]
                    break
                
                cn_block_list = [line for line in cn_block_list if get_leading_numbers(line) is not None]
                if len(cn_block_list) == 0:
                    continue
                if get_leading_numbers(cn_block_list[0]) == start_idx and \
                get_leading_numbers(cn_block_list[-1]) == end_idx:
                    if len(cn_block_list) != len(block_list):
                        # Insert missing lines
                        cn_map = {}
                        map = {}
                        for line in block_list:
                            i = get_leading_numbers(line)
                            map[i] = line
                        for line in cn_block_list:
                            i = get_leading_numbers(line)
                            cn_map[i] = line
                        for i in range(start_idx, end_idx + 1):
                            if i not in cn_map:
                                if i + 1 in cn_map:
                                    cn_map[i] = cn_map[i + 1]
                                elif i - 1 in cn_map:
                                    cn_map[i] = cn_map[i - 1]
                                else:
                                    cn_map[i] = map[i]
                        block_list = [map[i] for i in range(start_idx, end_idx + 1)]
                        cn_block_list = [cn_map[i] for i in range(start_idx, end_idx + 1)]
                    break
                else:
                    retry_count -= 1

            flag = True
            if len(cn_block_list) != len(block_list):
                logger.critical(f"Failed to translate {text} after {config['TRANSLATION_TITLE_RETRY_COUNT']} retries.")
                logger.info(f"Falling back to no translation")
                cn_block_list = block_list
                flag = False
            else:
                buffer[text] = cn_text
                
            for cn_line, line in zip(cn_block_list, block_list):
                line = remove_leading_numbers(line)
                if line in special_line:
                    line = special_line[line]
                if flag:
                    buffer[line] = remove_leading_numbers(cn_line)


def translate(jp_text, mode="translation", dryrun=False):
    # If number of non-digit letters is less than 2, return directly
    if len(re.findall(r'[^\d]', jp_text)) < 2:
        return jp_text
    
    # If it's a web link, return directly
    if jp_text.startswith("https") or jp_text.startswith("http"):
        # all valid characters in a URL
        return jp_text

    flag = True
    cn_text = '翻译失败'
    
    if dryrun:
        return "待翻译……"

    logger.info("\n------ JP Message ------\n\n" + jp_text + "\n------------------------\n\n")
    
    for name, model in translation_config.items():
        prompt = generate_prompt(jp_text)
        logger.info("\n-------- Prompt --------\n\n" + prompt + "\n------------------------\n\n")
        
        retry_count = model['retry_count']
        logger.info("Translating using " + name + " ...")
        
        ### API translation
        if model['type'] == 'api':
            if 'gemini' in name.lower():
                api_app = GoogleChatApp(api_key=model['key'], model_name=model['name'])
            elif 'poe' in name.lower():
                api_app = PoeAPIChatApp(api_key=model['key'], model_name=model['name'])
            elif 'claude' in name.lower():
                api_app = AnthropicChatApp(api_key=model['key'], model_name=model['name'])
            elif 'openai' in name.lower():
                api_app = OpenAIChatApp(api_key=model['key'], model_name=model['name'], endpoint=model['endpoint'])
            else:
                api_app = LiteLLMChatApp(api_key=model['key'], model_name=model['name'])
            
            backoff_time = 2  # Start with 2 seconds
            max_backoff_time = 64  # Maximum backoff time
            
            while flag and retry_count > 0:
                try:
                    cn_text = api_app.chat(prompt)
                    if "已经是中文" in cn_text:
                        return jp_text
                    if type(cn_text) is not str:
                        raise APITranslationFailure(f"Result is not string: {cn_text}")
                    if not validate(jp_text, cn_text):
                        raise APITranslationFailure(f"Validation failed: {cn_text}")
                    flag = False
                except APITranslationFailure as e:
                    if 'quota' in str(e):
                        retry_count += 1
                    logger.critical(f"API translation failed: {e}")
                    if 'BILLING' in config and config['BILLING'] == 'True':
                        pass
                    else:
                        time.sleep(backoff_time)
                    logger.debug(f"Retrying in {backoff_time} seconds ...")
                    backoff_time = min(backoff_time * 2, max_backoff_time)  # Exponential backoff
                    pass
                retry_count -= 1
        
        if not flag:
            break
                
        ### Web translation
        elif model['type'] == 'web':
            raise NotImplementedError("Web translation is not implemented yet.")
                
        if not flag:
            break
        
    if mode == "remove_annotation":
        return translate(cn_text, mode="polish", dryrun=dryrun)

    if type(cn_text) is not str:
        cn_text = "翻译失败"
    else:
        logger.info("\n------ CN Message ------\n\n" + cn_text + "\n------------------------\n\n")
                        
    return cn_text


class SqlWrapper:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self.cursor.execute('CREATE TABLE IF NOT EXISTS data (key TEXT PRIMARY KEY, value TEXT)')
        self.conn.commit()
    
    def items(self):
        self.cursor.execute('SELECT key, value FROM data')
        return self.cursor.fetchall()

    def __getitem__(self, key):
        self.cursor.execute('SELECT value FROM data WHERE key=?', (key,))
        result = self.cursor.fetchone()
        if result:
            return result[0]
        raise KeyError(key)

    def __setitem__(self, key, value):
        self.cursor.execute('INSERT OR REPLACE INTO data (key, value) VALUES (?, ?)', (key, value))
        self.conn.commit()

    def __delitem__(self, key):
        if key in self:
            self.cursor.execute('DELETE FROM data WHERE key=?', (key,))
            self.conn.commit()
        else:
            raise KeyError(key)

    def __contains__(self, key):
        self.cursor.execute('SELECT 1 FROM data WHERE key=?', (key,))
        return self.cursor.fetchone() is not None

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()
