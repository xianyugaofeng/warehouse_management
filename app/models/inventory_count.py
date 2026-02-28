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

    def __repr__(self):
        return f'<InventoryCountTask {self.task_no} - {self.name}>'
    
class InventoryCountResult(db.Model):
    """库存盘点结果"""
    __tablename__ = 'inventory_count_results'
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('inventory_count_tasks.id'), nullable=False) # 关联盘点任务
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
