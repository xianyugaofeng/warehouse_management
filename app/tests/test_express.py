import unittest
from app import create_app, db
from app.models.express import Waybill, ScanRecord, InventoryStatus
from app.models.inventory import Inventory, WarehouseLocation
from app.models.product import Product
from app.models.user import User
from flask_login import login_user
import json


class ExpressTestCase(unittest.TestCase):
    """快递站库存管理测试"""
    
    def setUp(self):
        """设置测试环境"""
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
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
        # 创建用户
        self.user = User(username='test', password_hash='test')
        db.session.add(self.user)
        
        # 创建库位
        self.location = WarehouseLocation(code='A1-01-01', name='测试库位', status=True)
        db.session.add(self.location)
        
        # 创建商品
        self.product = Product(code='P001', name='测试商品')
        db.session.add(self.product)
        
        # 创建运单
        self.waybill = Waybill(
            waybill_no='1234567890',
            product_id=self.product.id,
            status='in_transit'
        )
        db.session.add(self.waybill)
        
        db.session.commit()
    
    def test_scan_arrival(self):
        """测试到件扫描"""
        # 登录用户
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user.id
        
        # 发送到件扫描请求
        response = self.client.post('/express/scan/arrival', json={
            'waybill_no': '1234567890',
            'location_id': self.location.id,
            'batch_no': 'BATCH001'
        })
        
        # 检查响应
        data = json.loads(response.data)
        self.assertEqual(data['success'], True)
        
        # 检查运单状态
        waybill = Waybill.query.filter_by(waybill_no='1234567890').first()
        self.assertEqual(waybill.status, 'arrived_station')
        
        # 检查库存
        inventory = Inventory.query.filter_by(
            product_id=self.product.id,
            location_id=self.location.id,
            batch_no='BATCH001'
        ).first()
        self.assertIsNotNone(inventory)
        self.assertEqual(inventory.quantity, 1)
    
    def test_scan_departure(self):
        """测试派件扫描"""
        # 先执行到件扫描
        self.test_scan_arrival()
        
        # 发送派件扫描请求
        response = self.client.post('/express/scan/departure', json={
            'waybill_no': '1234567890',
            'location_id': self.location.id
        })
        
        # 检查响应
        data = json.loads(response.data)
        self.assertEqual(data['success'], True)
        
        # 检查运单状态
        waybill = Waybill.query.filter_by(waybill_no='1234567890').first()
        self.assertEqual(waybill.status, 'out_for_delivery')
        
        # 检查库存
        inventory = Inventory.query.filter_by(
            product_id=self.product.id,
            location_id=self.location.id
        ).first()
        self.assertEqual(inventory.quantity, 0)
    
    def test_scan_delivery(self):
        """测试签收扫描"""
        # 先执行到件和派件扫描
        self.test_scan_arrival()
        self.test_scan_departure()
        
        # 发送签收扫描请求
        response = self.client.post('/express/scan/delivery', json={
            'waybill_no': '1234567890',
            'location_id': self.location.id
        })
        
        # 检查响应
        data = json.loads(response.data)
        self.assertEqual(data['success'], True)
        
        # 检查运单状态
        waybill = Waybill.query.filter_by(waybill_no='1234567890').first()
        self.assertEqual(waybill.status, 'delivered')
    
    def test_scan_problem(self):
        """测试问题件扫描"""
        # 先执行到件扫描
        self.test_scan_arrival()
        
        # 发送问题件扫描请求
        response = self.client.post('/express/scan/problem', json={
            'waybill_no': '1234567890',
            'location_id': self.location.id,
            'remark': '包裹破损'
        })
        
        # 检查响应
        data = json.loads(response.data)
        self.assertEqual(data['success'], True)
        
        # 检查运单状态
        waybill = Waybill.query.filter_by(waybill_no='1234567890').first()
        self.assertEqual(waybill.status, 'problem')
        
        # 检查库存状态
        inventory_status = InventoryStatus.query.filter_by(
            waybill_id=waybill.id
        ).first()
        self.assertEqual(inventory_status.status, 'problem')
    
    def test_scan_return(self):
        """测试回流扫描"""
        # 先执行到件和派件扫描
        self.test_scan_arrival()
        self.test_scan_departure()
        
        # 发送回流扫描请求
        response = self.client.post('/express/scan/return', json={
            'waybill_no': '1234567890',
            'location_id': self.location.id
        })
        
        # 检查响应
        data = json.loads(response.data)
        self.assertEqual(data['success'], True)
        
        # 检查运单状态
        waybill = Waybill.query.filter_by(waybill_no='1234567890').first()
        self.assertEqual(waybill.status, 'in_station')
        
        # 检查库存
        inventory = Inventory.query.filter_by(
            product_id=self.product.id,
            location_id=self.location.id
        ).first()
        self.assertEqual(inventory.quantity, 1)
    
    def test_waybill_query(self):
        """测试运单查询"""
        # 先执行到件扫描
        self.test_scan_arrival()
        
        # 发送运单查询请求
        response = self.client.get(f'/express/waybill/query?waybill_no=1234567890')
        
        # 检查响应
        data = json.loads(response.data)
        self.assertEqual(data['success'], True)
        self.assertEqual(data['data']['waybill_no'], '1234567890')
    
    def test_inventory_status(self):
        """测试库存状态查询"""
        # 先执行到件扫描
        self.test_scan_arrival()
        
        # 发送库存状态查询请求
        response = self.client.get(f'/express/inventory/status?location_id={self.location.id}')
        
        # 检查响应
        data = json.loads(response.data)
        self.assertEqual(data['success'], True)
        self.assertGreater(len(data['data']), 0)
    
    def test_daily_checkout(self):
        """测试每日结账"""
        # 先执行到件扫描
        self.test_scan_arrival()
        
        # 发送每日结账请求
        response = self.client.post('/express/daily/checkout')
        
        # 检查响应
        data = json.loads(response.data)
        self.assertEqual(data['success'], True)
        
        # 检查运单状态
        waybill = Waybill.query.filter_by(waybill_no='1234567890').first()
        self.assertEqual(waybill.status, 'overnight')
    
    def test_batch_outbound(self):
        """测试批量出库"""
        # 先执行到件扫描
        self.test_scan_arrival()
        
        # 发送批量出库请求
        response = self.client.post('/express/batch/outbound', json={
            'waybill_nos': ['1234567890'],
            'location_id': self.location.id,
            'remark': '批量出库测试'
        })
        
        # 检查响应
        data = json.loads(response.data)
        self.assertEqual(data['success'], True)
    
    def test_no_waybill_outbound(self):
        """测试无单出库"""
        # 先执行到件扫描
        self.test_scan_arrival()
        
        # 发送无单出库请求
        response = self.client.post('/express/no-waybill/outbound', json={
            'product_id': self.product.id,
            'location_id': self.location.id,
            'quantity': 1,
            'remark': '无单出库测试'
        })
        
        # 检查响应
        data = json.loads(response.data)
        self.assertEqual(data['success'], True)
    
    def test_daily_inventory(self):
        """测试日终盘点"""
        # 先执行到件扫描
        self.test_scan_arrival()
        
        # 发送日终盘点请求
        response = self.client.post('/express/daily/inventory', json={
            'location_id': self.location.id,
            'actual_quantities': {'1234567890': 1}
        })
        
        # 检查响应
        data = json.loads(response.data)
        self.assertEqual(data['success'], True)


if __name__ == '__main__':
    unittest.main()