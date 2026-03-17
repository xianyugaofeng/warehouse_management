from datetime import datetime
from app import db


class PurchaseOrder(db.Model):
    __tablename__ = 'purchase_orders'
    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(32), unique=True, nullable=False)    # 采购单号（自动生成）
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'))   # 关联供应商
    operator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # 关联操作员
    expected_date = db.Column(db.Date, nullable=False)  # 预计到货日期
    actual_date = db.Column(db.Date)  # 实际到货日期
    total_amount = db.Column(db.Integer, default=0)   # 采购总数量
    allow_partial_receipt = db.Column(db.Boolean, default=False)  # 是否允许部分收货
    status = db.Column(db.String(16), default='pending_receipt', nullable=False)  # 状态(pending_receipt/receiving/completed)
    remark = db.Column(db.String(256))  # 备注
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联采购单明细
    items = db.relationship('PurchaseItem', backref='order', lazy='dynamic', cascade='all, delete-orphan')

    # 关联操作员
    operator = db.relationship('User', backref='purchase_orders')

    # 关联供应商
    supplier = db.relationship('Supplier')

    def __repr__(self):
        return f'<PurchaseOrder {self.order_no}>'


class PurchaseItem(db.Model):
    __tablename__ = 'purchase_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'), nullable=False)  # 关联采购单
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)   # 关联商品
    quantity = db.Column(db.Integer, nullable=False)   # 采购数量
    unit_price = db.Column(db.Float, nullable=False)    # 单价
    subtotal = db.Column(db.Float, nullable=False)     # 小计
    actual_quantity = db.Column(db.Integer, default=0)   # 实际收货数量
    quality_status = db.Column(db.String(16), default='pending')  # 质检状态(pending/passed/failed)
    remark = db.Column(db.String(256))  # 备注

    # 关联商品
    product = db.relationship('Product')

    def __repr__(self):
        product = self.product.name if self.product else '未知商品'
        return f'<PurchaseItem {product} - {self.quantity}>'