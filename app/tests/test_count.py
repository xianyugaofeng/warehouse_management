"""
库存盘点模块单元测试
测试范围：快照创建、差异计算、冻结机制、审核流程、合理性校验
"""
import unittest
import json
from datetime import datetime, date
from app import create_app, db
from app.models import (
    User, Role, Permission, Product, Category, Supplier, WarehouseLocation,
    Inventory, InventoryChangeLog, InventoryCount, InventoryCountDetail,
    VarianceDocument, VarianceDetail, InventoryFreezeRecord
)


class InventoryCountTestCase(unittest.TestCase):
    """库存盘点测试用例"""
    
    def setUp(self):
        """测试初始化"""
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        # 创建测试数据
        self._create_test_data()
    
    def tearDown(self):
        """测试清理"""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    def _create_test_data(self):
        """创建测试数据"""
        # 创建用户与权限
        user_role = Role(name='warehouse_manager', desc='仓库管理员')
        perm = Permission(name='inventory_manage', desc='库存管理')
        user_role.permissions.append(perm)
        
        user = User(username='testuser', real_name='测试员')
        user.set_password('password')
        user.roles.append(user_role)
        db.session.add_all([user_role, perm, user])
        
        # 创建分类与供应商
        category = Category(name='电子产品', desc='测试分类')
        supplier = Supplier(name='供应商A', contact_person='张三')
        
        # 创建商品
        product1 = Product(code='P001', name='商品A', spec='10x10', unit='件', category=category, supplier=supplier)
        product2 = Product(code='P002', name='商品B', spec='20x20', unit='件', category=category, supplier=supplier)
        product3 = Product(code='P003', name='商品C', spec='30x30', unit='件', category=category, supplier=supplier)
        
        # 创建库位
        location1 = WarehouseLocation(code='A-01-01', name='库位1', area='A区', location_type='normal')
        location2 = WarehouseLocation(code='A-01-02', name='库位2', area='A区', location_type='normal')
        location3 = WarehouseLocation(code='A-01-03', name='库位3', area='A区', location_type='normal')
        
        # 创建库存
        inv1 = Inventory(product=product1, location=location1, quantity=100,
                        locked_quantity=10, frozen_quantity=5, batch_no='B001')
        inv2 = Inventory(product=product2, location=location2, quantity=50,
                        locked_quantity=5, frozen_quantity=2, batch_no='B002')
        inv3 = Inventory(product=product3, location=location3, quantity=30,
                        locked_quantity=0, frozen_quantity=0, batch_no='B003')
        
        db.session.add_all([
            category, supplier, product1, product2, product3,
            location1, location2, location3,
            inv1, inv2, inv3
        ])
        db.session.commit()
        
        # 保存到实例变量便于测试使用
        self.user = user
        self.product1 = product1
        self.product2 = product2
        self.product3 = product3
        self.location1 = location1
        self.location2 = location2
        self.location3 = location3
        self.inv1 = inv1
        self.inv2 = inv2
        self.inv3 = inv3
    
    # ========== 快照创建测试 ==========
    
    def test_create_count_and_snapshot(self):
        """测试：创建盘点单并生成快照"""
        count = InventoryCount(
            count_no='CT20250319001',
            count_type='open_count',
            scope_type='all',
            scope_filter=json.dumps({}),
            plan_date=date.today(),
            operator=self.user,
            status='draft'
        )
        db.session.add(count)
        db.session.flush()
        
        # 生成快照
        from app.views.count_manage import _create_snapshot
        _create_snapshot(count, 'all', {})
        
        db.session.commit()
        
        # 验证快照
        self.assertEqual(count.total_items, 3)
        details = count.details.all()
        self.assertEqual(len(details), 3)
        
        # 验证第一个商品快照
        detail1 = count.details.filter_by(inventory_id=self.inv1.id).first()
        self.assertIsNotNone(detail1)
        self.assertEqual(detail1.snapshot_quantity, 100)
        self.assertEqual(detail1.snapshot_locked, 10)
        self.assertEqual(detail1.snapshot_frozen, 5)
        self.assertEqual(detail1.snapshot_available, 85)  # 100 - 10 - 5
    
    def test_create_count_with_location_filter(self):
        """测试：按库位筛选创建盘点单"""
        count = InventoryCount(
            count_no='CT20250319002',
            count_type='open_count',
            scope_type='location',
            scope_filter=json.dumps({'location_ids': [self.location1.id]}),
            plan_date=date.today(),
            operator=self.user,
            status='draft'
        )
        db.session.add(count)
        db.session.flush()
        
        from app.views.count_manage import _create_snapshot
        _create_snapshot(count, 'location', {'location_ids': [self.location1.id]})
        
        db.session.commit()
        
        # 只应包含location1的库存
        self.assertEqual(count.total_items, 1)
        detail = count.details.first()
        self.assertEqual(detail.product_id, self.product1.id)
    
    # ========== 差异计算测试 ==========
    
    def test_variance_calculation_gain(self):
        """测试：盘盈差异计算"""
        count = InventoryCount(
            count_no='CT20250319003',
            count_type='open_count',
            scope_type='all',
            scope_filter=json.dumps({}),
            plan_date=date.today(),
            operator=self.user,
            status='draft'
        )
        db.session.add(count)
        db.session.flush()
        
        from app.views.count_manage import _create_snapshot
        _create_snapshot(count, 'all', {})
        db.session.commit()
        
        # 获取盘点明细
        detail = count.details.filter_by(inventory_id=self.inv1.id).first()
        
        # 实盘数量大于快照数量（盘盈）
        detail.counted_quantity = 105
        detail.calculate_variance()
        
        self.assertEqual(detail.variance_quantity, 5)
        self.assertEqual(detail.variance_type, 'gain')
    
    def test_variance_calculation_loss(self):
        """测试：盘亏差异计算"""
        count = InventoryCount(
            count_no='CT20250319004',
            count_type='open_count',
            scope_type='all',
            scope_filter=json.dumps({}),
            plan_date=date.today(),
            operator=self.user,
            status='draft'
        )
        db.session.add(count)
        db.session.flush()
        
        from app.views.count_manage import _create_snapshot
        _create_snapshot(count, 'all', {})
        db.session.commit()
        
        # 获取盘点明细
        detail = count.details.filter_by(inventory_id=self.inv1.id).first()
        
        # 实盘数量小于快照数量（盘亏）
        detail.counted_quantity = 95
        detail.calculate_variance()
        
        self.assertEqual(detail.variance_quantity, -5)
        self.assertEqual(detail.variance_type, 'loss')
    
    def test_variance_calculation_none(self):
        """测试：无差异"""
        count = InventoryCount(
            count_no='CT20250319005',
            count_type='open_count',
            scope_type='all',
            scope_filter=json.dumps({}),
            plan_date=date.today(),
            operator=self.user,
            status='draft'
        )
        db.session.add(count)
        db.session.flush()
        
        from app.views.count_manage import _create_snapshot
        _create_snapshot(count, 'all', {})
        db.session.commit()
        
        detail = count.details.filter_by(inventory_id=self.inv1.id).first()
        
        # 实盘数量等于快照数量
        detail.counted_quantity = 100
        detail.calculate_variance()
        
        self.assertEqual(detail.variance_quantity, 0)
        self.assertEqual(detail.variance_type, 'none')
    
    # ========== 冻结机制测试 ==========
    
    def test_freeze_inventory_on_variance_generation(self):
        """测试：生成差异单时冻结库存"""
        # 创建盘点单和快照
        count = InventoryCount(
            count_no='CT20250319006',
            count_type='open_count',
            scope_type='all',
            scope_filter=json.dumps({}),
            plan_date=date.today(),
            operator=self.user,
            status='draft'
        )
        db.session.add(count)
        db.session.flush()
        
        from app.views.count_manage import _create_snapshot
        _create_snapshot(count, 'all', {})
        db.session.commit()
        
        # 录入实盘数量（盘亏5）
        detail1 = count.details.filter_by(inventory_id=self.inv1.id).first()
        detail1.counted_quantity = 95
        detail1.calculate_variance()
        
        detail2 = count.details.filter_by(inventory_id=self.inv2.id).first()
        detail2.counted_quantity = 50
        detail2.calculate_variance()
        
        detail3 = count.details.filter_by(inventory_id=self.inv3.id).first()
        detail3.counted_quantity = 35  # 盘盈5
        detail3.calculate_variance()
        
        db.session.commit()
        
        # 生成差异单
        from app.views.count_manage import _create_variance_document
        
        losses = [detail1]
        gains = [detail3]
        
        _create_variance_document(count, 'loss', losses)
        _create_variance_document(count, 'gain', gains)
        
        db.session.commit()
        
        # 验证冻结
        self.inv1 = db.session.merge(self.inv1)
        self.inv3 = db.session.merge(self.inv3)
        
        # inv1（盘亏5）应该冻结5
        self.assertEqual(self.inv1.frozen_quantity, 5 + 5)  # 原有5 + 新增5
        freeze_record1 = InventoryFreezeRecord.query.filter_by(inventory_id=self.inv1.id, status='frozen').first()
        self.assertIsNotNone(freeze_record1)
        self.assertEqual(freeze_record1.freeze_qty, 5)
        
        # inv3（盘盈5）应该冻结5
        self.assertEqual(self.inv3.frozen_quantity, 5)
        freeze_record3 = InventoryFreezeRecord.query.filter_by(inventory_id=self.inv3.id, status='frozen').first()
        self.assertIsNotNone(freeze_record3)
        self.assertEqual(freeze_record3.freeze_qty, 5)
    
    # ========== 审核流程测试 ==========
    
    def test_approve_variance_gain(self):
        """测试：审核通过盘盈单"""
        # 准备数据
        count = InventoryCount(
            count_no='CT20250319007',
            count_type='open_count',
            scope_type='all',
            scope_filter=json.dumps({}),
            plan_date=date.today(),
            operator=self.user,
            status='draft'
        )
        db.session.add(count)
        db.session.flush()
        
        from app.views.count_manage import _create_snapshot, _create_variance_document
        _create_snapshot(count, 'all', {})
        db.session.commit()
        
        # 盘盈5件
        detail = count.details.filter_by(inventory_id=self.inv1.id).first()
        detail.counted_quantity = 105
        detail.calculate_variance()
        db.session.commit()
        
        # 生成差异单
        gains = [detail]
        _create_variance_document(count, 'gain', gains)
        db.session.commit()
        
        variance = VarianceDocument.query.filter_by(count_id=count.id, variance_type='gain').first()
        
        # 审核通过
        from app.views.count_manage import _approve_variance_internal
        original_qty = self.inv1.quantity
        _approve_variance_internal(variance, False, self.user.id)
        db.session.commit()
        
        # 验证库存调整
        self.inv1 = db.session.merge(self.inv1)
        self.assertEqual(self.inv1.quantity, original_qty + 5)  # 增加5
        self.assertEqual(variance.status, 'approved')
    
    def test_approve_variance_loss(self):
        """测试：审核通过盘亏单"""
        count = InventoryCount(
            count_no='CT20250319008',
            count_type='open_count',
            scope_type='all',
            scope_filter=json.dumps({}),
            plan_date=date.today(),
            operator=self.user,
            status='draft'
        )
        db.session.add(count)
        db.session.flush()
        
        from app.views.count_manage import _create_snapshot, _create_variance_document
        _create_snapshot(count, 'all', {})
        db.session.commit()
        
        # 盘亏5件
        detail = count.details.filter_by(inventory_id=self.inv1.id).first()
        detail.counted_quantity = 95
        detail.calculate_variance()
        db.session.commit()
        
        # 生成差异单
        losses = [detail]
        _create_variance_document(count, 'loss', losses)
        db.session.commit()
        
        variance = VarianceDocument.query.filter_by(count_id=count.id, variance_type='loss').first()
        
        # 审核通过
        from app.views.count_manage import _approve_variance_internal
        original_qty = self.inv1.quantity
        original_frozen = self.inv1.frozen_quantity
        _approve_variance_internal(variance, False, self.user.id)
        db.session.commit()
        
        # 验证库存调整
        self.inv1 = db.session.merge(self.inv1)
        self.assertEqual(self.inv1.quantity, original_qty - 5)  # 减少5
        self.assertEqual(self.inv1.frozen_quantity, original_frozen - 5)  # 解冻5
        self.assertEqual(variance.status, 'approved')
    
    def test_reject_variance(self):
        """测试：驳回差异单"""
        count = InventoryCount(
            count_no='CT20250319009',
            count_type='open_count',
            scope_type='all',
            scope_filter=json.dumps({}),
            plan_date=date.today(),
            operator=self.user,
            status='draft'
        )
        db.session.add(count)
        db.session.flush()
        
        from app.views.count_manage import _create_snapshot, _create_variance_document
        _create_snapshot(count, 'all', {})
        db.session.commit()
        
        detail = count.details.filter_by(inventory_id=self.inv1.id).first()
        detail.counted_quantity = 95
        detail.calculate_variance()
        db.session.commit()
        
        losses = [detail]
        _create_variance_document(count, 'loss', losses)
        db.session.commit()
        
        variance = VarianceDocument.query.filter_by(count_id=count.id, variance_type='loss').first()
        original_frozen = self.inv1.frozen_quantity
        
        # 驳回
        variance.status = 'rejected'
        variance.rejection_reason = '数据错误'
        variance.approver = self.user
        
        # 解冻
        freeze_record = InventoryFreezeRecord.query.filter_by(variance_doc_id=variance.id).first()
        if freeze_record:
            freeze_record.status = 'released'
            self.inv1.frozen_quantity -= freeze_record.freeze_qty
        
        db.session.commit()
        
        # 验证冻结已解除
        self.inv1 = db.session.merge(self.inv1)
        self.assertEqual(self.inv1.frozen_quantity, original_frozen - 5)
        self.assertEqual(variance.status, 'rejected')
    
    # ========== 合理性校验测试 ==========
    
    def test_negative_available_warning(self):
        """测试：负可用数量警告"""
        # 创建一个库存：quantity=30, locked=20, frozen=5
        # available = 30 - 20 - 5 = 5
        # 如果盘亏超过5，调整后会出现负可用
        
        count = InventoryCount(
            count_no='CT20250319010',
            count_type='open_count',
            scope_type='all',
            scope_filter=json.dumps({}),
            plan_date=date.today(),
            operator=self.user,
            status='draft'
        )
        db.session.add(count)
        db.session.flush()
        
        # 创建一个特殊库存用于测试
        # 可用库存=40-20-5=15，足够冻结10
        product = Product(code='P004', name='特殊商品', unit='件')
        location = WarehouseLocation(code='B-01-01', name='库位B', area='B区', location_type='normal')
        inv_special = Inventory(
            product=product, location=location,
            quantity=40, locked_quantity=20, frozen_quantity=5, batch_no='B004'
        )
        db.session.add_all([product, location, inv_special])
        db.session.flush()
        
        from app.views.count_manage import _create_snapshot
        _create_snapshot(count, 'all', {})
        db.session.commit()
        
        detail = count.details.filter_by(inventory_id=inv_special.id).first()
        
        # 盘亏10
        detail.counted_quantity = 30
        detail.calculate_variance()
        db.session.commit()
        
        # 生成差异单（冻结10后frozen_quantity=15）
        from app.views.count_manage import _create_variance_document
        losses = [detail]
        _create_variance_document(count, 'loss', losses)
        db.session.commit()
        
        # 手动增加锁定数量，模拟其他业务操作导致可用不足
        # 此时：quantity=40, locked=20, frozen=15
        # 审核后：quantity=30, frozen=5
        # 如果locked增加到26，则可用=30-26-5=-1（负可用）
        inv_special.locked_quantity = 26
        db.session.commit()
        
        variance = VarianceDocument.query.filter_by(count_id=count.id, variance_type='loss').first()
        
        # 尝试审核不强制通过
        from app.views.count_manage import _approve_variance_internal
        
        try:
            _approve_variance_internal(variance, force=False, approver_id=self.user.id)
            self.fail('应该抛出ValueError')
        except ValueError as e:
            self.assertIn('可用数量将为负', str(e))
        
        # 强制通过应该成功
        variance.status = 'pending'  # 重置状态
        _approve_variance_internal(variance, force=True, approver_id=self.user.id)
        db.session.commit()
        
        self.assertEqual(variance.status, 'approved')
        self.assertTrue(variance.force_approved)
    
    # ========== 明盘与暗盘测试 ==========
    
    def test_open_count_snapshot_visible(self):
        """测试：明盘模式快照数据可见"""
        count = InventoryCount(
            count_no='CT20250319011',
            count_type='open_count',  # 明盘
            scope_type='all',
            scope_filter=json.dumps({}),
            plan_date=date.today(),
            operator=self.user,
            status='draft'
        )
        db.session.add(count)
        db.session.flush()
        
        from app.views.count_manage import _create_snapshot
        _create_snapshot(count, 'all', {})
        db.session.commit()
        
        detail = count.details.first()
        
        # 明盘应该有快照数据
        self.assertIsNotNone(detail.snapshot_quantity)
        self.assertIsNotNone(detail.snapshot_locked)
        self.assertIsNotNone(detail.snapshot_frozen)
        self.assertIsNotNone(detail.snapshot_available)
    
    def test_blind_count_type(self):
        """测试：暗盘模式创建"""
        count = InventoryCount(
            count_no='CT20250319012',
            count_type='blind_count',  # 暗盘
            scope_type='all',
            scope_filter=json.dumps({}),
            plan_date=date.today(),
            operator=self.user,
            status='draft'
        )
        db.session.add(count)
        db.session.flush()
        
        from app.views.count_manage import _create_snapshot
        _create_snapshot(count, 'all', {})
        db.session.commit()
        
        # 暗盘仍然有快照存储（后端），但前端展示时隐藏
        detail = count.details.first()
        self.assertIsNotNone(detail.snapshot_quantity)
        self.assertEqual(count.count_type, 'blind_count')


class InventoryChangeLogTestCase(unittest.TestCase):
    """库存变更日志测试"""
    
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
    
    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    def test_change_log_on_inventory_adjust(self):
        """测试：库存调整时记录变更日志"""
        # 创建基础数据
        category = Category(name='测试分类')
        product = Product(code='P001', name='测试商品', unit='件', category=category)
        location = WarehouseLocation(code='A-01-01', name='库位A', location_type='normal')
        inventory = Inventory(product=product, location=location, quantity=100,
                             locked_quantity=10, frozen_quantity=5)
        
        db.session.add_all([category, product, location, inventory])
        db.session.commit()
        
        # 调整库存
        inventory.adjust_quantity(105, '盘点调整')
        db.session.commit()
        
        # 验证变更日志
        log = InventoryChangeLog.query.filter_by(inventory_id=inventory.id).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.change_type, 'adjustment')
        self.assertEqual(log.quantity_before, 100)
        self.assertEqual(log.quantity_after, 105)


if __name__ == '__main__':
    unittest.main()
