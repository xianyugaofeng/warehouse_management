from datetime import datetime
from app import db


class DefectiveProduct(db.Model):
    __tablename__ = 'defective_products'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)  # 关联商品
    location_id = db.Column(db.Integer, db.ForeignKey('warehouse_locations.id'), nullable=False)  # 关联库位
    batch_no = db.Column(db.String(32))  # 批次号
    quantity = db.Column(db.Integer, nullable=False)  # 不合格数量
    defect_reason = db.Column(db.String(64), nullable=False)  # 不合格原因
    inspection_order_id = db.Column(db.Integer, db.ForeignKey('inspection_orders.id'), nullable=False)  # 关联检验单
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    remark = db.Column(db.String(256))  # 备注

    # 关联商品
    product = db.relationship('Product')
    # 关联库位
    location = db.relationship('WarehouseLocation')
    # 关联检验单
    inspection_order = db.relationship('InspectionOrder')

    def __repr__(self):
        product = self.product.name if self.product else '未知商品'
        return f'<DefectiveProduct {product} - {self.quantity}>'


class InspectionOrder(db.Model):
    __tablename__ = 'inspection_orders'
    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(32), unique=True, nullable=False)    # 检验单号（自动生成）
    purchase_order_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'), nullable=False)  # 关联采购单
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'))   # 关联供应商
    delivery_order_no = db.Column(db.String(32))    # 送货单号
    operator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # 关联操作员
    inspection_date = db.Column(db.Date, default=datetime.utcnow, nullable=False)  # 检验日期
    total_quantity = db.Column(db.Integer, default=0)   # 检验总数量
    qualified_quantity = db.Column(db.Integer, default=0)   # 合格数量
    unqualified_quantity = db.Column(db.Integer, default=0)   # 不合格数量
    status = db.Column(db.String(16), default='pending', nullable=False)  # 状态(pending/completed)
    signature = db.Column(db.String(64))  # 仓库管理员签字
    remark = db.Column(db.String(256))  # 备注
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联检验明细
    items = db.relationship('InspectionItem', backref='inspection', lazy='dynamic', cascade='all, delete-orphan')

    # 关联操作员
    operator = db.relationship('User', backref='inspection_orders')

    # 关联采购单
    purchase_order = db.relationship('PurchaseOrder')

    # 关联供应商
    supplier = db.relationship('Supplier')

    def __repr__(self):
        return f'<InspectionOrder {self.order_no}>'


class InspectionItem(db.Model):
    __tablename__ = 'inspection_items'
    id = db.Column(db.Integer, primary_key=True)
    inspection_id = db.Column(db.Integer, db.ForeignKey('inspection_orders.id'), nullable=False)  # 关联检验单
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)   # 关联商品
    quantity = db.Column(db.Integer, nullable=False)   # 检验数量
    qualified_quantity = db.Column(db.Integer, default=0)   # 合格数量
    unqualified_quantity = db.Column(db.Integer, default=0)   # 不合格数量
    quality_status = db.Column(db.String(16), default='pending')  # 质检状态(pending/completed)
    defect_reason = db.Column(db.String(64))  # 不合格原因
    remark = db.Column(db.String(256))  # 备注

    # 关联商品
    product = db.relationship('Product')

    def __repr__(self):
        product = self.product.name if self.product else '未知商品'
        return f'<InspectionItem {product} - {self.quantity}>'