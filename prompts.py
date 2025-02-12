__all__ = ['generate_prompt']
from models import BabyEvent

_PROMPTS = {}

_PROMPTS["INFO"] = """
您是一位婴幼儿养育指导专家，请根据家长提供的日常记录进行简明分析：

[基础信息]
·当前{days_old}日龄
·观察时段:最近{hours}小时
·数据说明：可能存在哺乳/睡眠等未记录项
·基于{events_length}条记录分析

[事件列表]
{event_summaries}
"""

_PROMPTS["OUTPUT"] = """
[输出要求]
禁止直接使用示例中的描述，必须关联到事件列表内容
不需要解释生成的内容，只需提供分析结果
[格式要求]
0. 输出html格式
1. 使用Bootstrap栅格系统布局
2. 关键结论用<strong>加粗</strong>呈现
3. 不同风险等级使用对应色彩标签：
   - 常规提醒：<span class="badge bg-info">...</span>
   - 重点关注：<span class="badge bg-warning">...</span>
"""

_PROMPTS["v1"] = """
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
"""

_PROMPTS["trial"] = """
[分析要求]
1.异常识别，例如：
    - 核对关键指标（体重/身长）是否符合WHO生长曲线50%基准线±20%
    - 发现矛盾作息模式（如清醒3小时未睡却只睡20分钟）
    - 标注重复3次以上的非常规现象
2. 关联分析，例如：
    - 哺乳量与排泄次数比例（每100ml奶对应3-4次排尿）
    - 睡眠周期与进食间隔的联动关系
    - 异常备注与发生时间的关联性
3. 实操建议，例如：
    - 必做事项（选最关键3项）：
    - 直接可操作的改善步骤（如"每次哺乳后竖抱拍嗝10分钟"）
    - 具体参数调整（如"清醒超过1.5小时启动睡眠程序"）
    - 简单检测方法（如"哺乳时听吞咽声，每分钟应有3-5次"）

4. 预防措施，例如：
    - 环境优化清单（温度/光线/声音）
    - 互动技巧（视觉追踪练习方法）

5. 医疗警戒体征（必须基于当前数据）：
    - 从[事件列表]中提取超过安全阈值的数值型指标（如拒食时长>X小时/单日腹泻>X次）
    - 根据宝宝当前{days_old}天龄匹配WHO异常体征（如体重日增长<20g）
    - 仅当数据中出现肉眼可见异常时列举（如便便含血丝/呼吸频率>60次/分）

所有建议需满足：1步操作、无需专业工具、立即见效
"""


def generate_prompt(days_old: int, hours: int, events: list[BabyEvent], prompt_name='trial'):
    if prompt_name not in _PROMPTS:
        raise ValueError(f"Unknown prompt name: {prompt_name}")
    prompt = f"{_PROMPTS['INFO']}{_PROMPTS[prompt_name]}{_PROMPTS['OUTPUT']}"
    events_str = "\n".join([f"- [{event.start_time.strftime('%m月%d日 %H:%M')}] {event.event_type}" for event in events])
    return prompt.format(days_old=days_old, hours=hours, events_length=len(events), event_summaries=events_str)
