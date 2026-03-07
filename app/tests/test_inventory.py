import unittest
from app import create_app, db
from app.models.inventory import Inventory
from app.models.inventory_count import VirtualInventory
from app.models.product import Product, Category
from app.models.inventory import WarehouseLocation
from app.utils.helpers import update_inventory, update_virtual_inventory

class TestInventoryManagement(unittest.TestCase):
    def setUp(self):
        # 创建测试应用
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        
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
        
        # 创建产品
        self.product = Product(
            code='TEST001',
            name='测试产品',
            spec='标准规格',
            unit='个',
            category_id=category.id
        )
        db.session.add(self.product)
        
        # 创建库位
        self.location = WarehouseLocation(
            code='A01-01-01',
            name='测试库位',
            area='A区',
            status=True
        )
        db.session.add(self.location)
        
        # 创建初始库存
        self.inventory = Inventory(
            product_id=self.product.id,
            location_id=self.location.id,
            batch_no='B2026030701',
            quantity=0  # 初始数量为0
        )
        db.session.add(self.inventory)
        
        # 创建初始虚拟库存
        self.virtual_inventory = VirtualInventory(
            product_id=self.product.id,
            location_id=self.location.id,
            batch_no='B2026030701',
            physical_quantity=0,
            in_transit_quantity=0,
            allocated_quantity=0
        )
        db.session.add(self.virtual_inventory)
        
        db.session.commit()
    
    def test_inbound_increases_in_transit_inventory(self):
        """测试入库操作增加在途库存"""
        # 执行入库操作
        update_inventory(
            self.product.id,
            self.location.id,
            'B2026030701',
            10,
            is_bound=True
        )
        
        # 重新获取虚拟库存
        vi = VirtualInventory.query.filter_by(
            product_id=self.product.id,
            location_id=self.location.id,
            batch_no='B2026030701'
        ).first()
        
        # 验证在途库存增加
        self.assertEqual(vi.in_transit_quantity, 10)
        # 验证实物库存不变
        inventory = Inventory.query.filter_by(
            product_id=self.product.id,
            location_id=self.location.id,
            batch_no='B2026030701'
        ).first()
        self.assertEqual(inventory.quantity, 0)
    
    def test_outbound_increases_allocated_inventory(self):
        """测试出库操作增加已分配库存"""
        # 先入库10个，增加在途库存
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
        
        # 重新获取虚拟库存
        vi = VirtualInventory.query.filter_by(
            product_id=self.product.id,
            location_id=self.location.id,
            batch_no='B2026030701'
        ).first()
        
        # 验证已分配库存增加
        self.assertEqual(vi.allocated_quantity, 5)
        # 验证在途库存不变
        self.assertEqual(vi.in_transit_quantity, 10)
        # 验证实物库存不变
        inventory = Inventory.query.filter_by(
            product_id=self.product.id,
            location_id=self.location.id,
            batch_no='B2026030701'
        ).first()
        self.assertEqual(inventory.quantity, 0)
    
    def test_virtual_inventory_calculation(self):
        """测试虚拟库存计算"""
        # 更新虚拟库存
        update_virtual_inventory(
            self.product.id,
            self.location.id,
            'B2026030701',
            physical_change=0,
            in_transit_change=10,
            allocated_change=3
        )
        
        # 重新获取虚拟库存
        vi = VirtualInventory.query.filter_by(
            product_id=self.product.id,
            location_id=self.location.id,
            batch_no='B2026030701'
        ).first()
        
        # 验证虚拟库存计算
        expected_virtual = 0 + 10 - 3  # 实物 + 在途 - 已分配
        self.assertEqual(vi.virtual_quantity, expected_virtual)

if __name__ == '__main__':
    unittest.main()