from datetime import datetime
from app import db


class TransferOrder(db.Model):
    __tablename__ = 'transfer_orders'
    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(32), unique=True, nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    audit_status = db.Column(db.String(16), default='pending', nullable=False)
    auditor_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    audit_time = db.Column(db.DateTime)
    remark = db.Column(db.String(256))
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = db.relationship('TransferItem', backref='order', lazy='dynamic', cascade='all, delete-orphan')

    creator = db.relationship('User', foreign_keys=[creator_id], backref='transfer_orders_creator')
    auditor = db.relationship('User', foreign_keys=[auditor_id], backref='transfer_orders_auditor')

    def __repr__(self):
        return f'<TransferOrder {self.order_no}>'


class TransferItem(db.Model):
    __tablename__ = 'transfer_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('transfer_orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    source_location_id = db.Column(db.Integer, db.ForeignKey('warehouse_locations.id'), nullable=False)
    target_location_id = db.Column(db.Integer, db.ForeignKey('warehouse_locations.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

    product = db.relationship('Product')
    source_location = db.relationship('WarehouseLocation', foreign_keys=[source_location_id])
    target_location = db.relationship('WarehouseLocation', foreign_keys=[target_location_id])

    def __repr__(self):
        product = self.product.name if self.product else '未知商品'
        return f'<TransferItem {product} - {self.quantity}>'