from flask import Flask, render_template, request, jsonify, redirect, url_for
from models import db, BabyEvent
from flask_bootstrap import Bootstrap5
from config import Config
from datetime import timedelta, datetime
from dataclasses import dataclass
from typing import Optional
from llm import analyze_events

app = Flask(__name__)
bootstrap = Bootstrap5(app)
app.config.from_object(Config)
db.init_app(app)

# 初始化数据库
with app.app_context():
    db.create_all()


@dataclass
class TimerState:
    running: bool = False
    start_time: Optional[datetime] = None
    accumulated_time: int = 0  # 累计时间(秒)


# 全局计时器状态
timer_state = {
    "left": TimerState(),
    "right": TimerState(),
    "last_side": None,  # 记录最后喂养侧
}


@app.route("/")
def index():
    hours = request.args.get("hours", 24, type=int)
    time_range = timedelta(hours=hours)

    last_page = request.cookies.get('lastVisitedPage')
    # 只有当不是直接点击时间轴链接时才进行重定向
    if last_page and last_page != '/' and request.args.get('redirect', 'true') == 'true':
        return redirect(last_page)

    events = (
        BabyEvent.query.filter(BabyEvent.start_time > datetime.now() - time_range)
        .order_by(BabyEvent.start_time.desc())
        .all()
    )

    return render_template(
        "index.html", events=events, datetime=datetime
    )  # 传递datetime对象


@app.route("/add_event", methods=["POST"])
def add_event():
    event_time = request.form.get("time")

    new_event = BabyEvent(
        event_type=request.form.get("type"),
        start_time=(
            datetime.strptime(event_time, "%Y-%m-%dT%H:%M")
            if event_time
            else datetime.now()
        ),
        duration=request.form.get("duration", type=int),
        notes=request.form.get("notes"),
    )

    db.session.add(new_event)
    db.session.commit()
    return jsonify(success=True)


@app.route("/delete_event/<int:event_id>", methods=["DELETE"])
def delete_event(event_id):
    event = BabyEvent.query.get_or_404(event_id)
    db.session.delete(event)
    db.session.commit()
    return jsonify(success=True)


@app.route("/edit_event/<int:event_id>", methods=["PUT"])
def edit_event(event_id):
    try:
        event = BabyEvent.query.get_or_404(event_id)

        # 获取表单数据并处理duration的空值情况
        duration_str = request.form.get("duration", "0")
        duration = int(duration_str) if duration_str.strip() else 0

        # 更新事件信息
        event.event_type = request.form.get("type")
        event.start_time = datetime.strptime(request.form.get("time"), "%Y-%m-%dT%H:%M")
        event.duration = duration
        event.notes = request.form.get("notes", "")

        db.session.commit()
        return jsonify({"success": True})
    except ValueError as e:
        db.session.rollback()
        return jsonify({"success": False, "error": "持续时间必须是有效的数字"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/analyze")
def ai_analysis():
    hours = request.args.get('hours', 24, type=int)
    provider = request.args.get('provider', 'gemini')  # 添加这一行
    generate_new = request.args.get('new', False, type=bool)
    
    if generate_new:
        events = BabyEvent.query.filter(
            BabyEvent.start_time > datetime.now() - timedelta(hours=hours)
        ).order_by(BabyEvent.start_time.desc()).all()
        
        analysis = analyze_events(events, llm_provider=provider, birth_date=datetime(2024, 10, 25))  # 修改这一行
        if analysis:
            current_time = datetime.now()
            for event in events:
                event.ai_analysis = analysis
                event.analysis_time = current_time
                event.analysis_range = hours
                event.llm_provider = provider  # 添加这一行
            db.session.commit()
        
        return redirect(url_for('ai_analysis', hours=hours, provider=provider))
    
    time_range = timedelta(hours=hours)

    # 获取时间范围内的事件
    events = (
        BabyEvent.query.filter(BabyEvent.start_time > datetime.now() - time_range)
        .order_by(BabyEvent.start_time.desc())
        .all()
    )

    # 获取最近的AI分析记录
    latest_event = (
        BabyEvent.query.filter(BabyEvent.ai_analysis.isnot(None))
        .order_by(BabyEvent.analysis_time.desc())
        .first()
    )
    analysis = latest_event.ai_analysis if latest_event else None
    analysis_range = latest_event.analysis_range if latest_event else None

    print(analysis)

    # 准备统计数据
    feed_count = sum(1 for e in events if e.event_type == "吃奶")
    total_sleep = sum(e.duration or 0 for e in events if e.event_type == "睡眠") / 60

    return render_template(
        "analysis.html",
        events=events,
        analysis=analysis,
        feed_count=feed_count,
        hours=analysis_range,
        total_sleep=round(total_sleep, 1),
        analysis_time=latest_event.analysis_time if latest_event else None,
        llm_provider=latest_event.llm_provider if latest_event else None,
    )


@app.route("/feeding")
def feeding():
    return render_template("feeding.html")


@app.route("/timer/toggle/<side>", methods=["POST"])
def toggle_timer(side):
    if side not in ["left", "right"]:
        return jsonify(success=False, error="Invalid side")

    current = timer_state[side]
    other_side = "right" if side == "left" else "left"

    # 如果另一侧在计时，先停止它
    if timer_state[other_side].running:
        stop_timer(other_side)

    if current.running:
        # 停止计时
        current.running = False
        if current.start_time:
            current.accumulated_time += int(
                (datetime.now() - current.start_time).total_seconds()
            )
            current.start_time = None
        timer_state["last_side"] = side  # 更新最后喂养侧
    else:
        # 开始计时
        current.running = True
        current.start_time = datetime.now()

    return jsonify(success=True, state=get_timer_state())


@app.route("/timer/reset/<side>", methods=["POST"])
def reset_side_timer(side):
    if side not in ["left", "right"]:
        return jsonify(success=False, error="Invalid side")

    # 重置指定侧的计时器
    timer_state[side].running = False
    timer_state[side].start_time = None
    timer_state[side].accumulated_time = 0

    return jsonify(success=True, state=get_timer_state())


def stop_timer(side):
    state = timer_state[side]
    if state.running and state.start_time:
        state.accumulated_time += int(
            (datetime.now() - state.start_time).total_seconds()
        )
        state.start_time = None
        state.running = False


@app.route("/timer/state")
def get_timer_state():
    result = {"left": {}, "right": {}, "last_side": timer_state["last_side"]}

    for side in ["left", "right"]:
        state = timer_state[side]
        elapsed = state.accumulated_time
        if state.running and state.start_time:
            elapsed += int((datetime.now() - state.start_time).total_seconds())
        result[side] = {"running": state.running, "time": elapsed}
    return result


@app.route("/timer/reset", methods=["POST"])
def reset_timer():
    global timer_state
    timer_state = {"left": TimerState(), "right": TimerState(), "last_side": None}
    return jsonify(success=True)


@app.template_filter("strftime")
def _jinja2_filter_datetime(date, fmt=None):
    return date.strftime(fmt or "%Y-%m-%d %H:%M")


@app.template_filter("convert_int")
def convert_int(value):
    try:
        return int(value) if value else 0
    except (TypeError, ValueError):
        return 0


@app.template_filter("side_to_cn")
def side_to_cn(side):
    return {"left": "左", "right": "右"}.get(side, "")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5600, debug=True)
