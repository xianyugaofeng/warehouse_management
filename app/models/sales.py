from datetime import datetime
from app import db


class SalesOrder(db.Model):
    """
    销售单主表
    核心流程：销售单创建 → 分配 → 拣货 → 复核 → 出库
    """
    __tablename__ = 'sales_orders'
    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(32), unique=True, nullable=False)  # 销售单号（自动生成）
    related_order = db.Column(db.String(32))  # 来源采购单号
    
    # 客户与仓库信息
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)  # 关联客户
    location_id = db.Column(db.Integer, db.ForeignKey('warehouse_locations.id'))  # 指定发货仓库
    
    # 出库类型与日期
    expected_outbound_date = db.Column(db.Date, nullable=False)  # 期望出库日期
    
    # 状态流转
    status = db.Column(db.String(16), default='pending_allocation', nullable=False)
    # 状态列表：
    #   pending_allocation - 待分配（初始状态）
    #   allocated - 已分配（分配单已生成）
    #   picked - 已拣货（拣货单已完成）
    #   inspected - 已复核（复核单已通过）
    #   shipped - 已出库（出库单已完成）
    #   canceled - 已取消
    
    # 统计数据
    total_quantity = db.Column(db.Integer, default=0)  # 总出库数量
    allocated_quantity = db.Column(db.Integer, default=0)  # 已分配数量
    picked_quantity = db.Column(db.Integer, default=0)  # 已拣货数量
    shipped_quantity = db.Column(db.Integer, default=0)  # 已出库数量
    
    # 操作员信息
    operator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # 创建人
    allocation_manager_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # 分配负责人
    
    # 备注
    remark = db.Column(db.String(256))
    
    # 时间戳
    create_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联关系
    customer = db.relationship('Customer', backref='sales_orders')
    operator = db.relationship('User', foreign_keys=[operator_id], backref='created_sales_orders')
    allocation_manager = db.relationship('User', foreign_keys=[allocation_manager_id], backref='allocated_sales_orders')
    items = db.relationship('SalesOrderItem', backref='order', lazy='dynamic', cascade='all, delete-orphan')
    allocation_order = db.relationship('AllocationOrder', back_populates='sales_order', uselist=False)
    picking_order = db.relationship('PickingOrder', back_populates='sales_order', uselist=False)
    inspection_order = db.relationship('InspectionOrder', back_populates='sales_order', uselist=False)
    shipping_order = db.relationship('ShippingOrder', back_populates='sales_order', uselist=False)
    
    def __repr__(self):
        return f'<SalesOrder {self.order_no}>'
    
    def can_allocate(self):
        """检查是否可以进行分配"""
        return self.status == 'pending_allocation' and not self.allocation_order
    
    def can_pick(self):
        """检查是否可以进行拣货"""
        return self.status == 'allocated' and self.allocation_order and self.allocation_order.status == 'completed'
    
    def can_inspect(self):
        """检查是否可以进行复核"""
        return self.status == 'picked' and self.picking_order and self.picking_order.status == 'completed'
    
    def can_ship(self):
        """检查是否可以进行出库"""
        return self.status == 'inspected' and self.inspection_order and self.inspection_order.status == 'passed'
    
    def get_summary(self):
        """获取销售单摘要"""
        return {
            'order_no': self.order_no,
            'customer': self.customer.name if self.customer else '',
            'total_qty': self.total_quantity,
            'allocated_qty': self.allocated_quantity,
            'picked_qty': self.picked_quantity,
            'shipped_qty': self.shipped_quantity,
            'status': self.status
        }


class SalesOrderItem(db.Model):
    """
    销售单明细表
    存储销售单中的每个商品及其数量
    """
    __tablename__ = 'sales_order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('sales_orders.id'), nullable=False)
    
    # 商品信息
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    
    # 数量与价格
    quantity = db.Column(db.Integer, nullable=False)  # 需求数量
    unit_price = db.Column(db.Float)  # 单价（可选）
    subtotal = db.Column(db.Float)  # 小计（可选）
    
    # 批次与序号（可选）
    preferred_batch_no = db.Column(db.String(32))  # 指定批次号（优先使用）
    
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关联关系
    product = db.relationship('Product')
    
    __table_args__ = (
        # 同一销售单内同一客户+商品组合唯一
        # 这确保了销售订单中不会有重复的商品
        db.UniqueConstraint('order_id', 'product_id', name='_sales_order_product_uc'),
    )
    
    def __repr__(self):
        product_name = self.product.name if self.product else 'Unknown'
        return f'<SalesOrderItem {product_name} - {self.quantity}>'
