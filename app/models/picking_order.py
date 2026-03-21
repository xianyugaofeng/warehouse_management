from datetime import datetime
from app import db


class PickingOrder(db.Model):
    """
    拣货单主表
    将分配单中的库存从正常库位转移至拣货库位
    核心操作：库位转移、库存状态变更、锁定解除
    """
    __tablename__ = 'picking_orders'
    id = db.Column(db.Integer, primary_key=True)
    picking_no = db.Column(db.String(32), unique=True, nullable=False)  # 拣货单号（自动生成）
    
    # 关联关系
    allocation_order_id = db.Column(db.Integer, db.ForeignKey('allocation_orders.id'), nullable=False)
    sales_order_id = db.Column(db.Integer, db.ForeignKey('sales_orders.id'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('warehouse_locations.id'), nullable=False)
    
    # 拣货区库位（商品从normal库位转移到该picked_location）
    picking_location_id = db.Column(db.Integer, db.ForeignKey('warehouse_locations.id'), nullable=False)
    
    # 状态流转
    status = db.Column(db.String(16), default='pending', nullable=False)
    # pending - 待拣货
    # in_progress - 拣货中
    # completed - 已完成
    # failed - 失败
    
    # 统计数据
    total_picked_qty = db.Column(db.Integer, default=0)  # 已拣货总数量
    
    # 操作员信息
    warehouse_staff_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # 拣货员
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # 拣货主管（审批）
    completed_time = db.Column(db.DateTime)  # 完成时间
    
    # 备注
    remark = db.Column(db.String(256))
    
    # 时间戳
    create_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联关系
    allocation_order = db.relationship('AllocationOrder', backref='picking_order')
    sales_order = db.relationship('SalesOrder', back_populates='picking_order')
    location = db.relationship('WarehouseLocation', foreign_keys=[warehouse_id], backref='picking_orders_source')
    picking_location = db.relationship('WarehouseLocation', foreign_keys=[picking_location_id], backref='picking_orders_destination')
    warehouse_staff = db.relationship('User', foreign_keys=[warehouse_staff_id], backref='created_picking_orders')
    manager = db.relationship('User', foreign_keys=[manager_id], backref='approved_picking_orders')
    items = db.relationship('PickingItem', backref='picking_order', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<PickingOrder {self.picking_no}>'
    
    def can_complete(self):
        """检查是否可以完成拣货"""
        # 所有拣货项都已完成
        all_items = self.items.all()
        return len(all_items) > 0 and all(item.status == 'completed' for item in all_items)
    
    def get_summary(self):
        """获取拣货单摘要"""
        return {
            'picking_no': self.picking_no,
            'sales_order_no': self.sales_order.order_no if self.sales_order else '',
            'total_picked': self.total_picked_qty,
            'status': self.status,
            'location': self.location.name if self.location else '',
            'picking_location': self.picking_location.name if self.picking_location else ''
        }


class PickingItem(db.Model):
    """
    拣货单明细表
    记录具体的库存转移操作
    关键功能：库位转移（normal → picking）、库存锁定解除、库存状态更新
    """
    __tablename__ = 'picking_items'
    id = db.Column(db.Integer, primary_key=True)
    picking_id = db.Column(db.Integer, db.ForeignKey('picking_orders.id'), nullable=False)
    
    # 分配单明细与库存信息
    allocation_item_id = db.Column(db.Integer, db.ForeignKey('allocation_items.id'), nullable=False)
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventories.id'), nullable=False)
    
    # 拣货数量
    picked_qty = db.Column(db.Integer, nullable=False)  # 实际拣货数量
    
    # 源库位与目标库位
    source_location_id = db.Column(db.Integer, db.ForeignKey('warehouse_locations.id'), nullable=False)
    target_location_id = db.Column(db.Integer, db.ForeignKey('warehouse_locations.id'), nullable=False)
    
    # 库存快照（用于验证库存未改变）
    snapshot_quantity = db.Column(db.Integer)  # 拣货时的库存数量
    snapshot_locked = db.Column(db.Integer)  # 拣货时的锁定数量
    
    # 状态
    status = db.Column(db.String(16), default='pending', nullable=False)
    # pending - 待拣货
    # in_progress - 拣货中
    # completed - 已完成（库位转移完成，库存锁定已解除）
    
    # 库存变更记录
    change_log_id = db.Column(db.Integer, db.ForeignKey('inventory_change_logs.id'))  # 库位转移的变更日志
    
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    completed_time = db.Column(db.DateTime)  # 拣货完成时间
    
    # 关联关系
    allocation_item = db.relationship('AllocationItem', backref='picking_items')
    inventory = db.relationship('Inventory', backref=db.backref('picking_items', lazy='dynamic'))
    source_location = db.relationship('WarehouseLocation', foreign_keys=[source_location_id], backref='from_picking_items')
    target_location = db.relationship('WarehouseLocation', foreign_keys=[target_location_id], backref='to_picking_items')
    change_log = db.relationship('InventoryChangeLog', backref='picking_item')
    
    def __repr__(self):
        return f'<PickingItem picking_id={self.picking_id} qty={self.picked_qty}>'
    
    def get_product(self):
        """获取商品信息"""
        if self.inventory:
            return self.inventory.product
        return None
    
    def get_product_name(self):
        """获取商品名称"""
        product = self.get_product()
        return product.name if product else 'Unknown'
    
    def can_complete(self):
        """检查是否可以完成拣货"""
        # 源库存仍然存在且数量一致
        if not self.inventory:
            return False
        # 库存未改变（快照验证）
        if self.snapshot_quantity is not None and self.inventory.quantity != self.snapshot_quantity:
            return False
        return True
