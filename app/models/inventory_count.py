from datetime import datetime
from app import db

class InventoryCountTask(db.Model):
    """库存盘点任务"""
    __tablename__ = 'inventory_count_tasks'
    id = db.Column(db.Integer, primary_key=True)
    task_no = db.Column(db.String(32), unique=True, nullable=False) # 盘点任务编号
    name = db.Column(db.String(64), nullable=False) # 任务名称
    type = db.Column(db.String(16), nullable=False) # 任务类型: time(时间触发), area(区域触发), timeshold(阈值触发)
    status = db.Column(db.String(16), nullable=False) # 状态: pending(待执行), in_progress(执行中), completed(已完成)， cancelled(已取消)
    start_time = db.Column(db.DateTime) # 开始时间
    end_time = db.Column(db.DateTime) # 结束时间
    operator_id = db.Column(db.Integer, db.ForeignKey('users.id')) # 执行时间
    area = db.Column(db.String(32)) # 盘点区域
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id')) # 供应商
    cycle_days = db.Column(db.Integer) # 周期天数
    thresold = db.Column(db.Integer) # 阈值
    remark = db.Column(db.String(256)) # 备注
    create_time = db.Column(db.DateTime, default=datetime.utcnow) # 创建时间
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow) # 更新时间

    # 关联
    operator = db.relationship('User', backref='inventory_count_tasks')
    supplier = db.relationship('Supplier')
    results = db.relationship('InventoryCountResult', backref='task', lazy='dynamic', cascade='all, delte-orphan')
    # 父对象的一切操作都会影响子对象（保存、合并、删除等）
    # 当子对象被解除与父对象的关联时，它也会被自动删除

    def __repr__(self):
        return f'<InventoryCountTask {self.task_no} - {self.name}>'
    
    