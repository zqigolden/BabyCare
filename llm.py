from abc import ABC, abstractmethod
from datetime import datetime
import os
from google import genai
import requests
import logging
from typing import List, Optional


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


def create_analysis_prompt(events: List, days_old: int, hours: int) -> str:
    """创建分析提示"""
    event_summaries = [format_event_summary(event) for event in events]
    event_summaries = "\n".join(event_summaries)
    return f"""
您是一位专业的婴幼儿发展观察员，请基于以下结构化数据完成养育行为分析：

[基础信息]
·当前{days_old}日龄
·观察时段：最近{hours}小时活动记录
·数据特性：可能存在哺乳/睡眠/排泄等未记录项
·分析基于家长提供的{len(events)}项记录，可能存在遗漏信息

[事件列表]
{event_summaries}

[分析要求]
1. 异常扫描
- 特别关注记录中的备注信息及异常指标
- 识别生理指标与月龄标准的偏差（使用WHO生长曲线参照）
- 发现行为模式中的矛盾点（如睡眠间隔与清醒时长的冲突）

2. 风险推导
- 关联离散事件构建完整画像（如哺乳效率与排泄频次的关系）
- 标注连续3次以上出现的异常模式
- 推断可能被忽略的发育信号（注意区分偶发与持续状态）

3. 建议生成
- 提供不超过3项优先处理建议
- 附加2项预防性措施
- 明确需要医疗介入的警戒体征

[输出规范]
1. 使用Bootstrap栅格系统布局
2. 关键结论用<strong>加粗</strong>呈现
3. 不同风险等级使用对应色彩标签：
   - 常规提醒：<span class="badge bg-info">...</span>
   - 重点关注：<span class="badge bg-warning">...</span>
4. 时间序列数据可视化建议用<ul class="timeline">呈现

不要包含markdown标签，不需要解释生成的内容，只需提供分析结果即可。
"""


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
        prompt = create_analysis_prompt(events, days_old, hours)

        if debug:
            logging.debug(f"分析提示:\n{prompt}")

        llm = create_llm(llm_provider)
        return llm.analyze(prompt)

    except Exception as e:
        logging.error(f"分析过程出错: {str(e)}")
        raise
