from datetime import datetime
from app import db


class ReturnOrder(db.Model):
    __tablename__ = 'return_orders'
    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(32), unique=True, nullable=False)  # 退货单号（自动生成）
    return_date = db.Column(db.Date, default=datetime.utcnow, nullable=False)  # 退货日期
    return_reason = db.Column(db.String(256), nullable=False)  # 退货原因
    operator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # 关联操作员
    status = db.Column(db.String(16), default='pending', nullable=False)  # 状态(pending/completed)
    total_amount = db.Column(db.Float, default=0.0)  # 退货总金额
    remark = db.Column(db.String(256))  # 备注
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联退货明细
    items = db.relationship('ReturnItem', backref='return_order', lazy='dynamic', cascade='all, delete-orphan')

    # 关联操作员
    operator = db.relationship('User', backref='return_orders')

    def __repr__(self):
        return f'<ReturnOrder {self.order_no}>'


class ReturnItem(db.Model):
    __tablename__ = 'return_items'
    id = db.Column(db.Integer, primary_key=True)
    return_order_id = db.Column(db.Integer, db.ForeignKey('return_orders.id'), nullable=False)  # 关联退货单
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)  # 关联商品
    location_id = db.Column(db.Integer, db.ForeignKey('warehouse_locations.id'), nullable=False)  # 关联库位
    batch_no = db.Column(db.String(32))  # 批次号
    quantity = db.Column(db.Integer, nullable=False)  # 退货数量
    unit_price = db.Column(db.Float, nullable=False)  # 单价
    amount = db.Column(db.Float, nullable=False)  # 退货金额
    defect_reason = db.Column(db.String(64), nullable=False)  # 不合格原因
    remark = db.Column(db.String(256))  # 备注

    # 关联商品
    product = db.relationship('Product')
    # 关联库位
    location = db.relationship('WarehouseLocation')

    def __repr__(self):
        product = self.product.name if self.product else '未知商品'
        return f'<ReturnItem {product} - {self.quantity}>'