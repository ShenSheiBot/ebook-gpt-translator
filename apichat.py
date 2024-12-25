from openai import OpenAI
import openai
import google.generativeai as genai
import yaml
import asyncio
import fastapi_poe as fp
from litellm import completion
from anthropic import Anthropic


SYSTEM_PROMPT = "你是一个翻译机器人，将外语翻译为中文。如果内容无需翻译，你会返回原文。你从不增加额外的分析，只返回翻译后的内容。你从来只回答中文。"
SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]


class APITranslationFailure(Exception):
    def __init__(self, message="API connection failed after retries.", *args):
        super().__init__(message, *args)


class APIChatApp:
    def __init__(self, api_key, model_name, temperature):
        self.api_key = api_key
        self.model_name = model_name
        self.INITIAL_MESSAGE = [
            {
                "role": "system", 
                "content": SYSTEM_PROMPT
            }
        ]
        self.messages = self.INITIAL_MESSAGE
        self.response = None
        self.temperature = temperature

    def chat(self, message):
        raise NotImplementedError("Subclasses must implement this method")
    

class OpenAIChatApp(APIChatApp):
    def __init__(self, api_key, model_name, temperature=0.7, endpoint="https://api.openai.com/v1"):
        super().__init__(api_key, model_name, temperature)
        if "gpt" in model_name:
            endpoint = "https://api.openai.com/v1"
        # print(base_url)
        self.client = OpenAI(
            api_key=api_key,
            base_url=endpoint
        )
        
        self.messages = [
            {
                "role": "system", 
                "content": "你是一个翻译模型，可以流畅通顺地将日文翻译成简体中文。"
            }
        ]

    def chat(self, message):
        self.messages.append(
            {
                "role": "user", 
                "content": message
            }
        )
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=self.messages,
                temperature=self.temperature,
                stop=["<|im_end|>"],
                frequency_penalty=0.5
            )
            self.messages = [{"role": "assistant", "content": response.choices[0].message.content}]
            self.response = response
            return response.choices[0].message.content
        except openai.APIError as e:
            raise APITranslationFailure(f"OpenAI API connection failed: {str(e)}")

    
class LiteLLMChatApp(APIChatApp):
    def __init__(self, api_key, model_name, temperature=1.0):
        super().__init__(api_key, model_name, temperature)
        
    def chat(self, message):
        self.messages.append({"role": "user", "content": message})
        try:
            response = completion(
                messages=self.messages, model=self.model_name, 
                api_key=self.api_key, temperature=self.temperature,
                **({"safety_settings": SAFETY_SETTINGS} if "gemini" in self.model_name.lower() else {})
            )
            response = response.choices[0].message.content
            self.messages += [{"role": "assistant", "content": response}]
            return response
        except Exception as e:
            raise APITranslationFailure(f"LiteLLM API connection failed: {str(e)}")


class GoogleChatApp(APIChatApp):
    def __init__(self, api_key, model_name, temperature=1.0):
        super().__init__(api_key, model_name, temperature)
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.model_name, system_instruction=SYSTEM_PROMPT)
        self.SAFETY_SETTINGS = SAFETY_SETTINGS

    def chat(self, message, image=None):
        if image:
            self.messages = []

        # Update all content to parts
        new_messages = []
        for i, m in enumerate(self.messages):
            if m["role"] == "assistant":
                m["role"] = "model"
            elif m["role"] == "system":
                continue
            if "content" in m:
                new_messages.append({"role": m["role"], "parts": [m["content"]]})
            else:
                new_messages.append({"role": m["role"], "parts": m["parts"]})
        self.messages = new_messages
        self.messages.append({"role": "user", "parts": [message]})
        try:
            response = self.model.generate_content(
                self.messages,
                safety_settings=self.SAFETY_SETTINGS,
                generation_config={"temperature": self.temperature, "max_output_tokens": 8192}
            )
            if 'block_reason' in response.prompt_feedback:
                print(vars(response))
                raise APITranslationFailure("Content generation blocked due to safety settings.")
            self.messages += [{"role": "assistant", "parts": response.parts}]
            return response.text if hasattr(response, "text") else response.parts
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


class AnthropicChatApp(APIChatApp):
    def __init__(self, api_key, model_name, temperature=1.0):
        super().__init__(api_key, model_name, temperature)
        self.client = Anthropic(api_key=self.api_key)
        self.system_prompt = SYSTEM_PROMPT
        self.messages = []

    def chat(self, message):
        self.messages.append({"role": "user", "content": message})
        self.messages.insert(0, {"role": "user", "content": self.system_prompt})
        try:
            response = self.client.messages.create(
                model=self.model_name,
                messages=self.messages,
                system=self.system_prompt,
                max_tokens=1000,
                temperature=self.temperature
            )
            assistant_message = response.content[0].text
            self.messages.append({"role": "assistant", "content": assistant_message})
            return assistant_message
        except Exception as e:
            raise APITranslationFailure(f"Anthropic API connection failed: {str(e)}")


if __name__ == "__main__":
    # Example usage:
    with open("translation.yaml", "r") as f:
        translation_config = yaml.load(f, Loader=yaml.FullLoader)

    image_prompt = "Recognize text from the book. Skip header and page number."
    
    # poe_chat = PoeAPIChatApp(
    #     api_key=translation_config['Poe-api']['key'], 
    #     model_name='Gemini-1.5-Pro'
    # )

    # image_prompt += "\n\n https://i.ibb.co/hgt8pkg/example.png"
    # print(poe_chat.chat(image_prompt))

    # image_prompt = "https://resize.cdn.otakumode.com/ex/800.1000/shop/product/036fb4d5406746d5b3ea3a0eb9f7691c.jpg"

    poe_chat = OpenAIChatApp(
        api_key=translation_config['Sakura-OpenAI-api']['key'], 
        model_name=translation_config['Sakura-OpenAI-api']['name'],
        endpoint=translation_config['Sakura-OpenAI-api']['endpoint']
    )
    poe_chat.chat(image_prompt)
