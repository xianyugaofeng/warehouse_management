from datetime import datetime
from app import db


class InventoryCount(db.Model):
    """
    盘点单主表
    支持明盘与暗盘两种方式，自动创建库存快照，记录差异与冻结状态
    """
    __tablename__ = 'inventory_counts'
    id = db.Column(db.Integer, primary_key=True)
    count_no = db.Column(db.String(32), unique=True, nullable=False)  # 盘点单号
    count_type = db.Column(db.String(16), nullable=False)  # 盘点方式：明盘(open_count) / 暗盘(blind_count)
    scope_type = db.Column(db.String(16), nullable=False)  # 盘点范围类型：location(库位) / category(分类) / product(商品) / all(全部)
    scope_filter = db.Column(db.String(256))  # 范围筛选条件（JSON格式，如 {"location_ids": [1,2,3]}）
    plan_date = db.Column(db.Date, nullable=False)  # 计划盘点日期
    
    # 盘点状态流转
    status = db.Column(db.String(16), default='draft', nullable=False)  # draft(草稿) / in_progress(进行中) / completed(已完成) / closed(已关闭)
    
    # 统计数据
    total_items = db.Column(db.Integer, default=0)  # 盘点物品总数
    counted_items = db.Column(db.Integer, default=0)  # 已实盘物品总数
    variance_items = db.Column(db.Integer, default=0)  # 有差异物品总数
    
    # 操作员与审批信息
    operator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # 盘点人员
    approver_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # 审批人员
    approved_time = db.Column(db.DateTime)  # 审批时间
    
    # 备注与关联
    remark = db.Column(db.String(256))
    attached_variance_id = db.Column(db.Integer)  # 关联生成的盘盈/盘亏单ID（支持多个）
    
    create_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联关系
    operator = db.relationship('User', foreign_keys=[operator_id], backref='count_orders')
    approver = db.relationship('User', foreign_keys=[approver_id])
    details = db.relationship('InventoryCountDetail', backref='count', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<InventoryCount {self.count_no} - {self.count_type}>'


class InventoryCountDetail(db.Model):
    """
    盘点明细表 - 包含库存快照与实盘数据
    一条记录代表一个商品在一个库位的快照与实盘对比
    """
    __tablename__ = 'inventory_count_details'
    id = db.Column(db.Integer, primary_key=True)
    count_id = db.Column(db.Integer, db.ForeignKey('inventory_counts.id'), nullable=False)
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventories.id'), nullable=False)  # 关联库存记录
    
    # 关键业务字段
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('warehouse_locations.id'), nullable=False)
    batch_no = db.Column(db.String(32))  # 批次号
    
    # ====== 快照数据（创建盘点单时自动记录，之后不可改） ======
    snapshot_quantity = db.Column(db.Integer, nullable=False)  # 快照时物理库存数量
    snapshot_locked = db.Column(db.Integer, default=0)  # 快照时锁定数量
    snapshot_frozen = db.Column(db.Integer, default=0)  # 快照时冻结数量
    snapshot_available = db.Column(db.Integer, default=0)  # 快照时可用数量（计算字段）
    snapshot_time = db.Column(db.DateTime, default=datetime.utcnow)  # 快照时间
    
    # ====== 实盘数据（可选更新，直到盘点完成） ======
    counted_quantity = db.Column(db.Integer)  # 实盘数量（nullable，允许未录入）
    counted_time = db.Column(db.DateTime)  # 实盘时间
    
    # ====== 差异计算（自动计算，可重新计算） ======
    variance_quantity = db.Column(db.Integer)  # 差异数量（counted - snapshot）
    variance_type = db.Column(db.String(16))  # 差异类型：gain(盘盈) / loss(盘亏) / none(无差异)
    variance_reason = db.Column(db.String(256))  # 差异原因（可选）
    
    # 冻结与审批状态
    frozen_qty = db.Column(db.Integer, default=0)  # 因差异冻结的数量（在VarianceDocument审核前冻结）
    freeze_record_id = db.Column(db.Integer, db.ForeignKey('inventory_freeze_records.id'))  # 关联冻结记录
    variance_doc_id = db.Column(db.Integer, db.ForeignKey('variance_documents.id'))  # 关联差异单
    
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联关系
    inventory = db.relationship('Inventory')
    product = db.relationship('Product')
    location = db.relationship('WarehouseLocation')
    variance_doc = db.relationship('VarianceDocument', backref='count_details')
    freeze_record = db.relationship('InventoryFreezeRecord', backref='count_detail')
    
    __table_args__ = (
        db.UniqueConstraint('count_id', 'inventory_id', name='_count_inventory_uc'),
    )
    
    def __repr__(self):
        return f'<InventoryCountDetail {self.count_id} - {self.product_id}>'
    
    def calculate_variance(self):
        """
        计算差异（调用此方法后自动更新variance_quantity、variance_type）
        """
        if self.counted_quantity is None:
            self.variance_quantity = None
            self.variance_type = None
            return
        
        self.variance_quantity = self.counted_quantity - self.snapshot_quantity
        
        # 更新盘点明细的差异状态
        if self.variance_quantity > 0:
            self.variance_type = 'gain'  # 盘盈
        elif self.variance_quantity < 0:
            self.variance_type = 'loss'  # 盘亏
        else:
            self.variance_type = 'none'  # 无差异


class VarianceDocument(db.Model):
    """
    盘盈/盘亏单 - 在盘点完成后根据差异自动生成，需经审核才能生效
    """
    __tablename__ = 'variance_documents'
    id = db.Column(db.Integer, primary_key=True)
    variance_no = db.Column(db.String(32), unique=True, nullable=False)  # 差异单号
    count_id = db.Column(db.Integer, db.ForeignKey('inventory_counts.id'), nullable=False)
    
    # 差异类型与状态
    variance_type = db.Column(db.String(16), nullable=False)  # gain(盘盈) / loss(盘亏)
    status = db.Column(db.String(16), default='pending', nullable=False)  # pending(待审) / approved(已通过) / rejected(已驳回)
    
    # 合并后的统计数据
    total_variance_qty = db.Column(db.Integer, nullable=False)  # 总差异数量（和）
    total_items = db.Column(db.Integer, nullable=False)  # 明细行数
    
    # 审批信息
    approver_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_time = db.Column(db.DateTime)
    force_approved = db.Column(db.Boolean, default=False)  # 是否强制通过（负可用时）
    rejection_reason = db.Column(db.String(256))  # 驳回原因
    
    # 库存调整记录
    adjust_log_id = db.Column(db.Integer, db.ForeignKey('inventory_change_logs.id'))  # 关联库存变更日志
    
    remark = db.Column(db.String(256))
    create_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联关系
    count = db.relationship('InventoryCount')
    approver = db.relationship('User', backref='approved_variances')
    details = db.relationship('VarianceDetail', backref='variance_doc', cascade='all, delete-orphan')
    adjust_log = db.relationship('InventoryChangeLog', backref='variance_doc')
    
    def __repr__(self):
        return f'<VarianceDocument {self.variance_no} - {self.variance_type}>'


class VarianceDetail(db.Model):
    """
    盘盈/盘亏明细 - VarianceDocument 的明细行，存储单个商品的差异信息
    """
    __tablename__ = 'variance_details'
    id = db.Column(db.Integer, primary_key=True)
    variance_doc_id = db.Column(db.Integer, db.ForeignKey('variance_documents.id'), nullable=False)
    count_detail_id = db.Column(db.Integer, db.ForeignKey('inventory_count_details.id'), nullable=False)
    
    # 商品与库位信息
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('warehouse_locations.id'), nullable=False)
    batch_no = db.Column(db.String(32))
    
    # 差异细节
    snapshot_quantity = db.Column(db.Integer, nullable=False)  # 快照数量
    counted_quantity = db.Column(db.Integer, nullable=False)  # 实盘数量
    variance_quantity = db.Column(db.Integer, nullable=False)  # 差异数量（counted - snapshot）
    
    # 审计信息（冻结的数量，差异原因等）
    snapshot_locked = db.Column(db.Integer, default=0)  # 快照时锁定数量
    snapshot_frozen = db.Column(db.Integer, default=0)  # 快照时冻结数量
    variance_reason = db.Column(db.String(256))  # 差异原因
    
    # 处理状态
    processed = db.Column(db.Boolean, default=False)  # 是否已处理（审核通过后置为True）
    processed_time = db.Column(db.DateTime)
    
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关联关系
    product = db.relationship('Product')
    location = db.relationship('WarehouseLocation')
    count_detail = db.relationship('InventoryCountDetail')
    
    def __repr__(self):
        return f'<VarianceDetail {self.variance_doc_id} - {self.product_id}>'


class InventoryFreezeRecord(db.Model):
    """
    库存冻结记录 - 记录因盘点差异而冻结的库存
    在盘盈/盘亏单生成时创建冻结记录（防止其他业务误用）
    在审核通过时解冻并实际调整物理库存
    """
    __tablename__ = 'inventory_freeze_records'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('warehouse_locations.id'), nullable=False)
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventories.id'), nullable=False)
    
    # 冻结信息
    freeze_qty = db.Column(db.Integer, nullable=False)  # 冻结数量（绝对值）
    freeze_type = db.Column(db.String(16), nullable=False)  # 冻结类型：count_gain(盘盈) / count_loss(盘亏)
    reason = db.Column(db.String(256))  # 原因（如：'Count Order #CO20250319001'）
    variance_doc_id = db.Column(db.Integer, db.ForeignKey('variance_documents.id'))  # 关联差异单
    count_id = db.Column(db.Integer, db.ForeignKey('inventory_counts.id'))  # 关联盘点单
    
    # 冻结状态
    status = db.Column(db.String(16), default='frozen', nullable=False)  # frozen(已冻结) / released(已释放)
    
    frozen_time = db.Column(db.DateTime, default=datetime.utcnow)
    released_time = db.Column(db.DateTime)  # 解冻时间（审核通过或驳回时）
    released_reason = db.Column(db.String(256))  # 解冻原因（'Variance approved' / 'Variance rejected'）
    
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联关系
    product = db.relationship('Product')
    location = db.relationship('WarehouseLocation')
    inventory = db.relationship('Inventory')
    variance_doc = db.relationship('VarianceDocument')
    count = db.relationship('InventoryCount')
    
    def __repr__(self):
        return f'<InventoryFreezeRecord {self.freeze_qty} - {self.status}>'
