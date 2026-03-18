import unittest
from app import create_app, db
from app.models.inventory import Inventory
from app.models.product import Product, Category
from app.models.inventory import WarehouseLocation
from app.utils.helpers import update_inventory

class TestInventoryManagement(unittest.TestCase):
    def setUp(self):
        # 创建测试应用
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # 创建所有表结构
        db.create_all()
        
        # 创建测试数据
        self.create_test_data()
    
    def tearDown(self):
        # 清理测试数据
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    def create_test_data(self):
        # 创建分类
        category = Category(name='测试分类')
        db.session.add(category)
        db.session.flush()  # 刷新会话，获取分类的 id
        
        # 创建产品
        self.product = Product(
            code='TEST001',
            name='测试产品',
            spec='标准规格',
            unit='个',
            category_id=category.id
        )
        db.session.add(self.product)
        db.session.flush()  # 刷新会话，获取产品的 id
        
        # 创建库位
        self.location = WarehouseLocation(
            code='A01-01-01',
            name='测试库位',
            area='A区',
            status=True
        )
        db.session.add(self.location)
        db.session.flush()  # 刷新会话，获取库位的 id
        
        # 创建初始库存
        self.inventory = Inventory(
            product_id=self.product.id,
            location_id=self.location.id,
            batch_no='B2026030701',
            quantity=0  # 初始数量为0
        )
        db.session.add(self.inventory)
        

        
        db.session.commit()
    
    def test_inbound_increases_inventory(self):
        """测试入库操作增加库存"""
        # 执行入库操作
        update_inventory(
            self.product.id,
            self.location.id,
            'B2026030701',
            10,
            is_bound=True
        )
        
        # 验证实物库存增加
        inventory = Inventory.query.filter_by(
            product_id=self.product.id,
            location_id=self.location.id,
            batch_no='B2026030701'
        ).first()
        self.assertEqual(inventory.quantity, 10)
    
    def test_outbound_decreases_inventory(self):
        """测试出库操作减少库存"""
        # 先入库10个
        update_inventory(
            self.product.id,
            self.location.id,
            'B2026030701',
            10,
            is_bound=True
        )
        
        # 执行出库操作
        update_inventory(
            self.product.id,
            self.location.id,
            'B2026030701',
            5,
            is_bound=False
        )
        
        # 验证实物库存减少
        inventory = Inventory.query.filter_by(
            product_id=self.product.id,
            location_id=self.location.id,
            batch_no='B2026030701'
        ).first()
        self.assertEqual(inventory.quantity, 5)
    


    def test_inventory_status_waiting(self):
        """测试库存状态：等待（对应入库管理模块的"待上架"状态）"""
        # 创建等待区库位
        waiting_location = WarehouseLocation(
            code='WAIT-01',
            name='等待区',
            area='等待区',
            location_type='waiting',
            status=True
        )
        db.session.add(waiting_location)
        db.session.flush()
        
        # 创建等待状态的库存记录
        inventory = Inventory(
            product_id=self.product.id,
            location_id=waiting_location.id,
            batch_no='B2026030702',
            quantity=10
        )
        db.session.add(inventory)
        db.session.commit()
        
        # 验证库存状态为"等待"
        self.assertEqual(inventory.status, 'waiting')
        self.assertEqual(inventory.location.location_type, 'waiting')
    
    def test_inventory_status_normal(self):
        """测试库存状态：正常"""
        # 创建正常库位
        normal_location = WarehouseLocation(
            code='NORM-01',
            name='正常库位',
            area='正常区',
            location_type='normal',
            status=True
        )
        db.session.add(normal_location)
        db.session.flush()
        
        # 创建正常状态的库存记录
        inventory = Inventory(
            product_id=self.product.id,
            location_id=normal_location.id,
            batch_no='B2026030703',
            quantity=20
        )
        db.session.add(inventory)
        db.session.commit()
        
        # 验证库存状态为"正常"
        self.assertEqual(inventory.status, 'normal')
        self.assertEqual(inventory.location.location_type, 'normal')
    
    def test_inventory_status_transition_waiting_to_normal(self):
        """测试库存状态转换：等待 -> 正常（模拟上架流程）"""
        # 创建等待区库位
        waiting_location = WarehouseLocation(
            code='WAIT-02',
            name='等待区',
            area='等待区',
            location_type='waiting',
            status=True
        )
        db.session.add(waiting_location)
        
        # 创建正常库位
        normal_location = WarehouseLocation(
            code='NORM-02',
            name='正常库位',
            area='正常区',
            location_type='normal',
            status=True
        )
        db.session.add(normal_location)
        db.session.flush()
        
        # 创建等待状态的库存记录（模拟入库后待上架）
        inventory = Inventory(
            product_id=self.product.id,
            location_id=waiting_location.id,
            batch_no='B2026030704',
            quantity=15
        )
        db.session.add(inventory)
        db.session.commit()
        
        # 验证初始状态为"等待"
        self.assertEqual(inventory.status, 'waiting')
        
        # 模拟上架操作：更新库位
        inventory.location_id = normal_location.id
        db.session.commit()
        
        # 刷新库存记录
        db.session.refresh(inventory)
        
        # 验证状态已自动更新为"正常"
        self.assertEqual(inventory.status, 'normal')
        self.assertEqual(inventory.location.location_type, 'normal')
    
    def test_inventory_status_defective(self):
        """测试库存状态：不合格"""
        # 创建不合格品库位
        reject_location = WarehouseLocation(
            code='REJECT-01',
            name='不合格品区',
            area='不合格品区',
            location_type='reject',
            status=True
        )
        db.session.add(reject_location)
        db.session.flush()
        
        # 创建不合格状态的库存记录
        inventory = Inventory(
            product_id=self.product.id,
            location_id=reject_location.id,
            batch_no='B2026030705',
            quantity=5,
            defect_reason='质量问题'
        )
        db.session.add(inventory)
        db.session.commit()
        
        # 验证库存状态为"不合格"
        self.assertEqual(inventory.status, 'defective')
        self.assertTrue(inventory.is_defective())
        self.assertEqual(inventory.location.location_type, 'reject')
    
    def test_inventory_status_pending_inspection(self):
        """测试库存状态：待检"""
        # 创建待检区库位
        inspection_location = WarehouseLocation(
            code='INSP-01',
            name='待检区',
            area='待检区',
            location_type='inspection',
            status=True
        )
        db.session.add(inspection_location)
        db.session.flush()
        
        # 创建待检状态的库存记录
        inventory = Inventory(
            product_id=self.product.id,
            location_id=inspection_location.id,
            batch_no='B2026030706',
            quantity=8
        )
        db.session.add(inventory)
        db.session.commit()
        
        # 验证库存状态为"待检"
        self.assertEqual(inventory.status, 'pending_inspection')
        self.assertEqual(inventory.location.location_type, 'inspection')
    
    def test_inbound_order_status_consistency(self):
        """测试入库单状态与库存状态的一致性"""
        # 创建等待区库位
        waiting_location = WarehouseLocation(
            code='WAIT-03',
            name='等待区',
            area='等待区',
            location_type='waiting',
            status=True
        )
        db.session.add(waiting_location)
        db.session.flush()
        
        # 创建入库待上架的库存记录
        inventory = Inventory(
            product_id=self.product.id,
            location_id=waiting_location.id,
            batch_no='B2026030707',
            quantity=25
        )
        db.session.add(inventory)
        db.session.commit()
        
        # 验证库存状态为"等待"，与入库管理模块的"待上架"状态一致
        self.assertEqual(inventory.status, 'waiting')
        
        # 模拟入库单状态为"pending"（待上架）
        # 此时库存状态应该为"waiting"（等待）
        # 两者语义一致，只是不同模块的表述方式不同
        self.assertEqual(inventory.status, 'waiting')
    
    def test_inventory_status_changes_in_workflow(self):
        """测试库存状态在收货、质检、入库时的变化"""
        # 创建各个区域的库位
        # 1. 待检区库位（收货时）
        inspection_location = WarehouseLocation(
            code='INSP-02',
            name='待检区',
            area='待检区',
            location_type='inspection',
            status=True
        )
        db.session.add(inspection_location)
        
        # 2. 待处理区库位（质检后合格商品）
        pending_location = WarehouseLocation(
            code='PEND-01',
            name='待处理区',
            area='待处理区',
            location_type='pending',
            status=True
        )
        db.session.add(pending_location)
        
        # 3. 不合格品区库位（质检后不合格商品）
        reject_location = WarehouseLocation(
            code='REJECT-02',
            name='不合格品区',
            area='不合格品区',
            location_type='reject',
            status=True
        )
        db.session.add(reject_location)
        
        # 4. 等待区库位（入库时）
        waiting_location = WarehouseLocation(
            code='WAIT-04',
            name='等待区',
            area='等待区',
            location_type='waiting',
            status=True
        )
        db.session.add(waiting_location)
        
        # 5. 正常库位（上架后）
        normal_location = WarehouseLocation(
            code='NORM-03',
            name='正常库位',
            area='正常区',
            location_type='normal',
            status=True
        )
        db.session.add(normal_location)
        
        db.session.flush()
        
        # 1. 收货时：库存放到待检区，状态为待检
        inventory = Inventory(
            product_id=self.product.id,
            location_id=inspection_location.id,
            batch_no='B2026031801',
            quantity=100
        )
        db.session.add(inventory)
        db.session.commit()
        
        # 验证收货后的状态
        self.assertEqual(inventory.status, 'pending_inspection')
        self.assertEqual(inventory.location.location_type, 'inspection')
        
        # 2. 质检时：合格商品转移到待处理区，状态为待处理
        inventory.location_id = pending_location.id
        db.session.commit()
        
        # 刷新库存记录
        db.session.refresh(inventory)
        
        # 验证质检后的状态
        self.assertEqual(inventory.status, 'pending')
        self.assertEqual(inventory.location.location_type, 'pending')
        
        # 3. 入库时：从待处理区转移到等待区，状态为等待
        inventory.location_id = waiting_location.id
        db.session.commit()
        
        # 刷新库存记录
        db.session.refresh(inventory)
        
        # 验证入库后的状态
        self.assertEqual(inventory.status, 'waiting')
        self.assertEqual(inventory.location.location_type, 'waiting')
        
        # 4. 上架时：从等待区转移到正常库位，状态为正常
        inventory.location_id = normal_location.id
        db.session.commit()
        
        # 刷新库存记录
        db.session.refresh(inventory)
        
        # 验证上架后的状态
        self.assertEqual(inventory.status, 'normal')
        self.assertEqual(inventory.location.location_type, 'normal')
        
    def test_inventory_status_changes_for_defective(self):
        """测试库存状态在收货、质检（不合格）时的变化"""
        # 创建各个区域的库位
        # 1. 待检区库位（收货时）
        inspection_location = WarehouseLocation(
            code='INSP-03',
            name='待检区',
            area='待检区',
            location_type='inspection',
            status=True
        )
        db.session.add(inspection_location)
        
        # 2. 不合格品区库位（质检后不合格商品）
        reject_location = WarehouseLocation(
            code='REJECT-03',
            name='不合格品区',
            area='不合格品区',
            location_type='reject',
            status=True
        )
        db.session.add(reject_location)
        
        db.session.flush()
        
        # 1. 收货时：库存放到待检区，状态为待检
        inventory = Inventory(
            product_id=self.product.id,
            location_id=inspection_location.id,
            batch_no='B2026031802',
            quantity=50
        )
        db.session.add(inventory)
        db.session.commit()
        
        # 验证收货后的状态
        self.assertEqual(inventory.status, 'pending_inspection')
        self.assertEqual(inventory.location.location_type, 'inspection')
        
        # 2. 质检时：不合格商品转移到不合格品区，状态为不合格
        inventory.location_id = reject_location.id
        inventory.defect_reason = '质量问题'
        db.session.commit()
        
        # 刷新库存记录
        db.session.refresh(inventory)
        
        # 验证质检后的状态
        self.assertEqual(inventory.status, 'defective')
        self.assertTrue(inventory.is_defective())
        self.assertEqual(inventory.location.location_type, 'reject')
        self.assertEqual(inventory.defect_reason, '质量问题')


if __name__ == '__main__':
    unittest.main()