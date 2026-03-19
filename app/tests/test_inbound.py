"""
入库流程单元测试
测试范围：采购、收货、质检、入库、上架的完整流程
"""
import unittest
from datetime import datetime, date, timedelta
from app import create_app, db
from app.models import (
    User, Role, Permission, Product, Category, Supplier, WarehouseLocation,
    Inventory, InventoryChangeLog, PurchaseOrder, InspectionOrder, InspectionItem,
    InboundOrder, InboundItem
)
from app.utils.helpers import (
    generate_purchase_no, generate_inspection_no, generate_inbound_no,
    update_inventory, recommend_location
)


class InboundFlowTestCase(unittest.TestCase):
    """入库流程测试用例"""
    
    def setUp(self):
        """测试初始化"""
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        self._create_test_data()
    
    def tearDown(self):
        """测试清理"""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    def _create_test_data(self):
        """创建测试基础数据"""
        # 创建权限和角色
        perm = Permission(name='inbound_manage', desc='入库管理')
        role = Role(name='warehouse_manager', desc='仓库管理员')
        role.permissions.append(perm)
        
        self.user = User(username='testuser', real_name='测试员')
        self.user.set_password('password')
        self.user.roles.append(role)
        db.session.add_all([perm, role, self.user])
        
        # 创建分类和供应商
        self.category = Category(name='原材料', desc='原材料分类')
        self.supplier = Supplier(
            name='测试供应商',
            contact_person='张三',
            phone='13800138000'
        )
        db.session.add_all([self.category, self.supplier])
        
        # 创建商品
        self.product = Product(
            code='RM-TEST-001',
            name='测试原材料',
            spec='标准规格',
            unit='件',
            category_id=self.category.id,
            supplier_id=self.supplier.id,
            warning_stock=10
        )
        db.session.add(self.product)
        
        # 创建库位
        # 正常库位
        self.normal_location = WarehouseLocation(
            name='A区-正常库位',
            code='A-001',
            area='A区',
            location_type='normal',
            status=True,
            remark='正常存储区'
        )
        # 不合格品库位
        self.reject_location = WarehouseLocation(
            name='B区-不合格品区',
            code='B-001',
            area='B区',
            location_type='reject',
            status=True,
            remark='不合格品存放区'
        )
        # 等待区库位
        self.waiting_location = WarehouseLocation(
            name='C区-等待区',
            code='C-001',
            area='C区',
            location_type='waiting',
            status=True,
            remark='入库待上架区域'
        )
        # 待处理区库位
        self.pending_location = WarehouseLocation(
            name='D区-待处理区',
            code='D-001',
            area='D区',
            location_type='pending',
            status=True,
            remark='检验待处理区域'
        )
        db.session.add_all([
            self.normal_location, self.reject_location,
            self.waiting_location, self.pending_location
        ])
        
        db.session.commit()
    
    def test_01_purchase_order_create(self):
        """测试采购单创建"""
        purchase_order = PurchaseOrder(
            order_no=generate_purchase_no(),
            supplier_id=self.supplier.id,
            product_id=self.product.id,
            operator_id=self.user.id,
            expected_date=date.today() + timedelta(days=7),
            actual_date=date.today(),
            quantity=100,
            unit_price=50.0,
            subtotal=5000.0,
            status='pending',
            remark='测试采购单'
        )
        db.session.add(purchase_order)
        db.session.commit()
        
        self.assertIsNotNone(purchase_order.id)
        self.assertEqual(purchase_order.quantity, 100)
        self.assertEqual(purchase_order.status, 'pending')
        print(f"✓ 采购单创建成功: {purchase_order.order_no}")
    
    def test_02_inspection_order_create(self):
        """测试检验单创建"""
        # 先创建采购单
        purchase_order = PurchaseOrder(
            order_no=generate_purchase_no(),
            supplier_id=self.supplier.id,
            product_id=self.product.id,
            operator_id=self.user.id,
            expected_date=date.today() + timedelta(days=7),
            actual_date=date.today(),
            quantity=100,
            unit_price=50.0,
            subtotal=5000.0,
            status='completed',
            remark='测试采购单'
        )
        db.session.add(purchase_order)
        db.session.flush()
        
        # 创建检验单
        inspection_order = InspectionOrder(
            order_no=generate_inspection_no(),
            purchase_order_id=purchase_order.id,
            supplier_id=self.supplier.id,
            delivery_order_no=purchase_order.order_no,
            operator_id=self.user.id,
            inspection_date=date.today(),
            total_quantity=100,
            qualified_quantity=95,
            unqualified_quantity=5,
            status='completed',
            signature='质检员',
            remark='检验完成'
        )
        db.session.add(inspection_order)
        db.session.flush()
        
        # 创建检验明细
        inspection_item = InspectionItem(
            inspection_id=inspection_order.id,
            product_id=self.product.id,
            quantity=100,
            qualified_quantity=95,
            unqualified_quantity=5,
            quality_status='passed',
            remark='合格'
        )
        db.session.add(inspection_item)
        
        # 创建不合格品库存
        defective_inventory = Inventory(
            product_id=self.product.id,
            location_id=self.reject_location.id,
            batch_no=f'B{datetime.now().strftime("%Y%m%d")}D',
            quantity=5,
            defect_reason='外观瑕疵',
            inspection_order_id=inspection_order.id,
            remark='检验不合格'
        )
        db.session.add(defective_inventory)
        db.session.commit()
        
        self.assertIsNotNone(inspection_order.id)
        self.assertEqual(inspection_order.qualified_quantity, 95)
        self.assertEqual(inspection_order.unqualified_quantity, 5)
        self.assertEqual(defective_inventory.quantity, 5)
        print(f"✓ 检验单创建成功: {inspection_order.order_no}")
        print(f"  - 合格数量: 95, 不合格数量: 5")
    
    def test_03_pending_inventory_create(self):
        """测试待处理区库存创建"""
        # 创建采购单和检验单
        purchase_order = PurchaseOrder(
            order_no=generate_purchase_no(),
            supplier_id=self.supplier.id,
            product_id=self.product.id,
            operator_id=self.user.id,
            expected_date=date.today() + timedelta(days=7),
            actual_date=date.today(),
            quantity=100,
            unit_price=50.0,
            subtotal=5000.0,
            status='completed'
        )
        db.session.add(purchase_order)
        db.session.flush()
        
        inspection_order = InspectionOrder(
            order_no=generate_inspection_no(),
            purchase_order_id=purchase_order.id,
            supplier_id=self.supplier.id,
            delivery_order_no=purchase_order.order_no,
            operator_id=self.user.id,
            inspection_date=date.today(),
            total_quantity=100,
            qualified_quantity=95,
            unqualified_quantity=5,
            status='completed'
        )
        db.session.add(inspection_order)
        db.session.flush()
        
        # 创建待处理区库存（模拟检验合格后的库存）
        pending_inventory = Inventory(
            product_id=self.product.id,
            location_id=self.pending_location.id,
            batch_no=f'B{datetime.now().strftime("%Y%m%d")}P',
            quantity=95,
            inspection_order_id=inspection_order.id,
            remark='检验合格待入库'
        )
        db.session.add(pending_inventory)
        db.session.commit()
        
        self.assertIsNotNone(pending_inventory.id)
        self.assertEqual(pending_inventory.quantity, 95)
        self.assertEqual(pending_inventory.location.location_type, 'pending')
        print(f"✓ 待处理区库存创建成功: {pending_inventory.quantity} 件")
    
    def test_04_inbound_order_create(self):
        """测试入库单创建"""
        # 准备数据
        purchase_order = PurchaseOrder(
            order_no=generate_purchase_no(),
            supplier_id=self.supplier.id,
            product_id=self.product.id,
            operator_id=self.user.id,
            expected_date=date.today() + timedelta(days=7),
            actual_date=date.today(),
            quantity=100,
            unit_price=50.0,
            subtotal=5000.0,
            status='completed'
        )
        db.session.add(purchase_order)
        db.session.flush()
        
        inspection_order = InspectionOrder(
            order_no=generate_inspection_no(),
            purchase_order_id=purchase_order.id,
            supplier_id=self.supplier.id,
            delivery_order_no=purchase_order.order_no,
            operator_id=self.user.id,
            inspection_date=date.today(),
            total_quantity=100,
            qualified_quantity=95,
            unqualified_quantity=5,
            status='completed'
        )
        db.session.add(inspection_order)
        db.session.flush()
        
        # 创建待处理区库存
        pending_inventory = Inventory(
            product_id=self.product.id,
            location_id=self.pending_location.id,
            batch_no=f'B{datetime.now().strftime("%Y%m%d")}P',
            quantity=95,
            inspection_order_id=inspection_order.id,
            remark='检验合格待入库'
        )
        db.session.add(pending_inventory)
        db.session.flush()
        
        # 创建入库单
        inbound_order = InboundOrder(
            order_no=generate_inbound_no(),
            supplier_id=self.supplier.id,
            related_order=purchase_order.order_no,
            delivery_order_no=purchase_order.order_no,
            inspection_cert_no=inspection_order.order_no,
            purchase_order_id=purchase_order.id,
            inspection_order_id=inspection_order.id,
            operator_id=self.user.id,
            inbound_date=date.today(),
            total_amount=95,
            status='pending',
            remark='测试入库单'
        )
        db.session.add(inbound_order)
        db.session.flush()
        
        # 将库存从待处理区转移到等待区
        pending_inventory.location_id = self.waiting_location.id
        pending_inventory.remark = '入库待上架'
        
        # 创建库存变更日志
        transfer_log = InventoryChangeLog(
            inventory_id=pending_inventory.id,
            change_type='transfer',
            quantity_before=pending_inventory.quantity,
            quantity_after=pending_inventory.quantity,
            locked_quantity_before=0,
            locked_quantity_after=0,
            frozen_quantity_before=0,
            frozen_quantity_after=0,
            operator=self.user.username,
            reason='从待处理区转移到等待区',
            reference_id=inbound_order.id,
            reference_type='inbound_order'
        )
        db.session.add(transfer_log)
        
        # 创建入库明细
        inbound_item = InboundItem(
            order_id=inbound_order.id,
            product_id=self.product.id,
            location_id=self.waiting_location.id,
            quantity=95,
            batch_no=pending_inventory.batch_no,
            unit_price=50.0,
            subtotal=4750.0
        )
        db.session.add(inbound_item)
        db.session.commit()
        
        self.assertIsNotNone(inbound_order.id)
        self.assertEqual(inbound_order.status, 'pending')
        self.assertEqual(pending_inventory.location_id, self.waiting_location.id)
        print(f"✓ 入库单创建成功: {inbound_order.order_no}")
        print(f"  - 库存已从待处理区转移到等待区")
    
    def test_05_putaway_operation(self):
        """测试上架操作"""
        # 准备完整数据
        purchase_order = PurchaseOrder(
            order_no=generate_purchase_no(),
            supplier_id=self.supplier.id,
            product_id=self.product.id,
            operator_id=self.user.id,
            expected_date=date.today() + timedelta(days=7),
            actual_date=date.today(),
            quantity=100,
            unit_price=50.0,
            subtotal=5000.0,
            status='completed'
        )
        db.session.add(purchase_order)
        db.session.flush()
        
        inspection_order = InspectionOrder(
            order_no=generate_inspection_no(),
            purchase_order_id=purchase_order.id,
            supplier_id=self.supplier.id,
            delivery_order_no=purchase_order.order_no,
            operator_id=self.user.id,
            inspection_date=date.today(),
            total_quantity=100,
            qualified_quantity=95,
            unqualified_quantity=5,
            status='completed'
        )
        db.session.add(inspection_order)
        db.session.flush()
        
        pending_inventory = Inventory(
            product_id=self.product.id,
            location_id=self.pending_location.id,
            batch_no=f'B{datetime.now().strftime("%Y%m%d")}P',
            quantity=95,
            inspection_order_id=inspection_order.id,
            remark='检验合格待入库'
        )
        db.session.add(pending_inventory)
        db.session.flush()
        
        inbound_order = InboundOrder(
            order_no=generate_inbound_no(),
            supplier_id=self.supplier.id,
            related_order=purchase_order.order_no,
            delivery_order_no=purchase_order.order_no,
            inspection_cert_no=inspection_order.order_no,
            purchase_order_id=purchase_order.id,
            inspection_order_id=inspection_order.id,
            operator_id=self.user.id,
            inbound_date=date.today(),
            total_amount=95,
            status='pending'
        )
        db.session.add(inbound_order)
        db.session.flush()
        
        # 转移到等待区
        pending_inventory.location_id = self.waiting_location.id
        pending_inventory.remark = '入库待上架'
        
        inbound_item = InboundItem(
            order_id=inbound_order.id,
            product_id=self.product.id,
            location_id=self.waiting_location.id,
            quantity=95,
            batch_no=pending_inventory.batch_no,
            unit_price=50.0,
            subtotal=4750.0
        )
        db.session.add(inbound_item)
        db.session.commit()
        
        # 执行上架操作
        # 推荐库位
        normal_locations = WarehouseLocation.query.filter_by(
            location_type='normal', status=True
        ).all()
        recommended_location = recommend_location(self.product.id, normal_locations)
        
        self.assertIsNotNone(recommended_location)
        
        # 更新入库明细
        inbound_item.location_id = recommended_location.id
        inbound_item.signature = '仓库管理员'
        
        # 转移库存到正常库位
        waiting_inventory = Inventory.query.filter_by(
            product_id=self.product.id,
            location_id=self.waiting_location.id,
            batch_no=pending_inventory.batch_no
        ).first()
        
        self.assertIsNotNone(waiting_inventory)
        
        # 创建库存变更日志
        putaway_log = InventoryChangeLog(
            inventory_id=waiting_inventory.id,
            change_type='transfer',
            quantity_before=waiting_inventory.quantity,
            quantity_after=waiting_inventory.quantity,
            locked_quantity_before=0,
            locked_quantity_after=0,
            frozen_quantity_before=0,
            frozen_quantity_after=0,
            operator=self.user.username,
            reason='上架操作，从等待区转移到正常库位',
            reference_id=inbound_order.id,
            reference_type='inbound_order'
        )
        db.session.add(putaway_log)
        
        # 更新库存位置
        waiting_inventory.location_id = recommended_location.id
        waiting_inventory.remark = '已上架'
        
        # 更新入库单状态
        inbound_order.status = 'completed'
        db.session.commit()
        
        # 验证结果
        self.assertEqual(inbound_order.status, 'completed')
        self.assertEqual(waiting_inventory.location_id, recommended_location.id)
        self.assertEqual(waiting_inventory.location.location_type, 'normal')
        print(f"✓ 上架操作成功")
        print(f"  - 库存已转移到正常库位: {recommended_location.code}")
        print(f"  - 入库单状态更新为: completed")
    
    def test_06_complete_inbound_flow(self):
        """测试完整入库流程"""
        print("\n========== 开始完整入库流程测试 ==========")
        
        # 1. 创建采购单
        print("\n1. 创建采购单...")
        purchase_order = PurchaseOrder(
            order_no=generate_purchase_no(),
            supplier_id=self.supplier.id,
            product_id=self.product.id,
            operator_id=self.user.id,
            expected_date=date.today() + timedelta(days=7),
            actual_date=date.today(),
            quantity=200,
            unit_price=50.0,
            subtotal=10000.0,
            status='pending',
            remark='完整流程测试采购单'
        )
        db.session.add(purchase_order)
        db.session.commit()
        self.assertIsNotNone(purchase_order.id)
        print(f"   采购单号: {purchase_order.order_no}")
        
        # 2. 采购单完成
        print("\n2. 采购单完成...")
        purchase_order.status = 'completed'
        db.session.commit()
        self.assertEqual(purchase_order.status, 'completed')
        
        # 3. 创建检验单
        print("\n3. 创建检验单...")
        inspection_order = InspectionOrder(
            order_no=generate_inspection_no(),
            purchase_order_id=purchase_order.id,
            supplier_id=self.supplier.id,
            delivery_order_no=purchase_order.order_no,
            operator_id=self.user.id,
            inspection_date=date.today(),
            total_quantity=200,
            qualified_quantity=190,
            unqualified_quantity=10,
            status='completed',
            signature='质检员',
            remark='检验完成'
        )
        db.session.add(inspection_order)
        db.session.flush()
        
        # 创建检验明细
        inspection_item = InspectionItem(
            inspection_id=inspection_order.id,
            product_id=self.product.id,
            quantity=200,
            qualified_quantity=190,
            unqualified_quantity=10,
            quality_status='passed'
        )
        db.session.add(inspection_item)
        
        # 创建不合格品库存
        defective_inventory = Inventory(
            product_id=self.product.id,
            location_id=self.reject_location.id,
            batch_no=f'B{datetime.now().strftime("%Y%m%d")}R',
            quantity=10,
            defect_reason='质量不合格',
            inspection_order_id=inspection_order.id
        )
        db.session.add(defective_inventory)
        db.session.commit()
        print(f"   检验单号: {inspection_order.order_no}")
        print(f"   合格数量: 190, 不合格数量: 10")
        
        # 4. 创建待处理区库存
        print("\n4. 创建待处理区库存...")
        pending_inventory = Inventory(
            product_id=self.product.id,
            location_id=self.pending_location.id,
            batch_no=f'B{datetime.now().strftime("%Y%m%d")}P',
            quantity=190,
            inspection_order_id=inspection_order.id,
            remark='检验合格待入库'
        )
        db.session.add(pending_inventory)
        db.session.commit()
        self.assertEqual(pending_inventory.location.location_type, 'pending')
        print(f"   待处理区库存: {pending_inventory.quantity} 件")
        
        # 5. 创建入库单
        print("\n5. 创建入库单...")
        inbound_order = InboundOrder(
            order_no=generate_inbound_no(),
            supplier_id=self.supplier.id,
            related_order=purchase_order.order_no,
            delivery_order_no=purchase_order.order_no,
            inspection_cert_no=inspection_order.order_no,
            purchase_order_id=purchase_order.id,
            inspection_order_id=inspection_order.id,
            operator_id=self.user.id,
            inbound_date=date.today(),
            total_amount=190,
            status='pending',
            remark='完整流程测试入库单'
        )
        db.session.add(inbound_order)
        db.session.flush()
        
        # 转移到等待区
        pending_inventory.location_id = self.waiting_location.id
        pending_inventory.remark = '入库待上架'
        
        # 创建变更日志
        transfer_log = InventoryChangeLog(
            inventory_id=pending_inventory.id,
            change_type='transfer',
            quantity_before=pending_inventory.quantity,
            quantity_after=pending_inventory.quantity,
            locked_quantity_before=0,
            locked_quantity_after=0,
            frozen_quantity_before=0,
            frozen_quantity_after=0,
            operator=self.user.username,
            reason='从待处理区转移到等待区',
            reference_id=inbound_order.id,
            reference_type='inbound_order'
        )
        db.session.add(transfer_log)
        
        # 创建入库明细
        inbound_item = InboundItem(
            order_id=inbound_order.id,
            product_id=self.product.id,
            location_id=self.waiting_location.id,
            quantity=190,
            batch_no=pending_inventory.batch_no,
            unit_price=50.0,
            subtotal=9500.0
        )
        db.session.add(inbound_item)
        db.session.commit()
        print(f"   入库单号: {inbound_order.order_no}")
        print(f"   库存已转移到等待区")
        
        # 6. 上架操作
        print("\n6. 执行上架操作...")
        normal_locations = WarehouseLocation.query.filter_by(
            location_type='normal', status=True
        ).all()
        recommended_location = recommend_location(self.product.id, normal_locations)
        
        inbound_item.location_id = recommended_location.id
        inbound_item.signature = '仓库管理员'
        
        # 创建上架变更日志
        putaway_log = InventoryChangeLog(
            inventory_id=pending_inventory.id,
            change_type='transfer',
            quantity_before=pending_inventory.quantity,
            quantity_after=pending_inventory.quantity,
            locked_quantity_before=0,
            locked_quantity_after=0,
            frozen_quantity_before=0,
            frozen_quantity_after=0,
            operator=self.user.username,
            reason='上架操作，从等待区转移到正常库位',
            reference_id=inbound_order.id,
            reference_type='inbound_order'
        )
        db.session.add(putaway_log)
        
        pending_inventory.location_id = recommended_location.id
        pending_inventory.remark = '已上架'
        inbound_order.status = 'completed'
        db.session.commit()
        
        print(f"   上架库位: {recommended_location.code}")
        print(f"   入库单状态: completed")
        
        # 7. 验证最终结果
        print("\n7. 验证最终结果...")
        
        # 验证库存
        final_inventory = Inventory.query.filter_by(
            product_id=self.product.id,
            location_id=recommended_location.id
        ).first()
        self.assertIsNotNone(final_inventory)
        self.assertEqual(final_inventory.quantity, 190)
        print(f"   正常库位库存: {final_inventory.quantity} 件")
        
        # 验证不合格品库存
        reject_inventory = Inventory.query.filter_by(
            product_id=self.product.id,
            location_id=self.reject_location.id
        ).first()
        self.assertIsNotNone(reject_inventory)
        self.assertEqual(reject_inventory.quantity, 10)
        print(f"   不合格品库存: {reject_inventory.quantity} 件")
        
        # 验证变更日志
        change_logs = InventoryChangeLog.query.filter_by(
            reference_id=inbound_order.id,
            reference_type='inbound_order'
        ).all()
        self.assertEqual(len(change_logs), 2)
        print(f"   库存变更日志: {len(change_logs)} 条")
        
        print("\n========== 完整入库流程测试通过 ==========")
    
    def test_07_inventory_change_log_tracking(self):
        """测试库存变更日志追踪"""
        # 创建初始库存
        inventory = Inventory(
            product_id=self.product.id,
            location_id=self.pending_location.id,
            batch_no='B2026031901',
            quantity=100
        )
        db.session.add(inventory)
        db.session.flush()
        
        # 记录变更日志
        log1 = InventoryChangeLog(
            inventory_id=inventory.id,
            change_type='transfer',
            quantity_before=100,
            quantity_after=100,
            locked_quantity_before=0,
            locked_quantity_after=0,
            frozen_quantity_before=0,
            frozen_quantity_after=0,
            operator=self.user.username,
            reason='测试变更日志1',
            reference_id=1,
            reference_type='test'
        )
        db.session.add(log1)
        
        # 转移库存
        inventory.location_id = self.waiting_location.id
        
        log2 = InventoryChangeLog(
            inventory_id=inventory.id,
            change_type='transfer',
            quantity_before=100,
            quantity_after=100,
            locked_quantity_before=0,
            locked_quantity_after=0,
            frozen_quantity_before=0,
            frozen_quantity_after=0,
            operator=self.user.username,
            reason='测试变更日志2',
            reference_id=2,
            reference_type='test'
        )
        db.session.add(log2)
        db.session.commit()
        
        # 验证日志
        logs = InventoryChangeLog.query.filter_by(inventory_id=inventory.id).all()
        self.assertEqual(len(logs), 2)
        print(f"✓ 库存变更日志追踪测试通过，共 {len(logs)} 条日志")


if __name__ == '__main__':
    unittest.main(verbosity=2)