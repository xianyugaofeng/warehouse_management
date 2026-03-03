from datetime import datetime
from app import db

class InventoryCountTask(db.Model):
    """库存盘点任务"""
    __tablename__ = 'inventory_count_tasks'
    id = db.Column(db.Integer, primary_key=True)
    task_no = db.Column(db.String(32), unique=True, nullable=False) # 盘点任务编号
    name = db.Column(db.String(64), nullable=False) # 任务名称
    type = db.Column(db.String(16), nullable=False) # 任务类型: time(时间触发), area(区域触发), threshold(阈值触发)
    status = db.Column(db.String(16), nullable=False) # 状态: pending(待执行), in_progress(执行中), completed(已完成)， cancelled(已取消)
    start_time = db.Column(db.DateTime) # 开始时间
    end_time = db.Column(db.DateTime) # 结束时间
    operator_id = db.Column(db.Integer, db.ForeignKey('users.id')) # 执行人员
    area = db.Column(db.String(32)) # 盘点区域
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id')) # 供应商
    cycle_days = db.Column(db.Integer) # 周期天数
    threshold = db.Column(db.Integer) # 阈值
    remark = db.Column(db.String(256)) # 备注
    create_time = db.Column(db.DateTime, default=datetime.utcnow) # 创建时间
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow) # 更新时间

    # 关联
    operator = db.relationship('User', backref='inventory_count_tasks')
    supplier = db.relationship('Supplier')
    results = db.relationship('InventoryCountResult', backref='task', lazy='dynamic', cascade='all, delete-orphan')
    # 父对象的一切操作都会影响子对象（保存、合并、删除等）
    # 当子对象被解除与父对象的关联时，它也会被自动删除
    # cascade='all, delete-orphan' 
    # 表示当删除InventoryCountTask时，会自动删除与之关联的所有InventoryCountResult
    # 当 InventoryCountResult 与 InventoryCountTask 解除关联时，也会被自动删除

    # 正向关联: 通过 backref 参数，SQLAlchemy 在关联的另一端自动创建反向引用
    # 反向关联: backref='task' 会在 InventoryCountResult 中自动生成 task 属性，指向关联的 InventoryCountTask 实例

    # 查询时的自动处理
    # 延迟加载: 默认情况下，关联数据会在首次访问时才从数据库加载（懒加载）
    # 生成查询: 自动构建并执行 SQL 查询，获取关联数据
    def __repr__(self):
        return f'<InventoryCountTask {self.task_no} - {self.name}>'
    
class InventoryCountResult(db.Model):
    """库存盘点结果"""
    __tablename__ = 'inventory_count_results'
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('inventory_count_tasks.id'), nullable=False) # 关联盘点任务
    # - InventoryCountResult 表中有一个 task_id 外键，指向 InventoryCountTask 表的 id
    # 这是物理上的关联，存储在数据库中
    # - SQLAlchemy 通过 relationship 和 backref 在 ORM 层面建立双向引用
    # 当查询时，SQLAlchemy 会自动处理这些关联，使得可以通过属性访问关联对象

    # SQLAlchemy 的关联基于数据库外键实现
    # 识别外键: 自动查找关联模型中的外键字段InventoryCountResult.task_id
    # 建立映射: 将外键与主键关联，形成逻辑上的父子关系

    
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventories.id'), nullable=False) # 关联库存
    expected_quantity = db.Column(db.Integer, nullable=False) # 系统预期数量
    actual_quantity = db.Column(db.Integer, nullable=False) # 实际盘点数量
    difference = db.Column(db.Integer) # 差异数量
    status = db.Column(db.String(16), default='pending', nullable=False) # 状态: pending(待处理), auto_adjusted(自动调整)
    # manual_processing(人工处理) processed(已处理)
    adjust_reason = db.Column(db.String(256)) # 调整原因
    processor_id = db.Column(db.Integer, db.ForeignKey('users.id')) # 处理人员
    process_time = db.Column(db.DateTime, default=datetime.utcnow) # 处理时间
    create_time = db.Column(db.DateTime, default=datetime.utcnow) # 创建时间

    # 关联
    inventory = db.relationship('Inventory')
    processor = db.relationship('User')

    def __repr__(self):
        return f'<InventoryCountResult {self.id} - {self.inventory_id}>'

class InventoryAdjustment(db.Model):
    """库存调整历史"""
    __tablename__ = 'inventory_adjustments'
    id = db.Column(db.Integer, primary_key=True)
    adjustment_no = db.Column(db.String(32), unique=True, nullable=False) # 调整单号
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventories.id'), nullable=False) # 关联库存
    before_quantity = db.Column(db.Integer, nullable=False) # 调整前数量
    after_quantity = db.Column(db.Integer, nullable=False) # 调整后数量
    adjustment_quantity = db.Column(db.Integer, nullable=False) # 调整数量
    type = db.Column(db.String(16), nullable=False) # 调整类别: count_adjustment(盘点调整), loss(损耗), other(其他)
    reason = db.Column(db.String(256), nullable=False) # 调整原因
    operator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False) # 操作人
    count_task_id = db.Column(db.Integer, db.ForeignKey('inventory_count_tasks.id')) # 关联盘点任务
    create_time = db.Column(db.DateTime, default=datetime.utcnow) # 创建时间

    # 关联
    inventory = db.relationship('Inventory')
    operator = db.relationship('User')
    count_task = db.relationship('InventoryCountTask')

    def __repr__(self):
        return f'<InventoryAdjustment {self.adjustment_no}>'

class VirtualInventory(db.Model):
    """虚拟库存"""
    __tablename__ = 'virtual_inventories'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False) # 关联商品
    location_id = db.Column(db.Integer, db.ForeignKey('warehouse_locations.id'), nullable=False) # 关联库位
    batch_no = db.Column(db.String(32)) # 批次号
    physical_quantity = db.Column(db.Integer, default=0) # 实物库存
    in_transit_quantity = db.Column(db.Integer, default=0) # 在途库存
    allocate_quantity = db.Column(db.Integer, default=0) # 已分配库存
    virtual_quantity = db.Column(db.Integer, default=0) # 虚拟库存 = 实物库存 + 在途库存 - 已分配库存
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow) # 更新时间

    # 联合唯一约束
    __table_args__ = (
        db.UniqueConstraint('product_id', 'location_id', 'batch_no', name='_virtual_product_location_batch_uc')
    )

    # 关联 
    product = db.relationship('Product')
    location = db.relationship('WarehouseLocation')

    def __repr__(self):
        return f'<VirtualInventory {self.product_id} - {self.location_id} - {self.virtual_quantity}>'

class InventoryAccuracy(db.Model):
    """库存准确率记录"""
    __tablename__ = 'inventory_accuracies'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False) # 日期
    total_items = db.Column(db.Integer, nullable=False) # 总盘点项数
    accurate_items = db.Column(db.Integer, nullable=False) # 准确项数
    accuracy_rate = db.Column(db.Float, nullable=False) # 准确率
    create_time = db.Column(db.DateTime, default=datetime.utcnow) # 创建时间

    def __repr__(self):
        return f'<InventoryAccuracy {self.date} - {self.accuracy_rate:.2f}%>'


class InventoryCountTaskSchedule(db.Model):
    """盘点任务调度"""
    __tablename__ = 'inventory_count_task_schedules'
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('inventory_count_tasks.id'), nullable=False) # 关联盘点任务
    interval_hours = db.Column(db.Integer, default=24) # 运行间隔（小时）
    max_executions = db.Column(db.Integer, default=0) # 最大执行次数，0表示无限
    execution_count = db.Column(db.Integer, default=0) # 当前执行次数
    last_execution_time = db.Column(db.DateTime) # 上次执行时间
    next_execution_time = db.Column(db.DateTime) # 下次执行时间
    status = db.Column(db.String(16), default='active', nullable=False) # 状态：active(活跃), paused(暂停), stopped(停止)
    create_time = db.Column(db.DateTime, default=datetime.utcnow) # 创建时间
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow) # 更新时间

    # 关联
    task = db.relationship('InventoryCountTask', backref='schedules')

    def __repr__(self):
        return f'<InventoryCountTaskSchedule {self.task_id} - {self.status}>'


class InventoryCountTaskLog(db.Model):
    """盘点任务执行日志"""
    __tablename__ = 'inventory_count_task_logs'
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('inventory_count_tasks.id'), nullable=False) # 关联盘点任务
    schedule_id = db.Column(db.Integer, db.ForeignKey('inventory_count_task_schedules.id')) # 关联调度
    start_time = db.Column(db.DateTime, nullable=False) # 开始时间
    end_time = db.Column(db.DateTime) # 结束时间
    status = db.Column(db.String(16), nullable=False) # 状态：success(成功), failed(失败)
    error_message = db.Column(db.Text) # 错误信息
    execution_type = db.Column(db.String(16), nullable=False) # 执行类型：manual(手动), automatic(自动)
    operator_id = db.Column(db.Integer, db.ForeignKey('users.id')) # 操作人
    create_time = db.Column(db.DateTime, default=datetime.utcnow) # 创建时间

    # 关联
    task = db.relationship('InventoryCountTask')
    schedule = db.relationship('InventoryCountTaskSchedule')
    operator = db.relationship('User')

    def __repr__(self):
        return f'<InventoryCountTaskLog {self.task_id} - {self.status}>'
