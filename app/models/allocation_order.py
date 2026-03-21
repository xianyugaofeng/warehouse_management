from datetime import datetime
from app import db


class AllocationOrder(db.Model):
    """
    分配单主表
    根据销售单需求，从仓库库存中分配商品
    执行库存锁定，确保分配的库存不被其他操作使用
    """
    __tablename__ = 'allocation_orders'
    id = db.Column(db.Integer, primary_key=True)
    allocation_no = db.Column(db.String(32), unique=True, nullable=False)  # 分配单号（自动生成）
    
    # 关联关系
    sales_order_id = db.Column(db.Integer, db.ForeignKey('sales_orders.id'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('warehouse_locations.id'), nullable=False)
    
    # 分配策略
    allocation_strategy = db.Column(db.String(16), nullable=False, default='fifo')
    # fifo - 先进先出（按生产日期）
    # near_expiry - 临近过期优先
    
    # 状态流转
    status = db.Column(db.String(16), default='pending', nullable=False)
    # pending - 待处理（初始状态）
    # completed - 已完成（分配完成，库存已锁定）
    # partially_completed - 部分完成（部分商品库存不足）
    # failed - 失败（库存不足无法完成分配）
    
    # 统计数据
    total_allocated_qty = db.Column(db.Integer, default=0)  # 已分配总数量
    
    # 操作员信息
    operator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # 分配员
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # 审批人（可选）
    approved_time = db.Column(db.DateTime)  # 审批时间
    
    # 备注
    remark = db.Column(db.String(256))
    
    # 时间戳
    create_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联关系
    sales_order = db.relationship('SalesOrder', back_populates='allocation_order')
    location = db.relationship('WarehouseLocation', backref='allocation_orders')
    operator = db.relationship('User', foreign_keys=[operator_id], backref='created_allocations')
    # 多对一(多个分配单可由同一个操作员创建)
    manager = db.relationship('User', foreign_keys=[manager_id], backref='approved_allocations')
    items = db.relationship('AllocationItem', backref='allocation_order', lazy='dynamic', cascade='all, delete-orphan')
    # 一对多(一个分配单有多个分配明细)
    
    def __repr__(self):
        return f'<AllocationOrder {self.allocation_no}>'
    
    def get_summary(self):
        """获取分配单摘要"""
        return {
            'allocation_no': self.allocation_no,
            'sales_order_no': self.sales_order.order_no if self.sales_order else '',
            'total_allocated': self.total_allocated_qty,
            'strategy': self.allocation_strategy,
            'status': self.status
        }


class AllocationItem(db.Model):
    """
    分配单明细表
    记录将哪些库存分配给销售单中的商品
    关键作用：建立销售单商品与实际库存的绑定关系
    """
    __tablename__ = 'allocation_items'
    id = db.Column(db.Integer, primary_key=True)
    allocation_id = db.Column(db.Integer, db.ForeignKey('allocation_orders.id'), nullable=False)
    
    # 销售单与库存信息
    sales_order_item_id = db.Column(db.Integer, db.ForeignKey('sales_order_items.id'), nullable=False)
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventories.id'), nullable=False)
    
    # 分配数量
    allocated_qty = db.Column(db.Integer, nullable=False)  # 本次分配数量
    
    # 库存快照（用于后续追踪与审计）
    snapshot_quantity = db.Column(db.Integer)  # 分配时的库存数量
    snapshot_batch_no = db.Column(db.String(32))  # 分配时的批次号
    snapshot_expire_date = db.Column(db.Date)  # 分配时的过期日期
    
    # 状态
    status = db.Column(db.String(16), default='allocated', nullable=False)
    # allocated - 已分配（库存已锁定）
    # picked - 已拣货
    # shipped - 已出库
    
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关联关系
    sales_order_item = db.relationship('SalesOrderItem')
    inventory = db.relationship('Inventory', backref=db.backref('allocation_items', lazy='dynamic'))
    
    __table_args__ = (
        # 同一分配单中，同一库存不重复分配
        db.UniqueConstraint('allocation_id', 'inventory_id', name='_allocation_inventory_uc'),
    )
    
    def __repr__(self):
        return f'<AllocationItem allocation_id={self.allocation_id} inventory_id={self.inventory_id} qty={self.allocated_qty}>'
    
    def get_source_location(self):
        """获取分配的库存来源库位"""
        if self.inventory:
            return self.inventory.location
        return None
    
    def get_product(self):
        """获取商品信息"""
        if self.sales_order_item:
            return self.sales_order_item.product
        return None
