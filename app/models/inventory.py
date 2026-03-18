from datetime import datetime
import logging
from app import db

# 配置日志记录器
logger = logging.getLogger(__name__)


class WarehouseLocation(db.Model):
    __tablename__ = 'warehouse_locations'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, nullable=False)  # 库位编码(如A1-01-02)
    name = db.Column(db.String(64), nullable=False)  # 库位名称
    area = db.Column(db.String(32))  # 所属区域
    location_type = db.Column(db.String(16), default='normal')  # 库位类型: normal(正常), inspection(待检), reject(不合格品)
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
    defect_reason = db.Column(db.String(64))  # 不合格原因
    inspection_order_id = db.Column(db.Integer, db.ForeignKey('inspection_orders.id'))  # 关联检验单
    create_time = db.Column(db.DateTime, default=datetime.utcnow)  # 创建时间
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # 最后更新时间
    # 关联商品
    product = db.relationship('Product')
    # 关联检验单
    inspection_order = db.relationship('InspectionOrder')

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
    
    # 获取库存状态
    @property
    def status(self):
        """根据库位类型自动确定库存状态
        
        状态对应关系：
        - waiting: 等待（对应入库管理模块的"待上架"状态）
        - normal: 正常（已上架的正常库存）
        - pending_inspection: 待检
        - defective: 不合格
        """
        if not self.location:
            logger.warning(f'库存记录 {self.id} 没有关联库位，返回unknown状态')
            return 'unknown'
        
        location_type = self.location.location_type
        status_map = {
            'waiting': 'waiting',  # 等待/待上架 - 与入库管理模块的"待上架"状态一致
            'normal': 'normal',  # 正常库存
            'inspection': 'pending_inspection',  # 待检
            'reject': 'defective',  # 不合格
            'pending': 'pending'  # 待处理
        }
        
        status = status_map.get(location_type, 'unknown')
        logger.debug(f'库存记录 {self.id} (商品:{self.product_id}, 库位:{self.location_id}, 类型:{location_type}) 状态: {status}')
        return status
    
    # 检查是否为不合格商品
    def is_defective(self):
        return self.status == 'defective'
    
    # 验证检验单关联
    def validate_inspection_order(self):
        """验证检验单关联：只有不合格商品库存需要关联检验单"""
        if self.is_defective():
            # 不合格商品必须关联检验单
            if not self.inspection_order_id:
                raise ValueError('不合格商品库存必须关联检验单')
            if not self.defect_reason:
                raise ValueError('不合格商品库存必须填写不合格原因')
        else:
            # 正常库存和待检库存不需要关联检验单
            # 如果有关联检验单，则清除（可选，根据业务需求）
            pass
        return True
