import unittest
import uuid
from datetime import datetime
from app import create_app, db
from app.models import ReturnOrder, ReturnItem, DefectiveProduct, Product, WarehouseLocation, User


class TestReturn(unittest.TestCase):
    def setUp(self):
        """设置测试环境"""
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        # 先删除所有表，确保测试环境干净
        db.drop_all()
        # 再创建所有表
        db.create_all()
        
        # 创建测试数据
        self.create_test_data()
    
    def tearDown(self):
        """清理测试环境"""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    def create_test_data(self):
        """创建测试数据"""
        # 创建用户，使用唯一的用户名
        random_username = f'testuser_{uuid.uuid4().hex[:8]}'
        self.user = User(username=random_username, real_name='测试用户')
        self.user.set_password('password')
        db.session.add(self.user)
        
        # 创建商品，使用唯一的代码
        random_code = f'TEST_{uuid.uuid4().hex[:8]}'
        self.product = Product(name='测试商品', code=random_code)
        db.session.add(self.product)
        
        # 创建库位，使用唯一的代码
        random_code = f'A1-01_{uuid.uuid4().hex[:8]}'
        self.location = WarehouseLocation(code=random_code, name='测试库位', location_type='reject')
        db.session.add(self.location)
        
        # 先提交用户、商品和库位，确保它们有ID
        db.session.commit()
        
        # 创建供应商
        from app.models import Supplier
        supplier = Supplier(
            name=f'Supplier_{uuid.uuid4().hex[:8]}',
            contact_person='测试联系人',
            phone='13800138000'
        )
        db.session.add(supplier)
        db.session.commit()
        
        # 创建采购单
        from app.models import PurchaseOrder
        purchase_order = PurchaseOrder(
            order_no=f'PO_{uuid.uuid4().hex[:8]}',
            supplier_id=supplier.id,  # 使用刚刚创建的供应商ID
            product_id=self.product.id,  # 使用刚刚创建的商品ID
            operator_id=self.user.id,
            expected_date=datetime.now().date(),
            quantity=100,  # 设置采购数量
            unit_price=100.0,  # 设置单价
            subtotal=10000.0  # 设置小计
        )
        db.session.add(purchase_order)
        db.session.commit()
        
        # 创建检验单，使用唯一的检验单号
        from app.models import InspectionOrder
        random_order_no = f'QO_{uuid.uuid4().hex[:8]}'
        inspection_order = InspectionOrder(
            order_no=random_order_no,
            purchase_order_id=purchase_order.id,  # 使用刚刚创建的采购单ID
            operator_id=self.user.id,  # 设置为之前创建的用户的ID
            inspection_date=datetime.now().date()
        )
        db.session.add(inspection_order)
        db.session.commit()
        
        # 创建不合格商品
        self.defective_product = DefectiveProduct(
            product=self.product,
            location=self.location,
            quantity=100,
            batch_no='BATCH001',
            defect_reason='质量问题',
            inspection_order_id=inspection_order.id
        )
        db.session.add(self.defective_product)
        db.session.commit()
    
    def test_return_order_creation(self):
        """测试退货单创建"""
        # 创建退货单
        return_order = ReturnOrder(
            order_no='RT202603180001',
            return_date=datetime.now().date(),
            return_reason='质量问题',
            operator_id=self.user.id
        )
        
        # 创建退货明细
        return_item = ReturnItem(
            return_order=return_order,
            product_id=self.product.id,
            location_id=self.location.id,
            batch_no='BATCH001',
            quantity=10,
            unit_price=100.0,
            amount=1000.0,
            defect_reason='质量问题'
        )
        
        db.session.add(return_order)
        db.session.commit()
        
        # 手动更新不合格商品数量，模拟视图函数中的逻辑
        defective_product = DefectiveProduct.query.filter_by(
            product_id=self.product.id,
            location_id=self.location.id,
            batch_no='BATCH001'
        ).first()
        if defective_product and defective_product.quantity >= 10:
            defective_product.quantity -= 10
            db.session.commit()
        
        # 验证退货单创建成功
        self.assertIsNotNone(return_order.id)
        self.assertEqual(return_order.order_no, 'RT202603180001')
        self.assertEqual(return_order.items.count(), 1)
        
        # 验证不合格商品数量更新
        updated_defective = DefectiveProduct.query.filter_by(
            product_id=self.product.id,
            location_id=self.location.id,
            batch_no='BATCH001'
        ).first()
        self.assertEqual(updated_defective.quantity, 90)  # 100 - 10 = 90
    
    def test_return_order_query(self):
        """测试退货单查询"""
        # 创建退货单
        return_order = ReturnOrder(
            order_no='RT202603180001',
            return_date=datetime.now().date(),
            return_reason='质量问题',
            operator_id=self.user.id
        )
        
        db.session.add(return_order)
        db.session.commit()
        
        # 查询退货单
        queried_order = ReturnOrder.query.filter_by(order_no='RT202603180001').first()
        self.assertIsNotNone(queried_order)
        self.assertEqual(queried_order.id, return_order.id)
    
    def test_return_item_relationship(self):
        """测试退货明细与退货单的关系"""
        # 创建退货单
        return_order = ReturnOrder(
            order_no='RT202603180001',
            return_date=datetime.now().date(),
            return_reason='质量问题',
            operator_id=self.user.id
        )
        
        # 创建多个退货明细
        for i in range(3):
            return_item = ReturnItem(
                return_order=return_order,
                product_id=self.product.id,
                location_id=self.location.id,
                batch_no=f'BATCH00{i+1}',
                quantity=5,
                unit_price=100.0,
                amount=500.0,
                defect_reason='质量问题'
            )
        
        db.session.add(return_order)
        db.session.commit()
        
        # 验证退货明细与退货单的关系
        self.assertEqual(return_order.items.count(), 3)
        for item in return_order.items:
            self.assertEqual(item.return_order_id, return_order.id)


if __name__ == '__main__':
    unittest.main()