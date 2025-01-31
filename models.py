from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class BabyEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(20))  
    start_time = db.Column(db.DateTime, default=datetime.now)
    duration = db.Column(db.Integer)      
    notes = db.Column(db.Text)
    ai_analysis = db.Column(db.Text)      
    analysis_time = db.Column(db.DateTime) 
    analysis_range = db.Column(db.Integer) # 新增分析范围字段(小时)