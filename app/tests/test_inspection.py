import unittest
from datetime import datetime, date
from app import create_app, db
from app.models.user import User, Role, Permission
from app.models.purchase import PurchaseOrder
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
            product_id=self.product1.id,
            operator_id=self.user.id,
            expected_date=date.today(),
            quantity=100,
            unit_price=1.0,
            subtotal=100.0,
            allow_partial_receipt=True,
            status='pending_receipt'
        )
        db.session.add(order)
        db.session.flush()
        
        db.session.commit()
        
        # 验证采购单创建成功
        self.assertEqual(order.allow_partial_receipt, True)
        self.assertEqual(order.status, 'pending_receipt')
    
    def test_receive_and_inspection_with_defective(self):
        """测试收货和质检，包含不合格商品：只有已完成的采购单才能进行质检"""
        # 创建采购单，计划数量100
        order = PurchaseOrder(
            order_no='PO20260317002',
            supplier_id=self.supplier.id,
            product_id=self.product1.id,
            operator_id=self.user.id,
            expected_date=date.today(),
            quantity=100,
            unit_price=1.0,
            subtotal=100.0,
            status='pending_receipt'
        )
        db.session.add(order)
        db.session.flush()
        
        db.session.commit()
        
        # 第一次收货30个（不合格），累计收货数量30 < 计划数量100，状态应为收货中
        from flask import request
        from werkzeug.datastructures import MultiDict
        
        # 模拟POST请求数据：本次收货30个，全部不合格
        post_data = MultiDict({
            'signature': '测试管理员',
            'actual_quantity': '30',
            'qualified_quantity': '0',
            'unqualified_quantity': '30',
            'quality_status': 'failed',
            'defect_reason': '破损',
            'defect_location': str(self.reject_location.id)
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
            
            # 验证采购单状态：累计收货数量30 < 计划数量100，状态应为收货中
            updated_order = PurchaseOrder.query.get(order.id)
            self.assertEqual(updated_order.status, 'receiving')
            self.assertEqual(updated_order.qualified_quantity, 0)
            self.assertEqual(updated_order.unqualified_quantity, 30)
            self.assertEqual(updated_order.actual_quantity, 30)
            
            # 验证不应该创建检验单（因为只有已完成的采购单才能进行质检）
            inspection_orders = InspectionOrder.query.filter_by(purchase_order_id=order.id).all()
            self.assertEqual(len(inspection_orders), 0)  # 未完成的采购单不能创建检验单
        
        # 第二次收货40个（合格），累计收货数量70 < 计划数量100，状态仍为收货中
        post_data2 = MultiDict({
            'signature': '测试管理员',
            'actual_quantity': '40',
            'qualified_quantity': '40',
            'unqualified_quantity': '0',
            'quality_status': 'passed'
        })
        
        with self.app.test_request_context('/inspection/receive/1', method='POST', data=post_data2):
            from flask_login import login_user
            login_user(self.user)
            
            response = receive(order.id)
            
            # 验证采购单状态：累计收货数量70 < 计划数量100，状态应为收货中
            updated_order = PurchaseOrder.query.get(order.id)
            self.assertEqual(updated_order.status, 'receiving')
            self.assertEqual(updated_order.qualified_quantity, 40)
            self.assertEqual(updated_order.actual_quantity, 70)
        
        # 第三次收货30个（合格），累计收货数量100 >= 计划数量100，状态变为已完成
        post_data3 = MultiDict({
            'signature': '测试管理员',
            'actual_quantity': '30',
            'qualified_quantity': '30',
            'unqualified_quantity': '0',
            'quality_status': 'passed'
        })
        
        with self.app.test_request_context('/inspection/receive/1', method='POST', data=post_data3):
            from flask_login import login_user
            login_user(self.user)
            
            response = receive(order.id)
            
            # 刷新数据库会话，确保获取最新数据
            db.session.expire_all()
            
            # 验证采购单状态：累计收货数量100 >= 计划数量100，状态应为已完成
            updated_order = PurchaseOrder.query.get(order.id)
            self.assertEqual(updated_order.status, 'completed')
            self.assertEqual(updated_order.qualified_quantity, 70)
            self.assertEqual(updated_order.actual_quantity, 100)
            
            # 验证已完成的采购单可以创建检验单
            inspection_orders = InspectionOrder.query.filter_by(purchase_order_id=order.id).all()
            self.assertEqual(len(inspection_orders), 1)
            
            # 验证已完成的采购单可以创建检验单
            inspection_orders = InspectionOrder.query.filter_by(purchase_order_id=order.id).all()
            self.assertEqual(len(inspection_orders), 1)
    
    def test_purchase_order_status_update(self):
        """测试采购单状态自动更新逻辑：根据累计合格数量判断"""
        # 创建采购单，计划数量50
        order = PurchaseOrder(
            order_no='PO20260317003',
            supplier_id=self.supplier.id,
            product_id=self.product1.id,
            operator_id=self.user.id,
            expected_date=date.today(),
            quantity=50,
            unit_price=1.0,
            subtotal=50.0,
            status='pending_receipt'
        )
        db.session.add(order)
        db.session.flush()
        
        db.session.commit()
        
        # 模拟收货：合格数量50 = 计划数量50
        from flask import request
        from werkzeug.datastructures import MultiDict
        
        post_data = MultiDict({
            'signature': '测试管理员',
            'actual_quantity': '50',
            'qualified_quantity': '50',
            'unqualified_quantity': '0',
            'quality_status': 'passed'
        })
        
        from app.views.inspection_manage import receive
        
        with self.app.test_request_context('/inspection/receive/1', method='POST', data=post_data):
            from flask_login import login_user
            login_user(self.user)
            
            response = receive(order.id)
            
            # 验证采购单状态：累计合格数量50 >= 计划数量50，状态应为已完成
            updated_order = PurchaseOrder.query.get(order.id)
            self.assertEqual(updated_order.status, 'completed')
            
            # 验证已完成的采购单可以创建检验单
            inspection_orders = InspectionOrder.query.filter_by(purchase_order_id=order.id).all()
            self.assertEqual(len(inspection_orders), 1)
    
    def test_partial_receipt_functionality(self):
        """测试部分收货功能：根据累计合格数量判断采购单状态"""
        # 创建采购单，计划数量100
        order = PurchaseOrder(
            order_no='PO20260317004',
            supplier_id=self.supplier.id,
            product_id=self.product1.id,
            operator_id=self.user.id,
            expected_date=date.today(),
            quantity=100,
            unit_price=1.0,
            subtotal=100.0,
            status='pending_receipt'
        )
        db.session.add(order)
        db.session.flush()
        
        db.session.commit()
        
        # 第一次部分收货40个（合格）
        from flask import request
        from werkzeug.datastructures import MultiDict
        
        post_data1 = MultiDict({
            'signature': '测试管理员',
            'actual_quantity': '40',
            'qualified_quantity': '40',
            'unqualified_quantity': '0',
            'quality_status': 'passed'
        })
        
        from app.views.inspection_manage import receive
        
        with self.app.test_request_context('/inspection/receive/1', method='POST', data=post_data1):
            from flask_login import login_user
            login_user(self.user)
            
            response = receive(order.id)
            
            # 验证采购单状态：累计合格数量40 < 计划数量100，状态应为收货中
            updated_order = PurchaseOrder.query.get(order.id)
            self.assertEqual(updated_order.status, 'receiving')
            self.assertEqual(updated_order.qualified_quantity, 40)
        
        # 第三次收货30个（合格），剩余30个，累计收货70 < 计划100，状态仍为收货中
        post_data3 = MultiDict({
            'signature': '测试管理员',
            'actual_quantity': '30',
            'qualified_quantity': '30',
            'unqualified_quantity': '0',
            'quality_status': 'passed'
        })
        
        with self.app.test_request_context('/inspection/receive/1', method='POST', data=post_data3):
            from flask_login import login_user
            login_user(self.user)
            
            response = receive(order.id)
            
            # 验证采购单状态：累计收货数量70 < 计划100，状态应为收货中
            updated_order = PurchaseOrder.query.get(order.id)
            self.assertEqual(updated_order.status, 'receiving')
            self.assertEqual(updated_order.qualified_quantity, 70)
            self.assertEqual(updated_order.actual_quantity, 70)
        
        # 第四次收货30个（合格），剩余0个，累计收货100 >= 计划100，状态变为已完成
        post_data4 = MultiDict({
            'signature': '测试管理员',
            'actual_quantity': '30',
            'qualified_quantity': '30',
            'unqualified_quantity': '0',
            'quality_status': 'passed'
        })
        
        with self.app.test_request_context('/inspection/receive/1', method='POST', data=post_data4):
            from flask_login import login_user
            login_user(self.user)
            
            response = receive(order.id)
            
            # 刷新数据库会话，确保获取最新数据
            db.session.expire_all()
            
            # 验证采购单状态：累计收货数量100 >= 计划100，状态应为已完成
            updated_order = PurchaseOrder.query.get(order.id)
            self.assertEqual(updated_order.status, 'completed')
            self.assertEqual(updated_order.qualified_quantity, 100)
            self.assertEqual(updated_order.actual_quantity, 100)
            
            # 验证已完成的采购单可以创建检验单
            inspection_orders = InspectionOrder.query.filter_by(purchase_order_id=order.id).all()
            self.assertEqual(len(inspection_orders), 1)
        
        # 第三次收货30个（合格），剩余30个，累计合格100 >= 计划100，状态变为已完成
        post_data3 = MultiDict({
            'signature': '测试管理员',
            'actual_quantity': '30',
            'qualified_quantity': '30',
            'unqualified_quantity': '0',
            'quality_status': 'passed'
        })
        
        with self.app.test_request_context('/inspection/receive/1', method='POST', data=post_data3):
            from flask_login import login_user
            login_user(self.user)
            
            response = receive(order.id)
            
            # 刷新数据库会话，确保获取最新数据
            db.session.expire_all()
            
            # 验证采购单状态：累计合格数量100 >= 计划数量100，状态应为已完成
            updated_order = PurchaseOrder.query.get(order.id)
            self.assertEqual(updated_order.status, 'completed')
            self.assertEqual(updated_order.qualified_quantity, 100)
            
            # 验证已完成的采购单可以创建检验单
            inspection_orders = InspectionOrder.query.filter_by(purchase_order_id=order.id).all()
            self.assertEqual(len(inspection_orders), 1)

if __name__ == '__main__':
    unittest.main()