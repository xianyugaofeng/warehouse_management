from datetime import datetime
from app import db


class InboundOrder(db.Model):
    __tablename__ = 'inbound_orders'
    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(32), unique=True, nullable=False)    # 入库单号（自动生成）
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'))   # 关联供应商
    related_order = db.Column(db.String(32), nullable=False)    # 采购单号（送货单）
    delivery_order_no = db.Column(db.String(32), nullable=False)    # 正式送货单号
    inspection_cert_no = db.Column(db.String(32), nullable=False)    # 检验合格单号
    operator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # 关联操作员
    inbound_date = db.Column(db.Date, default=datetime.utcnow, nullable=False)  # 入库日期
    total_amount = db.Column(db.Integer, default=0)   # 入库总数量
    status = db.Column(db.String(16), default='completed', nullable=False)  # 状态(draft/completed/canceled/rejected)
    reject_reason = db.Column(db.String(256))  # 拒绝原因
    remark = db.Column(db.String(256))  # 备注
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联入库单明细
    items = db.relationship('InboundItem', backref='order', lazy='dynamic', cascade='all, delete-orphan')

    # 关联操作员
    operator = db.relationship('User', backref='inbound_orders')

    # 关联供应商
    supplier = db.relationship('Supplier')

    def __repr__(self):
        return f'<InboundOrder {self.order_no}>'


class InboundItem(db.Model):
    __tablename__ = 'inbound_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('inbound_orders.id'), nullable=False)  # 关联入库单
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)   # 关联商品
    location_id = db.Column(db.Integer, db.ForeignKey('warehouse_locations.id'), nullable=False)   # 关联库位
    quantity = db.Column(db.Integer, nullable=False)   # 入库数量
    batch_no = db.Column(db.String(32), nullable=False)   # 批次号
    production_date = db.Column(db.Date)   # 生产日期
    expire_date = db.Column(db.Date)    # 过期日期
    unit_price = db.Column(db.Float, nullable=False)    # 单价
    subtotal = db.Column(db.Float, nullable=False)     # 小计
    signature = db.Column(db.String(64))  # 仓库管理员签字

    # 关联商品、库位
    product = db.relationship('Product')
    location = db.relationship('WarehouseLocation')

    def __repr__(self):
        product = self.product.name if self.product else '未知商品'
        return f'<InboundItem {product} - {self.quantity}>'

