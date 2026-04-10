from datetime import datetime
from app import db


class WarehouseLocation(db.Model):
    __tablename__ = 'warehouse_locations'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, nullable=False)  # 库位编码(如A1-01-02)
    name = db.Column(db.String(64), nullable=False)  # 库位名称
    area = db.Column(db.String(32))  # 所属区域
    status = db.Column(db.Boolean, default=True)  # 状态(启用/禁用)
    remark = db.Column(db.String(256))  # 备注
    inventories = db.relationship('Inventory', backref='location', lazy='dynamic')  # 关联库存

    # 通过warehouselocation.inventories获取该位置的所有库存(动态加载)
    # 通过inventory.location获取属于该库存的所有位置(立即加载)

    def __repr__(self):
        return f'<WarehouseLocation {self.code}>'


class Inventory(db.Model):
    # product_id相同的商品可以有不同的库位和不同的批次
    __tablename__ = 'inventories'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)  # 关联商品
    location_id = db.Column(db.Integer, db.ForeignKey('warehouse_locations.id'), nullable=False)  # 关联库位
    quantity = db.Column(db.Integer, default=0, nullable=False)  # 库存数量
    batch_no = db.Column(db.String(32))  # 批次号
    production_date = db.Column(db.Date)  # 生产日期
    expire_date = db.Column(db.Date)  # 过期日期
    stock_status = db.Column(db.String(16), default='normal', nullable=False)  # 库存状态(normal正常/damaged损坏/frozen冻结)
    status_remark = db.Column(db.String(256))  # 状态备注（损坏原因、冻结原因）
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # 最后更新时间
    # 关联商品
    product = db.relationship('Product')

    # 联合唯一约束（同一商品同一库位同一批次唯一）
    __table_args__ = (
        db.UniqueConstraint('product_id', 'location_id', 'batch_no', name='_product_location_batch_uc'),
    )

    def __repr__(self):
        product = self.product.name if self.product else '未知商品'
        return f'<Inventory {product} - {self.location.code} - {self.quantity}>'

    # 检查是否低于预警阈值
    def is_warning(self):
        if not self.product or self.product.warning_stock is None:
            return False
        return self.quantity <= self.product.warning_stock

    @staticmethod
    def check_location_product_conflict(location_id, product_id, exclude_batch_no=None):
        """
        检查库位是否已有其他商品
        :param location_id: 库位ID
        :param product_id: 商品ID
        :param exclude_batch_no: 排除的批次号（用于更新现有库存时排除自己）
        :return: 如果有冲突返回冲突的商品名称，否则返回 None
        """
        query = Inventory.query.filter_by(location_id=location_id)
        if exclude_batch_no:
            query = query.filter(Inventory.batch_no != exclude_batch_no)
        
        existing = query.filter(Inventory.product_id != product_id).first()
        if existing:
            return existing.product.name if existing.product else '未知商品'
        return None
