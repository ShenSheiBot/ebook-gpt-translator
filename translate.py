from apichat import OpenAIChatApp, GoogleChatApp, PoeAPIChatApp, BaichuanChatApp, APITranslationFailure
from loguru import logger
import re
import yaml
import sqlite3

with open("translation.yaml", "r") as f:
    translation_config = yaml.load(f, Loader=yaml.FullLoader)


def generate_prompt(jp_text, mode="translation"):
    return "将下面的英文文本翻译为中文：\n" + jp_text


def validate(jp_text, cn_text):
    # Check ratio of Chinese characters to English characters (avg 1.6)
    if "**" in cn_text and "**" not in jp_text:
        return False
    if len(cn_text) == 0:
        return True
    ratio = len(jp_text) / len(cn_text)
    if ratio < 0.9 or ratio > 10:
        logger.warning(f"Validation failed: ratio of Chinese characters to English words: {ratio}")
        return False
    else:
        return True


def translate(jp_text, mode="translation", dryrun=False):
    # If single character, return directly
    if len(jp_text.strip()) == 1:
        return jp_text
           
    flag = True
    
    if dryrun:
        return "待翻译……"

    logger.info("\n------ JP Message ------\n\n" + jp_text + "\n------------------------\n\n")
    
    for name, model in translation_config.items():
        
        if "Sakura" in name:
            prompt = generate_prompt(jp_text, mode="sakura")
            logger.info("\n-------- Prompt --------\n\n" + prompt + "\n------------------------\n\n")
        else:
            prompt = generate_prompt(jp_text, mode=mode)
            logger.info("\n-------- Prompt --------\n\n" + prompt + "\n------------------------\n\n")
        
        if mode == "title_translation":
            if 'Poe' not in name:
                continue
            else:
                model['name'] = "ChatGPT"
        
        retry_count = model['retry_count']
        
        logger.info("Translating using " + name + " ...")
        
        ### API translation
        if model['type'] == 'api':
            if 'Gemini' in name:
                api_app = GoogleChatApp(api_key=model['key'], model_name=model['name'])
            elif 'OpenAI' in name:
                api_app = OpenAIChatApp(api_key=model['key'], model_name=model['name'])
            elif 'Poe' in name:
                api_app = PoeAPIChatApp(api_key=model['key'], model_name=model['name'])
            elif 'Baichuan' in name:
                api_app = BaichuanChatApp(api_key=model['key'], model_name=model['name'])
            else:
                raise ValueError("Invalid model name.")
            
            while flag and retry_count > 0:
                try:
                    cn_text = api_app.chat(prompt)
                    if not validate(jp_text, cn_text):
                        raise APITranslationFailure("Validation failed.")
                    flag = False
                except APITranslationFailure as e:
                    logger.critical(f"API translation failed: {e}")
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