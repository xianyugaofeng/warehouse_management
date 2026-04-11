from datetime import datetime
from app import db


class CheckInventory(db.Model):
    __tablename__ = 'check_inventories'
    id = db.Column(db.Integer, primary_key=True)
    check_no = db.Column(db.String(32), unique=True, nullable=False)
    check_status = db.Column(db.String(16), default='pending', nullable=False)
    checker_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filter_product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    filter_category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    filter_location_id = db.Column(db.Integer, db.ForeignKey('warehouse_locations.id'))
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    remark = db.Column(db.String(256))
    frozen_status = db.Column(db.Boolean, default=False)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = db.relationship('CheckInventoryItem', backref='check_inventory', lazy='dynamic', cascade='all, delete-orphan')
    results = db.relationship('CheckInventoryResult', backref='check_inventory', lazy='dynamic', cascade='all, delete-orphan')

    checker = db.relationship('User', backref='check_inventories')
    filter_product = db.relationship('Product')
    filter_category = db.relationship('Category')
    filter_location = db.relationship('WarehouseLocation')

    def __repr__(self):
        return f'<CheckInventory {self.check_no}>'


class CheckInventoryItem(db.Model):
    __tablename__ = 'check_inventory_items'
    id = db.Column(db.Integer, primary_key=True)
    check_inventory_id = db.Column(db.Integer, db.ForeignKey('check_inventories.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('warehouse_locations.id'), nullable=False)
    book_quantity = db.Column(db.Integer, default=0, nullable=False)

    product = db.relationship('Product')
    location = db.relationship('WarehouseLocation')
    results = db.relationship('CheckInventoryResult', backref='item', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        product = self.product.name if self.product else '未知商品'
        return f'<CheckInventoryItem {product} - 账面数量: {self.book_quantity}>'


class CheckInventoryResult(db.Model):
    __tablename__ = 'check_inventory_results'
    id = db.Column(db.Integer, primary_key=True)
    check_inventory_id = db.Column(db.Integer, db.ForeignKey('check_inventories.id'), nullable=False)
    check_item_id = db.Column(db.Integer, db.ForeignKey('check_inventory_items.id'), nullable=False)
    check_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    book_quantity = db.Column(db.Integer, nullable=False)
    actual_quantity = db.Column(db.Integer, nullable=True)  # 修改为可空，null表示未盘点
    diff_quantity = db.Column(db.Integer, nullable=False)
    check_result = db.Column(db.String(16), nullable=False)

    check_item = db.relationship('CheckInventoryItem', backref='item')  # 统一关联关系命名，与视图中使用一致

    def __repr__(self):
        return f'<CheckInventoryResult 差异: {self.diff_quantity} - {self.check_result}>'