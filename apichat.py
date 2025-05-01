from openai import OpenAI
import openai
from google import genai
from google.genai import types
import yaml
import asyncio
import fastapi_poe as fp
from litellm import completion
from anthropic import Anthropic

SYSTEM_PROMPT = "你是一个翻译机器人，将外语翻译为中文。如果内容无需翻译，你会返回原文。你从不增加额外的分析，只返回翻译后的内容。你从来只回答中文。"
SAFETY_SETTINGS = [
    types.SafetySetting(
        category='HARM_CATEGORY_SEXUALLY_EXPLICIT',
        threshold='BLOCK_NONE'
    ),
    types.SafetySetting(
        category='HARM_CATEGORY_HATE_SPEECH',
        threshold='BLOCK_NONE'
    ),
    types.SafetySetting(
        category='HARM_CATEGORY_HARASSMENT',
        threshold='BLOCK_NONE'
    ),
    types.SafetySetting(
        category='HARM_CATEGORY_DANGEROUS_CONTENT',
        threshold='BLOCK_NONE'
    )
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
        self.client = genai.Client(api_key=self.api_key)
        
    def chat(self, message, image=None):
        if image:
            self.messages = []

        try:
            contents = []
            for msg in self.messages:
                if msg["role"] == "system":
                    continue
                elif msg["role"] == "assistant":
                    role = "model"
                else:
                    role = msg["role"]
                
                if "content" in msg:
                    contents.append(types.Content(
                        role=role,
                        parts=[types.Part.from_text(msg["content"])]
                    ))
                else:
                    contents.append(types.Content(
                        role=role,
                        parts=msg["parts"]
                    ))
            
            contents.append(types.Content(
                role="user",
                parts=[types.Part.from_text(message)]
            ))

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    safety_settings=SAFETY_SETTINGS,
                    temperature=self.temperature,
                    max_output_tokens=8192
                )
            )
            
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback is not None:
                print(vars(response))
                raise APITranslationFailure("Content generation blocked due to safety settings.")
            
            from loguru import logger
            logger.critical(response)
            
            self.messages.append({
                "role": "assistant",
                "content": response.text
            })
            
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
    
    # poe_chat = GoogleChatApp(
    #     api_key=translation_config['Gemini-Pro-api']['key'], 
    #     model_name=translation_config['Gemini-Pro-api']['name']
    # )
    
    poe_chat = PoeAPIChatApp(
        api_key=translation_config['Poe-api']['key'], 
        model_name=translation_config['Poe-api']['name']
    )

    # image_prompt += "\n\n https://i.ibb.co/hgt8pkg/example.png"
    # print(poe_chat.chat(image_prompt))

    # image_prompt = "https://resize.cdn.otakumode.com/ex/800.1000/shop/product/036fb4d5406746d5b3ea3a0eb9f7691c.jpg"

    # poe_chat = OpenAIChatApp(
    #     api_key=translation_config['Sakura-OpenAI-api']['key'], 
    #     model_name=translation_config['Sakura-OpenAI-api']['name'],
    #     endpoint=translation_config['Sakura-OpenAI-api']['endpoint']
    # )
    print(poe_chat.model_name)
    print(poe_chat.chat("翻译以下外文为中文：Hello, how are you today?"))
