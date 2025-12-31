from datetime import datetime
from app import db


class OutboundOrder(db.Model):
    __tablename__ = 'outbound_orders'
    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(32), unique=True, nullable=False)   # 出库单号（自动生成）
    related_order = db.Column(db.String(32))   # 销售单号
    operator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)   # 操作员
    receiver = db.Column(db.String(32), nullable=False)   # 领用人
    receive_phone = db.Column(db.String(16))   # 领用电话
    outbound_date = db.Column(db.Date, default=datetime.utcnow, nullable=False)   # 出库日期
    total_amount = db.Column(db.Integer, default=0)   # 出库总数量
    purpose = db.Column(db.String(64))   # 领用用途
    status = db.Column(db.String(16), default='completed', nullable=False)   # 状态(draft/completed/canceled)
    remark = db.Column(db.String(256))   # 备注
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联出库单明细
    items = db.relationship('OutboundItem', backref='order', lazy='dynamic', cascade='all,delete-orphan')

    # 关联操作员
    operator = db.relationship('User', backref='outbound_orders')

    def __repr__(self):
        return f'<OutboundOrder {self.order_no}>'


class OutboundItem(db.Model):
    __tablename__ = 'outbound_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('outbound_orders.id'), nullable=False)   # 关联出库单
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)   # 关联商品
    location_id = db.Column(db.Integer, db.ForeignKey('warehouse_locations.id'), nullable=False)   # 关联库位
    quantity = db.Column(db.Integer, nullable=False)   # 出库数量
    batch_no = db.Column(db.String(32))   # 批次号
    unit_price = db.Column(db.Float)   # 单价（可选）
    subtotal = db.Column(db.Float)     # 小计（可选）

    # 关联商品、库位
    product = db.relationship('Product')
    location = db.relationship('WarehouseLocation')

    def __repr__(self):
        product = self.product.name if self.product else '未知商品'
        return f'<OutboundItem {product} - {self.quantity}>'
