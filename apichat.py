from openai import OpenAI
import openai
import google.generativeai as genai
import yaml
import time
import asyncio
import fastapi_poe as fp
import requests
import re
import json


last_chat_time = None


class APITranslationFailure(Exception):
    def __init__(self, message="API connection failed after retries.", *args):
        super().__init__(message, *args)


class APIChatApp:
    def __init__(self, api_key, model_name, temperature):
        self.api_key = api_key
        self.model_name = model_name
        self.messages = [
            {
                "role": "system", 
                "content": "API_PROMPT"
            }, 
            {
                "role": "user",
                "content": "将下面的英文文本翻译为中文，如果无须翻译则返回原文。不要分析，只返回翻译内容：Example"
            },
            {
                "role": "assistant",
                "content": "例子" 
            }
        ]
        self.response = None
        self.temperature = temperature

    def chat(self, message):
        raise NotImplementedError("Subclasses must implement this method")


class OpenAIChatApp(APIChatApp):
    def __init__(self, api_key, model_name, temperature=0.7):
        super().__init__(api_key, model_name, temperature)
        if model_name in ['gpt-3.5-turbo']:
            base_url = "https://api.openai.com/v1"
        else:
            base_url = "http://localhost:7999/v1"
        # print(base_url)
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )

    def chat(self, message):
        self.messages = [
            {
                "role": "system", 
                "content": "You are a helpful translation assistant."
            },
            {
                "role": "user", 
                "content": message
            }
        ]
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=self.messages,
                temperature=self.temperature
            )
            self.messages = [{"role": "assistant", "content": response.choices[0].message.content}]
            self.response = response
            return response.choices[0].message.content
        except openai.APIError as e:
            raise APITranslationFailure(f"OpenAI API connection failed: {str(e)}")


class GoogleChatApp(APIChatApp):
    def __init__(self, api_key, model_name, temperature=0.2):
        super().__init__(api_key, model_name, temperature)
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.model_name)

    def chat(self, message):
        global last_chat_time
        
        if last_chat_time is not None:
            elapsed_time = time.time() - last_chat_time
            if elapsed_time < 1:
                time_to_wait = 1 - elapsed_time
                time.sleep(time_to_wait)
        last_chat_time = time.time()
            
        self.messages.append({"role": "user", "content": message})
        prompt = "".join([m["content"] for m in self.messages])
        try:
            response = self.model.generate_content(
                prompt,
                safety_settings=[
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                ],
                generation_config={"temperature": self.temperature, "max_output_tokens": 8192}
            )
            if 'block_reason' in response.prompt_feedback:
                print(vars(response))
                raise APITranslationFailure("Content generation blocked due to safety settings.")
            self.messages += [{"role": "assistant", "content": response.text}]
            return response.text
        except Exception as e:
            raise APITranslationFailure(f"Google API connection failed: {str(e)}")


class PoeAPIChatApp:
    def __init__(self, api_key, model_name):
        self.api_key = api_key
        self.model_name = model_name
        self.messages = []
        
    def chat(self, message):
        return asyncio.run(self._async_chat(message))
    
    async def _async_chat(self, message):
        self.messages.append({"role": "user", "content": message})
        final_message = ""
        try:
            async for partial in fp.get_bot_response(messages=self.messages, bot_name=self.model_name, 
                                                     api_key=self.api_key):
                final_message += partial.text
        except Exception as e:
            raise APITranslationFailure(f"Poe API connection failed: {str(e)}")
        return final_message


class BaichuanChatApp:
    def __init__(self, api_key, model_name):
        self.api_key = api_key
        self.model_name = model_name
        self.url = 'https://api.baichuan-ai.com/v1/chat/completions'
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }
    
    def chat(self, message, temperature=0.3, top_p=0.85, max_tokens=2048):
        payload = {
            "model": self.model_name,
            "messages": [{
                "role": "user",
                "content": message
            }],
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "with_search_enhance": False,
            "stream": True
        }

        response = requests.post(self.url, headers=self.headers, data=json.dumps(payload))
        if response.status_code == 200:
            raw_stream_response = response.text
            matches = ''.join(re.findall(r'\"content\":\"(.*?)\"', raw_stream_response, re.DOTALL))
            finish_reason_matches = re.findall(r'\"finish_reason\":\"(.*?)\"', raw_stream_response)
            if not finish_reason_matches or "stop" not in finish_reason_matches:
                err_msg = "\n".join(response.text.split('\n')[-5:])
                raise APITranslationFailure(f"Baichuan API translation terminated: {err_msg}")
            else:
                return matches.replace('\\n', '\n')
        else:
            raise APITranslationFailure(f"Baichuan API connection failed: {response.text}")


if __name__ == "__main__":
    # Example usage:
    with open("translation.yaml", "r") as f:
        translation_config = yaml.load(f, Loader=yaml.FullLoader)

    google_chat = GoogleChatApp(
        api_key=translation_config['Gemini-Pro-api']['key'], 
        model_name='gemini-pro'
    )

    prompt = f"""将下面的日文文本翻译成中文：
　微かな震動に揺れる大きな馬車の中、初めて乗る馬車と言う乗り物に感想を抱く事も無く頭を抱える。
　光永君は勇者祭への参加を了承したらしく、国賓として王宮へ向かうと楠さんと柚木さんに軽く挨拶をしてから、物凄く豪華な馬車に乗っていった。俺もそっちに連れて行って欲しかった。
「……あの、カイトさん？　大丈夫ですか？　御気分が優れないようなら、休憩等を挟みますが……」
「イエ、ダイジョウブデス」
「お嬢様、ミヤマ様はきっとまだ混乱されているのでしょう」
　このメイドはいけしゃあしゃあと……原因分かってるくせに、当り前の様にとぼけてやがる。"""
    # print(openai_chat.chat(prompt))
    print(google_chat.chat(prompt))
    # print(poe_chat.chat(prompt))
    # print(baichuan_chat.chat(prompt))
