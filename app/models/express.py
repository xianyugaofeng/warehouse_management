from datetime import datetime
from app import db


class Waybill(db.Model):
    """运单模型"""
    __tablename__ = 'waybills'
    id = db.Column(db.Integer, primary_key=True)
    waybill_no = db.Column(db.String(32), unique=True, nullable=False)  # 运单号/条形码
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)  # 关联商品
    location_id = db.Column(db.Integer, db.ForeignKey('warehouse_locations.id'))  # 关联库位
    status = db.Column(db.String(32), default='in_transit', nullable=False)  # 状态：in_transit(运输中), sent_to_station(发往站点), arrived_station(已到达站点), in_station(站点暂存), out_for_delivery(派送中), delivered(已送达), problem(问题件),滞留件(overnight)
    courier_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # 关联快递员
    create_time = db.Column(db.DateTime, default=datetime.utcnow)  # 创建时间
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # 更新时间
    
    # 关联
    product = db.relationship('Product')
    location = db.relationship('WarehouseLocation')
    courier = db.relationship('User')
    scan_records = db.relationship('ScanRecord', backref='waybill', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Waybill {self.waybill_no} - {self.status}>'


class ScanRecord(db.Model):
    """扫描记录模型"""
    __tablename__ = 'scan_records'
    id = db.Column(db.Integer, primary_key=True)
    waybill_id = db.Column(db.Integer, db.ForeignKey('waybills.id'), nullable=False)  # 关联运单
    scan_type = db.Column(db.String(32), nullable=False)  # 扫描类型：arrival(到件扫描), departure(派件扫描), delivery(签收扫描), problem(问题件扫描), return(回流扫描)
    operator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # 操作人
    location_id = db.Column(db.Integer, db.ForeignKey('warehouse_locations.id'), nullable=False)  # 扫描地点
    scan_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)  # 扫描时间
    batch_no = db.Column(db.String(32))  # 批次号（如卸车批次）
    remark = db.Column(db.String(256))  # 备注
    
    # 关联
    operator = db.relationship('User')
    location = db.relationship('WarehouseLocation')
    
    def __repr__(self):
        return f'<ScanRecord {self.waybill_id} - {self.scan_type}>'


class InventoryStatus(db.Model):
    """库存状态模型"""
    __tablename__ = 'inventory_statuses'
    id = db.Column(db.Integer, primary_key=True)
    location_id = db.Column(db.Integer, db.ForeignKey('warehouse_locations.id'), nullable=False)  # 关联库位
    waybill_id = db.Column(db.Integer, db.ForeignKey('waybills.id'), nullable=False)  # 关联运单
    status = db.Column(db.String(32), nullable=False)  # 库存状态：normal(正常待派), problem(问题件), overnight(滞留件)
    create_time = db.Column(db.DateTime, default=datetime.utcnow)  # 创建时间
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # 更新时间
    
    # 关联
    location = db.relationship('WarehouseLocation')
    waybill = db.relationship('Waybill')
    
    def __repr__(self):
        return f'<InventoryStatus {self.waybill_id} - {self.status}>'