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
    


if __name__ == '__main__':
    unittest.main()