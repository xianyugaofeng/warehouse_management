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
    quantity = db.Column(db.Integer, default=0, nullable=False)  # 物理库存数量
    locked_quantity = db.Column(db.Integer, default=0, nullable=False)  # 锁定数量
    frozen_quantity = db.Column(db.Integer, default=0, nullable=False)  # 冻结数量
    batch_no = db.Column(db.String(32))  # 批次号
    production_date = db.Column(db.Date)  # 生产日期
    expire_date = db.Column(db.Date)  # 过期日期
    supplier_batch_no = db.Column(db.String(32))  # 供应商批次号
    owner_id = db.Column(db.Integer)  # 所有者ID，用于多货主仓库模式
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
        return f'<Inventory {product} - {self.location.code} - 物理库存:{self.quantity} - 可用:{self.available_quantity}>'
    
    # 计算可用数量
    @property
    def available_quantity(self):
        """可用数量 = 物理库存 - 锁定数量 - 冻结数量"""
        return max(0, self.quantity - self.locked_quantity - self.frozen_quantity)

    # 检查是否低于预警阈值
    def is_warning(self):
        if not self.product or self.product.warning_stock is None:
            return False
        return self.available_quantity <= self.product.warning_stock
    
    # 锁定库存
    @log_inventory_change('lock')
    def lock_quantity(self, amount):
        """锁定库存数量"""
        if amount > self.available_quantity:
            raise ValueError('锁定数量不能超过可用数量')
        self.locked_quantity += amount
        return self
    
    # 解锁库存
    @log_inventory_change('unlock')
    def unlock_quantity(self, amount):
        """解锁库存数量"""
        if amount > self.locked_quantity:
            raise ValueError('解锁数量不能超过锁定数量')
        self.locked_quantity -= amount
        return self
    
    # 冻结库存
    @log_inventory_change('freeze')
    def freeze_quantity(self, amount):
        """冻结库存数量"""
        if amount > self.available_quantity:
            raise ValueError('冻结数量不能超过可用数量')
        self.frozen_quantity += amount
        return self
    
    # 解冻库存
    @log_inventory_change('unfreeze')
    def unfreeze_quantity(self, amount):
        """解冻库存数量"""
        if amount > self.frozen_quantity:
            raise ValueError('解冻数量不能超过冻结数量')
        self.frozen_quantity -= amount
        return self
    
    # 增加物理库存
    @log_inventory_change('inbound')
    def increase_quantity(self, amount):
        """增加物理库存数量"""
        if amount < 0:
            raise ValueError('增加数量不能为负数')
        self.quantity += amount
        return self
    
    # 减少物理库存
    @log_inventory_change('outbound')
    def decrease_quantity(self, amount):
        """减少物理库存数量"""
        if amount < 0:
            raise ValueError('减少数量不能为负数')
        if amount > (self.quantity - self.frozen_quantity):
            raise ValueError('减少数量不能超过非冻结库存数量')
        self.quantity -= amount
        # 如果锁定数量大于当前可用数量，自动调整锁定数量
        if self.locked_quantity > self.available_quantity:
            self.locked_quantity = self.available_quantity
        return self
    
    # 调整库存（用于盘点）
    @log_inventory_change('adjustment')
    def adjust_quantity(self, new_quantity, reason='盘点调整'):
        """调整库存数量（用于盘点）"""
        if new_quantity < 0:
            raise ValueError('库存数量不能为负数')
        self.quantity = new_quantity
        # 自动调整锁定和冻结数量
        if self.locked_quantity > self.available_quantity:
            self.locked_quantity = self.available_quantity
        return self
    
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


class InventoryChangeLog(db.Model):
    """库存变更日志"""
    __tablename__ = 'inventory_change_logs'
    id = db.Column(db.Integer, primary_key=True)
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventories.id'), nullable=False)  # 关联库存
    change_type = db.Column(db.String(16), nullable=False)  # 变更类型: inbound(入库), outbound(出库), lock(锁定), unlock(解锁), freeze(冻结), unfreeze(解冻), adjustment(调整)
    quantity_before = db.Column(db.Integer, nullable=False)  # 变更前数量
    quantity_after = db.Column(db.Integer, nullable=False)  # 变更后数量
    locked_quantity_before = db.Column(db.Integer, nullable=False)  # 变更前锁定数量
    locked_quantity_after = db.Column(db.Integer, nullable=False)  # 变更后锁定数量
    frozen_quantity_before = db.Column(db.Integer, nullable=False)  # 变更前冻结数量
    frozen_quantity_after = db.Column(db.Integer, nullable=False)  # 变更后冻结数量
    operator = db.Column(db.String(64))  # 操作人
    reason = db.Column(db.String(256))  # 变更原因
    reference_id = db.Column(db.Integer)  # 关联业务单据ID
    reference_type = db.Column(db.String(32))  # 关联业务单据类型
    create_time = db.Column(db.DateTime, default=datetime.utcnow)  # 创建时间
    
    # 关联库存
    inventory = db.relationship('Inventory', backref=db.backref('change_logs', lazy='dynamic'))
    
    def __repr__(self):
        return f'<InventoryChangeLog {self.change_type} - {self.inventory_id}>'


# 库存变更日志记录装饰器
def log_inventory_change(change_type, operator='system', reason='', reference_id=None, reference_type=None):
    """记录库存变更日志的装饰器"""
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            # 记录变更前的状态
            quantity_before = self.quantity
            locked_quantity_before = self.locked_quantity
            frozen_quantity_before = self.frozen_quantity
            
            # 执行原函数
            result = func(self, *args, **kwargs)
            
            # 记录变更后的状态
            quantity_after = self.quantity
            locked_quantity_after = self.locked_quantity
            frozen_quantity_after = self.frozen_quantity
            
            # 创建变更日志
            log = InventoryChangeLog(
                inventory_id=self.id,
                change_type=change_type,
                quantity_before=quantity_before,
                quantity_after=quantity_after,
                locked_quantity_before=locked_quantity_before,
                locked_quantity_after=locked_quantity_after,
                frozen_quantity_before=frozen_quantity_before,
                frozen_quantity_after=frozen_quantity_after,
                operator=operator,
                reason=reason,
                reference_id=reference_id,
                reference_type=reference_type
            )
            db.session.add(log)
            
            return result
        return wrapper
    return decorator
