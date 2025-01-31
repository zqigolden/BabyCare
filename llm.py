from datetime import datetime
import requests
from config import Config


def analyze_events(events, hours=24, debug=False):
    if not events:
        return None
        
    # 获取宝宝年龄
    birth_date = datetime(2024, 10, 25)  # 固定出生日期
    days_old = (datetime.now() - birth_date).days

    # 构造分析提示词
    event_summaries = []
    for event in events:
        summary = f"- [{event.start_time.strftime('%m月%d日 %H:%M')}] {event.event_type}"
        if event.duration:
            summary += f" ({event.duration}分钟)"
        if event.notes:
            summary += f" 备注: {event.notes}"
        event_summaries.append(summary)

    system_prompt = f"""
您是一位专业的婴幼儿发展观察员，请基于以下结构化数据完成养育行为分析：

[基础信息]
·出生日期：{birth_date.strftime('%Y年%m月%d日')}（当前{days_old}日龄）
·观察时段：最近{hours}小时活动记录
·数据特性：可能存在哺乳/睡眠/排泄等未记录项

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

请避免使用"危险""严重"等刺激性词汇，采用"建议关注""需要注意"等中性表达。所有结论需标注数据支撑依据，如"（基于近8小时3次哺乳记录）"。最后补充数据完整性声明："请注意本次分析基于家长提供的{len(events)}项记录，实际照护中请核实遗漏信息"

"""

    user_prompt = "\n".join(event_summaries)
    if debug:
        return system_prompt + "\n" + user_prompt
    try:
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {Config.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}],
                "temperature": 1.3,
                "max_tokens": 800,
            },
        )

        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            return "抱歉，分析服务暂时不可用。"

    except Exception as e:
        print(f"API调用错误: {e}")
        return "分析过程中出现错误，请稍后再试。"
