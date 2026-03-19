import unittest
from app import create_app, db
from app.models.inventory import Inventory, WarehouseLocation
from app.models.product import Product, Category


class TestStockMoveSimple(unittest.TestCase):
    """简化的移库测试"""
    
    def setUp(self):
        # 创建测试应用
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # 创建所有表结构
        db.create_all()
    
    def tearDown(self):
        # 清理测试数据
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    def test_create_location(self):
        """测试创建库位"""
        location = WarehouseLocation(
            code='TEST-01',
            name='测试库位',
            area='测试区',
            location_type='normal',
            status=True
        )
        db.session.add(location)
        db.session.commit()
        
        # 验证库位创建成功
        saved_location = WarehouseLocation.query.filter_by(code='TEST-01').first()
        self.assertIsNotNone(saved_location)
        self.assertEqual(saved_location.name, '测试库位')
    
    def test_create_product(self):
        """测试创建产品"""
        category = Category(name='测试分类')
        db.session.add(category)
        db.session.commit()
        
        product = Product(
            code='TEST001',
            name='测试产品',
            spec='标准规格',
            unit='个',
            category_id=category.id
        )
        db.session.add(product)
        db.session.commit()
        
        # 验证产品创建成功
        saved_product = Product.query.filter_by(code='TEST001').first()
        self.assertIsNotNone(saved_product)
        self.assertEqual(saved_product.name, '测试产品')
    
    def test_create_inventory(self):
        """测试创建库存"""
        # 创建分类
        category = Category(name='测试分类')
        db.session.add(category)
        db.session.commit()
        
        # 创建产品
        product = Product(
            code='TEST001',
            name='测试产品',
            spec='标准规格',
            unit='个',
            category_id=category.id
        )
        db.session.add(product)
        db.session.commit()
        
        # 创建库位
        location = WarehouseLocation(
            code='TEST-01',
            name='测试库位',
            area='测试区',
            location_type='normal',
            status=True
        )
        db.session.add(location)
        db.session.commit()
        
        # 创建库存
        inventory = Inventory(
            product_id=product.id,
            location_id=location.id,
            batch_no='B2026031801',
            quantity=100,
            locked_quantity=0,
            frozen_quantity=0
        )
        db.session.add(inventory)
        db.session.commit()
        
        # 验证库存创建成功
        saved_inventory = Inventory.query.filter_by(
            product_id=product.id,
            location_id=location.id
        ).first()
        self.assertIsNotNone(saved_inventory)
        self.assertEqual(saved_inventory.quantity, 100)


if __name__ == '__main__':
    unittest.main()