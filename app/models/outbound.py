from datetime import datetime
from app import db


class ShippingOrder(db.Model):
    """
    出库单主表（原 OutboundOrder，重新设计）
    最终的出库执行单，由复核单触发自动创建或手工创建
    支持部分出库功能
    """
    __tablename__ = 'shipping_orders'
    id = db.Column(db.Integer, primary_key=True)
    shipping_no = db.Column(db.String(32), unique=True, nullable=False)  # 出库单号（自动生成）
    
    # 关联关系
    inspection_order_id = db.Column(db.Integer, db.ForeignKey('inspection_orders.id'), nullable=False)
    sales_order_id = db.Column(db.Integer, db.ForeignKey('sales_orders.id'), nullable=False)
    picking_order_id = db.Column(db.Integer, db.ForeignKey('picking_orders.id'), nullable=False)
    
    # 收货人信息
    receiver = db.Column(db.String(32), nullable=False)  # 收货人名称
    receiver_phone = db.Column(db.String(16))  # 收货人电话
    receiver_address = db.Column(db.String(256))  # 收货地址
    
    # 出库信息
    outbound_date = db.Column(db.Date, default=datetime.utcnow, nullable=False)  # 实际出库日期
    
    # 数量统计
    total_quantity = db.Column(db.Integer, nullable=False)  # 计划出库数量
    shipped_quantity = db.Column(db.Integer, default=0)  # 已出库数量
    remaining_quantity = db.Column(db.Integer, nullable=False)  # 剩余可出库数量
    
    # 状态流转
    status = db.Column(db.String(16), default='pending', nullable=False)
    # pending - 待出库
    # partialShipped - 部分出库
    # completed - 已完成
    # canceled - 已取消
    
    # 操作员信息
    operator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # 操作员
    approver_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # 审批人（可选）
    approved_time = db.Column(db.DateTime)  # 审批时间
    
    # 备注与单据
    purpose = db.Column(db.String(64))  # 出库用途
    remark = db.Column(db.String(256))  # 备注
    related_order = db.Column(db.String(32))  # 关联采购单号（如有）
    
    # 时间戳
    create_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_time = db.Column(db.DateTime)  # 出库完成时间
    
    # 关联关系
    inspection_order = db.relationship('InspectionOrder', back_populates='shipping_orders')
    sales_order = db.relationship('SalesOrder', back_populates='shipping_order')
    picking_order = db.relationship('PickingOrder', backref='shipping_orders')
    operator = db.relationship('User', foreign_keys=[operator_id], backref='created_shipping_orders')
    approver = db.relationship('User', foreign_keys=[approver_id], backref='approved_shipping_orders')
    items = db.relationship('ShippingItem', backref='shipping_order', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<ShippingOrder {self.shipping_no}>'
    
    def can_complete(self):
        """检查是否可以完成出库"""
        return self.shipped_quantity == self.total_quantity
    
    def get_summary(self):
        """获取出库单摘要"""
        return {
            'shipping_no': self.shipping_no,
            'sales_order_no': self.sales_order.order_no if self.sales_order else '',
            'total_qty': self.total_quantity,
            'shipped_qty': self.shipped_quantity,
            'remaining_qty': self.remaining_quantity,
            'receiver': self.receiver,
            'status': self.status
        }


class ShippingItem(db.Model):
    """
    出库单明细表
    记录具体商品的出库操作
    支持部分出库，自动更新剩余可出库数量
    """
    __tablename__ = 'shipping_items'
    id = db.Column(db.Integer, primary_key=True)
    shipping_id = db.Column(db.Integer, db.ForeignKey('shipping_orders.id'), nullable=False)
    
    # 拣货单明细
    picking_item_id = db.Column(db.Integer, db.ForeignKey('picking_items.id'), nullable=False)
    
    # 库存信息
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventories.id'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('warehouse_locations.id'), nullable=False)
    
    # 商品与价格
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    unit_price = db.Column(db.Float)  # 单价
    
    # 出库数量
    planned_quantity = db.Column(db.Integer, nullable=False)  # 计划出库数量
    shipped_quantity = db.Column(db.Integer, default=0)  # 已出库数量
    remaining_quantity = db.Column(db.Integer, nullable=False)  # 剩余可出库数量
    
    # 库存快照（用于验证）
    snapshot_quantity = db.Column(db.Integer)  # 出库前的库存数量
    
    # 库存变更记录
    change_log_id = db.Column(db.Integer, db.ForeignKey('inventory_change_logs.id'))  # 扣减库存的变更日志
    
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关联关系
    picking_item = db.relationship('PickingItem', backref='shipping_items')
    inventory = db.relationship('Inventory', backref=db.backref('shipping_items', lazy='dynamic'))
    location = db.relationship('WarehouseLocation', backref='shipping_items')
    product = db.relationship('Product', backref='shipping_items')
    change_log = db.relationship('InventoryChangeLog', backref='shipping_item')
    
    def __repr__(self):
        product_name = self.product.name if self.product else 'Unknown'
        return f'<ShippingItem {product_name} - {self.shipped_quantity}/{self.planned_quantity}>'
    
    def can_ship(self, qty):
        """检查是否可以出库指定数量"""
        return qty > 0 and qty <= self.remaining_quantity
    
    def get_product_info(self):
        """获取商品信息"""
        if self.product:
            return {
                'code': self.product.code,
                'name': self.product.name,
                'spec': self.product.spec,
                'unit': self.product.unit
            }
        return {}


# 保留向后兼容性别名
OutboundOrder = ShippingOrder
OutboundItem = ShippingItem
