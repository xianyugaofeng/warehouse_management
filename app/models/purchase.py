from datetime import datetime
from app import db


class PurchaseOrder(db.Model):
    __tablename__ = 'purchase_orders'
    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(32), unique=True, nullable=False)    # 采购单号（自动生成）
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'))   # 关联供应商
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)  # 关联商品（一个采购单只能对应一种商品）
    operator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # 关联操作员
    expected_date = db.Column(db.Date, nullable=False)  # 预计到货日期
    actual_date = db.Column(db.Date)  # 实际到货日期
    quantity = db.Column(db.Integer, nullable=False)   # 采购数量
    unit_price = db.Column(db.Float, nullable=False)    # 单价
    subtotal = db.Column(db.Float, nullable=False)     # 小计
    actual_quantity = db.Column(db.Integer, default=0)   # 实际收货数量
    qualified_quantity = db.Column(db.Integer, default=0)   # 合格数量
    unqualified_quantity = db.Column(db.Integer, default=0)   # 不合格数量
    quality_status = db.Column(db.String(16), default='pending')  # 质检状态(pending/completed)
    allow_partial_receipt = db.Column(db.Boolean, default=False)  # 是否允许部分收货
    status = db.Column(db.String(16), default='pending_receipt', nullable=False)  # 状态(pending_receipt/receiving/completed)
    remark = db.Column(db.String(256))  # 备注
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联操作员
    operator = db.relationship('User', backref='purchase_orders')

    # 关联供应商
    supplier = db.relationship('Supplier')
    
    # 关联商品
    product = db.relationship('Product')

    def __repr__(self):
        return f'<PurchaseOrder {self.order_no}>'