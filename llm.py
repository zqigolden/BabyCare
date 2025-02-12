from abc import ABC, abstractmethod
from datetime import datetime
import os
from google import genai
import requests
import logging
from typing import List, Optional
from prompts import generate_prompt


class LLM_client(ABC):
    @abstractmethod
    def chat(self, messages):
        pass

    def analyze(self, prompt):
        return self.chat(prompt)


class OpenAI_compatiable(LLM_client):
    def __init__(
        self,
        api_key,
        model_name,
        api_endpoint="https://api.openai.com",
        temperature=0.7,
        top_p=0.95,
        max_tokens=2048,
    ):
        self.api_key = api_key
        self.model_name = model_name
        self.api_endpoint = api_endpoint
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens

    def chat(self, messages):
        url = f"{self.api_endpoint}/v1/chat/completions"
        print(url)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": messages}],
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
        }

        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            raise Exception(f"API请求失败: {response.status_code}")


class DeepSeek(OpenAI_compatiable):
    def __init__(self):
        super().__init__(
            api_key=os.environ.get("DEEPSEEK_API_KEY"),
            model_name="deepseek-chat",
            api_endpoint="https://api.deepseek.com",
        )


class Gemini(LLM_client):
    def __init__(self, temperature=0.2, top_p=0.8, max_tokens=65536):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.api_key)

        self.config = {
            "temperature": temperature,
            "top_p": top_p,
            "max_output_tokens": max_tokens,
        }
        self.model = "gemini-2.0-flash-exp"

    def chat(self, messages):
        response = self.client.models.generate_content(
            model=self.model,
            contents=messages,
            config=self.config,
        )
        return response.text


def create_llm(provider="gemini"):
    if provider == "gemini":
        return Gemini()
    elif provider == "deepseek":
        return DeepSeek()
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


def format_event_summary(event) -> str:
    """格式化单个事件为字符串"""
    summary = f"- [{event.start_time.strftime('%m月%d日 %H:%M')}] {event.event_type}"
    if event.duration:
        summary += f" ({event.duration}分钟)"
    if event.notes:
        summary += f" 备注: {event.notes}"
    return summary


def analyze_events(
    events: List,
    birth_date: datetime,
    hours: int = 24,
    llm_provider: str = "gemini",
    debug: bool = False,
) -> Optional[str]:
    """分析婴儿活动数据并提供建议"""
    try:
        if not events:
            logging.warning("没有事件数据可供分析")
            return None

        days_old = (datetime.now() - birth_date).days
        prompt = generate_prompt(days_old, hours, events)

        if debug:
            logging.debug(f"分析提示:\\n{prompt}")

        llm = create_llm(llm_provider)
        output = llm.analyze(prompt)
        return post_process(output)

    except Exception as e:
        logging.error(f"分析过程出错: {str(e)}")
        raise


def post_process(output):
    """后处理分析结果"""
    # 移除多余的空行
    output = output.strip()
    # 移除无效的HTML标签
    output = output.replace("```html", "").replace("```", "")
    return output
