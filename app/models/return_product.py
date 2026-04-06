from datetime import datetime
from app import db


class ReturnOrder(db.Model):
    __tablename__ = 'return_orders'
    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(32), unique=True, nullable=False)
    return_date = db.Column(db.Date, default=datetime.utcnow, nullable=False)
    operator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(16), default='pending', nullable=False)
    total_amount = db.Column(db.Float, default=0.0)
    remark = db.Column(db.String(256))
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = db.relationship('ReturnItem', backref='return_order', lazy='dynamic', cascade='all, delete-orphan')
    operator = db.relationship('User', backref='return_orders')

    def __repr__(self):
        return f'<ReturnOrder {self.order_no}>'


class ReturnItem(db.Model):
    __tablename__ = 'return_items'
    id = db.Column(db.Integer, primary_key=True)
    return_order_id = db.Column(db.Integer, db.ForeignKey('return_orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('warehouse_locations.id'), nullable=False)
    inspection_order_id = db.Column(db.Integer, db.ForeignKey('inspection_orders.id'))
    batch_no = db.Column(db.String(32))
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    defect_reason = db.Column(db.String(64), nullable=False)
    remark = db.Column(db.String(256))
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product = db.relationship('Product')
    location = db.relationship('WarehouseLocation')
    inspection_order = db.relationship('InspectionOrder')

    def __repr__(self):
        product = self.product.name if self.product else '未知商品'
        return f'<ReturnItem {product} - {self.quantity}>'