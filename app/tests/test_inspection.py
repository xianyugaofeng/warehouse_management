import unittest
from datetime import datetime, date
from app import create_app, db
from app.models.user import User, Role, Permission
from app.models.purchase import PurchaseOrder, PurchaseItem
from app.models.product import Product, Supplier, Category
from app.models.inspection import InspectionOrder, InspectionItem, DefectiveProduct
from app.models.inventory import WarehouseLocation

class TestInspection(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        # 创建测试数据
        self.create_test_data()
        
    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    def create_test_data(self):
        # 创建角色和权限
        role = Role(name='仓库管理员', desc='仓库管理员角色')
        perm = Permission(name='inbound_manage', desc='入库管理')
        role.permissions.append(perm)
        db.session.add(role)
        db.session.add(perm)
        
        # 创建用户
        self.user = User(username='test')
        self.user.set_password('123456')
        self.user.roles.append(role)
        db.session.add(self.user)
        
        # 创建供应商
        self.supplier = Supplier(name='测试供应商', contact_person='张三', phone='13800138000')
        db.session.add(self.supplier)
        
        # 创建分类
        category1 = Category(name='电子产品', desc='电子产品分类')
        category2 = Category(name='服装', desc='服装分类')
        db.session.add(category1)
        db.session.add(category2)
        
        # 创建商品
        self.product1 = Product(name='测试商品1', code='P001', unit='个', category_id=category1.id)
        self.product2 = Product(name='测试商品2', code='P002', unit='件', category_id=category2.id)
        db.session.add(self.product1)
        db.session.add(self.product2)
        
        # 创建库位
        self.normal_location = WarehouseLocation(code='N001', name='正常库位', location_type='normal')
        self.reject_location = WarehouseLocation(code='R001', name='不合格品暂存区', location_type='reject')
        db.session.add(self.normal_location)
        db.session.add(self.reject_location)
        
        db.session.commit()
    
    def test_create_purchase_order_with_partial_receipt(self):
        """测试创建允许部分收货的采购单"""
        # 创建允许部分收货的采购单
        order = PurchaseOrder(
            order_no='PO20260317001',
            supplier_id=self.supplier.id,
            operator_id=self.user.id,
            expected_date=date.today(),
            total_amount=100,
            allow_partial_receipt=True,
            status='pending_receipt'
        )
        db.session.add(order)
        db.session.flush()
        
        # 添加采购明细
        item1 = PurchaseItem(
            order_id=order.id,
            product_id=self.product1.id,
            quantity=50,
            unit_price=100.0,
            subtotal=5000.0
        )
        item2 = PurchaseItem(
            order_id=order.id,
            product_id=self.product2.id,
            quantity=50,
            unit_price=200.0,
            subtotal=10000.0
        )
        db.session.add(item1)
        db.session.add(item2)
        db.session.commit()
        
        # 验证采购单创建成功
        self.assertEqual(order.allow_partial_receipt, True)
        self.assertEqual(order.status, 'pending_receipt')
        self.assertEqual(order.items.count(), 2)
    
    def test_receive_and_inspection_with_defective(self):
        """测试收货和质检，包含不合格商品"""
        # 创建采购单
        order = PurchaseOrder(
            order_no='PO20260317002',
            supplier_id=self.supplier.id,
            operator_id=self.user.id,
            expected_date=date.today(),
            total_amount=100,
            allow_partial_receipt=False,
            status='pending_receipt'
        )
        db.session.add(order)
        db.session.flush()
        
        # 添加采购明细
        item = PurchaseItem(
            order_id=order.id,
            product_id=self.product1.id,
            quantity=100,
            unit_price=100.0,
            subtotal=10000.0
        )
        db.session.add(item)
        db.session.commit()
        
        # 模拟收货和质检数据
        from flask import request
        from werkzeug.datastructures import MultiDict
        
        # 模拟POST请求数据
        post_data = MultiDict({
            'signature': '测试管理员',
            f'actual_quantity_{item.id}': '80',
            f'quality_status_{item.id}': 'failed',
            f'defect_reason_{item.id}': '破损',
            f'defect_location_{item.id}': str(self.reject_location.id)
        })
        
        # 导入视图函数进行测试
        from app.views.inspection_manage import receive
        
        # 模拟请求上下文
        with self.app.test_request_context('/inspection/receive/1', method='POST', data=post_data):
            # 模拟登录用户
            from flask_login import login_user
            login_user(self.user)
            
            # 调用收货函数
            response = receive(order.id)
            
            # 验证采购单状态
            updated_order = PurchaseOrder.query.get(order.id)
            self.assertEqual(updated_order.status, 'receiving')  # 未达到计划数量，状态应为收货中
            
            # 验证不合格商品记录
            defective_products = DefectiveProduct.query.filter_by(inspection_order_id=InspectionOrder.query.first().id).all()
            self.assertEqual(len(defective_products), 1)
            self.assertEqual(defective_products[0].quantity, 80)
            self.assertEqual(defective_products[0].defect_reason, '破损')
            self.assertEqual(defective_products[0].location_id, self.reject_location.id)
    
    def test_purchase_order_status_update(self):
        """测试采购单状态自动更新逻辑"""
        # 创建不允许部分收货的采购单
        order = PurchaseOrder(
            order_no='PO20260317003',
            supplier_id=self.supplier.id,
            operator_id=self.user.id,
            expected_date=date.today(),
            total_amount=50,
            allow_partial_receipt=False,
            status='pending_receipt'
        )
        db.session.add(order)
        db.session.flush()
        
        # 添加采购明细
        item = PurchaseItem(
            order_id=order.id,
            product_id=self.product1.id,
            quantity=50,
            unit_price=100.0,
            subtotal=5000.0
        )
        db.session.add(item)
        db.session.commit()
        
        # 模拟全量收货
        from flask import request
        from werkzeug.datastructures import MultiDict
        
        post_data = MultiDict({
            'signature': '测试管理员',
            f'actual_quantity_{item.id}': '50',
            f'quality_status_{item.id}': 'passed'
        })
        
        from app.views.inspection_manage import receive
        
        with self.app.test_request_context('/inspection/receive/1', method='POST', data=post_data):
            from flask_login import login_user
            login_user(self.user)
            
            response = receive(order.id)
            
            # 验证采购单状态
            updated_order = PurchaseOrder.query.get(order.id)
            self.assertEqual(updated_order.status, 'completed')  # 达到计划数量，状态应为已完成
    
    def test_partial_receipt_functionality(self):
        """测试部分收货功能"""
        # 创建允许部分收货的采购单
        order = PurchaseOrder(
            order_no='PO20260317004',
            supplier_id=self.supplier.id,
            operator_id=self.user.id,
            expected_date=date.today(),
            total_amount=100,
            allow_partial_receipt=True,
            status='pending_receipt'
        )
        db.session.add(order)
        db.session.flush()
        
        # 添加采购明细
        item = PurchaseItem(
            order_id=order.id,
            product_id=self.product1.id,
            quantity=100,
            unit_price=100.0,
            subtotal=10000.0
        )
        db.session.add(item)
        db.session.commit()
        
        # 第一次部分收货
        from flask import request
        from werkzeug.datastructures import MultiDict
        
        # 第一次收货40个
        post_data1 = MultiDict({
            'signature': '测试管理员',
            f'actual_quantity_{item.id}': '40',
            f'quality_status_{item.id}': 'passed',
            'complete_receipt': 'false'
        })
        
        from app.views.inspection_manage import receive
        
        with self.app.test_request_context('/inspection/receive/1', method='POST', data=post_data1):
            from flask_login import login_user
            login_user(self.user)
            
            response = receive(order.id)
            
            # 验证采购单状态
            updated_order = PurchaseOrder.query.get(order.id)
            self.assertEqual(updated_order.status, 'receiving')  # 部分收货，状态应为收货中
        
        # 第二次部分收货并标记完成
        post_data2 = MultiDict({
            'signature': '测试管理员',
            f'actual_quantity_{item.id}': '30',  # 累计70个
            f'quality_status_{item.id}': 'passed',
            'complete_receipt': 'true'  # 手动标记完成
        })
        
        with self.app.test_request_context('/inspection/receive/1', method='POST', data=post_data2):
            from flask_login import login_user
            login_user(self.user)
            
            response = receive(order.id)
            
            # 验证采购单状态
            updated_order = PurchaseOrder.query.get(order.id)
            self.assertEqual(updated_order.status, 'completed')  # 手动标记完成，状态应为已完成

if __name__ == '__main__':
    unittest.main()