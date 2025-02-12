from flask import Flask, render_template, request, jsonify, redirect, url_for
import argparse
from models import db, BabyEvent, GrowthRecord
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
    last_page = request.cookies.get("lastVisitedPage")
    # 只有当不是直接点击时间轴链接时才进行重定向
    if (last_page and last_page != "/" and
            request.args.get("redirect", "true") == "true"):
        return redirect(last_page)
    events = (BabyEvent.query.filter(
                BabyEvent.start_time > datetime.now() - time_range)
              .order_by(BabyEvent.start_time.desc())
              .all())
    for event in events:
        if event.duration:
            # 数据库存储的是结束时间，计算开始时间
            event.end_time = event.start_time
            event.start_time = event.end_time - timedelta(minutes=event.duration)
    return render_template("index.html", events=events, datetime=datetime)


@app.route("/add_event", methods=["POST"])
def add_event():
    event_time = request.form.get("time")
    new_event = BabyEvent(
        event_type=request.form.get("type"),
        start_time=(datetime.strptime(event_time, "%Y-%m-%dT%H:%M")
                    if event_time else datetime.now()),
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
        # 获取表单数据
        event_type = request.form.get("type")
        event_time = request.form.get("time")
        duration = request.form.get("duration", "0")
        notes = request.form.get("notes", "")
        # 数据验证
        if not event_type or not event_time:
            return jsonify(
                {"success": False, "error": "类型和时间不能为空"}
            ), 400
        # 转换持续时间
        try:
            duration = int(duration) if duration.strip() else 0
        except ValueError:
            return jsonify(
                {"success": False, "error": "持续时间必须是有效的数字"}
            ), 400
        # 更新事件
        event.event_type = event_type
        event.start_time = datetime.strptime(event_time, "%Y-%m-%dT%H:%M")
        event.duration = duration
        event.notes = notes
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        print(f"Error updating event: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/analyze")
def ai_analysis():
    hours = request.args.get("hours", 24, type=int)
    provider = request.args.get("provider", "gemini")
    generate_new = request.args.get("new", False, type=bool)
    if generate_new:
        events = (BabyEvent.query.filter(
                    BabyEvent.start_time > datetime.now() - timedelta(hours=hours))
                  .order_by(BabyEvent.start_time.desc())
                  .all())
        analysis = analyze_events(
            events,
            llm_provider=provider,
            birth_date=datetime(2024, 10, 25),
            hours=hours,
        )
        if analysis:
            current_time = datetime.now()
            for event in events:
                event.ai_analysis = analysis
                event.analysis_time = current_time
                event.analysis_range = hours
                event.llm_provider = provider
            db.session.commit()
        return redirect(url_for("ai_analysis", hours=hours, provider=provider))
    time_range = timedelta(hours=hours)
    events = (BabyEvent.query.filter(
                BabyEvent.start_time > datetime.now() - time_range)
              .order_by(BabyEvent.start_time.desc())
              .all())
    latest_event = (BabyEvent.query.filter(
                        BabyEvent.ai_analysis.isnot(None))
                    .order_by(BabyEvent.analysis_time.desc())
                    .first())
    analysis = latest_event.ai_analysis if latest_event else None
    analysis_range = (latest_event.analysis_range if latest_event else None)
    print(analysis)
    feed_count = sum(1 for e in events if e.event_type == "吃奶")
    total_sleep = sum(e.duration or 0 for e in events if e.event_type == "睡眠")
    total_sleep /= 60
    return render_template(
        "analysis.html",
        events=events,
        analysis=analysis,
        feed_count=feed_count,
        hours=analysis_range,
        total_sleep=round(total_sleep, 1),
        analysis_time=(latest_event.analysis_time if latest_event else None),
        llm_provider=(latest_event.llm_provider if latest_event else None),
    )


def format_time_interval(minutes):
    """将分钟数转换为更易读的时间格式"""
    if minutes < 60:
        return f"{minutes}分钟"
    hours = minutes // 60
    remaining_minutes = minutes % 60
    if remaining_minutes == 0:
        return f"{hours}小时"
    return f"{hours}小时{remaining_minutes}分钟"


@app.route("/feeding")
def feeding():
    last_feeding = (BabyEvent.query.filter_by(event_type="吃奶")
                    .order_by(BabyEvent.start_time.desc())
                    .first())
    last_feeding_info = {
        "time": None,
        "duration": None,
        "last_side": None,
        "interval": None,
    }
    if last_feeding:
        feeding_details = parse_feeding_notes(last_feeding.notes)
        total_duration = feeding_details["left"] + feeding_details["right"]
        interval_minutes = int((datetime.now() - last_feeding.start_time).total_seconds() / 60)
        last_feeding_info.update({
            "time": last_feeding.start_time,
            "duration": total_duration,
            "last_side": feeding_details["last_side"],
            "interval": format_time_interval(interval_minutes),
        })
    return render_template(
        "feeding.html",
        timer_state=get_timer_state(),
        last_feeding=last_feeding_info,
    )


@app.route("/timer/toggle/<side>", methods=["POST"])
def toggle_timer(side):
    if side not in ["left", "right"]:
        return jsonify(success=False, error="Invalid side")
    current = timer_state[side]
    other_side = "right" if side == "left" else "left"
    if timer_state[other_side].running:
        stop_timer(other_side)
    if current.running:
        current.running = False
        if current.start_time:
            current.accumulated_time += int(
                (datetime.now() - current.start_time).total_seconds()
            )
            current.start_time = None
        timer_state["last_side"] = side
    else:
        current.running = True
        current.start_time = datetime.now()
    return jsonify(success=True, state=get_timer_state())


@app.route("/timer/reset/<side>", methods=["POST"])
def reset_side_timer(side):
    if side not in ["left", "right"]:
        return jsonify(success=False, error="Invalid side")
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


def parse_feeding_notes(notes: str) -> dict:
    """解析喂奶事件的备注信息"""
    result = {"left": 0, "right": 0, "last_side": None}
    if not notes:
        return result
    try:
        parts = notes.split(", ")
        for part in parts:
            if "左侧:" in part:
                result["left"] = int(
                    part.split("左侧:")[1].strip().replace("分钟", "")
                )
            elif "右侧:" in part:
                result["right"] = int(
                    part.split("右侧:")[1].strip().replace("分钟", "")
                )
            elif "最后喂养:" in part:
                result["last_side"] = part.split("最后喂养:")[1].strip()
    except Exception:
        pass
    return result


@app.route("/growth", methods=["GET", "POST"])
def growth():
    if request.method == "POST":
        date_str = request.form.get("date")
        height = request.form.get("height", type=float)
        weight = request.form.get("weight", type=float)
        if date_str:
            record_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        else:
            record_date = datetime.utcnow().date()
        new_record = GrowthRecord(date=record_date, height=height, weight=weight)
        db.session.add(new_record)
        db.session.commit()
        return redirect(url_for("growth"))
    records = GrowthRecord.query.order_by(GrowthRecord.date.asc()).all()
    return render_template("growth.html", records=records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the BabyCare app.")
    parser.add_argument(
        "--port", type=int, default=5600, help="Port to run the app on."
    )
    args = parser.parse_args()

    debug = True
    if args.port == 80:
        debug = False

    app.run(host="0.0.0.0", port=args.port, debug=debug)
