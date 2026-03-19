import unittest
from app import create_app, db
from app.models.inventory import Inventory, WarehouseLocation, StockMoveOrder, StockMoveItem, InventoryChangeLog
from app.models.product import Product, Category
from app.models.user import User, Role
from datetime import datetime
import logging

# 配置日志记录器
logger = logging.getLogger(__name__)


class TestStockMoveBasic(unittest.TestCase):
    """基本移库测试"""
    
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
        db.session.commit()
        
        # 创建产品
        self.product1 = Product(
            code='TEST001',
            name='测试产品1',
            spec='标准规格',
            unit='个',
            category_id=category.id
        )
        db.session.add(self.product1)
        
        self.product2 = Product(
            code='TEST002',
            name='测试产品2',
            spec='大规格',
            unit='个',
            category_id=category.id
        )
        db.session.add(self.product2)
        db.session.commit()
        
        # 创建正常库位
        self.normal_location1 = WarehouseLocation(
            code='NORM-01',
            name='正常库位1',
            area='A区',
            location_type='normal',
            status=True
        )
        db.session.add(self.normal_location1)
        
        self.normal_location2 = WarehouseLocation(
            code='NORM-02',
            name='正常库位2',
            area='A区',
            location_type='normal',
            status=True
        )
        db.session.add(self.normal_location2)
        
        # 创建等待区库位
        self.waiting_location = WarehouseLocation(
            code='WAIT-01',
            name='等待区',
            area='等待区',
            location_type='waiting',
            status=True
        )
        db.session.add(self.waiting_location)
        db.session.commit()
        
        # 创建初始库存
        self.inventory1 = Inventory(
            product_id=self.product1.id,
            location_id=self.normal_location1.id,
            batch_no='B2026031801',
            quantity=100,
            locked_quantity=0,
            frozen_quantity=0
        )
        db.session.add(self.inventory1)
        
        self.inventory2 = Inventory(
            product_id=self.product2.id,
            location_id=self.normal_location2.id,
            batch_no='B2026031802',
            quantity=50,
            locked_quantity=0,
            frozen_quantity=0
        )
        db.session.add(self.inventory2)
        
        # 创建用户
        role = Role(name='测试角色')
        db.session.add(role)
        db.session.commit()

        self.user = User(
            username='testuser',
            real_name='测试用户'
        )
        self.user.set_password('test123')
        self.user.roles.append(role)
        db.session.add(self.user)

        db.session.commit()
    
    def test_create_stock_move_order(self):
        """测试创建移库单"""
        # 创建移库单
        order_no = f'MV{datetime.now().strftime("%Y%m%d")}001'
        stock_move_order = StockMoveOrder(
            order_no=order_no,
            operator_id=self.user.id,
            move_date=datetime.now().date(),
            total_quantity=20,
            status='pending',
            reason='补货',
            remark='测试移库'
        )
        db.session.add(stock_move_order)
        db.session.commit()
        
        # 验证移库单创建成功
        saved_order = StockMoveOrder.query.filter_by(order_no=order_no).first()
        self.assertIsNotNone(saved_order)
        self.assertEqual(saved_order.status, 'pending')
        self.assertEqual(saved_order.total_quantity, 20)
    
    def test_create_stock_move_item(self):
        """测试创建移库明细"""
        # 创建移库单
        order_no = f'MV{datetime.now().strftime("%Y%m%d")}002'
        stock_move_order = StockMoveOrder(
            order_no=order_no,
            operator_id=self.user.id,
            move_date=datetime.now().date(),
            total_quantity=20,
            status='pending'
        )
        db.session.add(stock_move_order)
        db.session.commit()
        
        # 创建移库明细
        move_item = StockMoveItem(
            order_id=stock_move_order.id,
            product_id=self.product1.id,
            source_location_id=self.normal_location1.id,
            target_location_id=self.normal_location2.id,
            quantity=20,
            move_batch_no='MV2026031801'
        )
        db.session.add(move_item)
        db.session.commit()
        
        # 验证移库明细创建成功
        saved_item = StockMoveItem.query.filter_by(order_id=stock_move_order.id).first()
        self.assertIsNotNone(saved_item)
        self.assertEqual(saved_item.quantity, 20)
    
    def test_location_type_validation(self):
        """测试库位类型验证"""
        # 验证正常库位类型相同
        self.assertEqual(self.normal_location1.location_type, 'normal')
        self.assertEqual(self.normal_location2.location_type, 'normal')
        
        # 验证等待区库位类型不同
        self.assertEqual(self.waiting_location.location_type, 'waiting')
        self.assertNotEqual(self.normal_location1.location_type, self.waiting_location.location_type)
    
    def test_inventory_quantity_validation(self):
        """测试库存数量验证"""
        # 验证初始库存数量
        self.assertEqual(self.inventory1.quantity, 100)
        self.assertEqual(self.inventory1.locked_quantity, 0)
        self.assertEqual(self.inventory1.frozen_quantity, 0)
        self.assertEqual(self.inventory1.available_quantity, 100)
        
        # 验证可用数量计算
        self.inventory1.locked_quantity = 20
        self.assertEqual(self.inventory1.available_quantity, 80)
        
        self.inventory1.frozen_quantity = 10
        self.assertEqual(self.inventory1.available_quantity, 70)


if __name__ == '__main__':
    unittest.main()