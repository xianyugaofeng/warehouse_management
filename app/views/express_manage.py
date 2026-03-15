from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from datetime import datetime
from app import db
from app.models.express import Waybill, ScanRecord, InventoryStatus
from app.models.inventory import Inventory, WarehouseLocation
from app.models.user import User
from app.utils.auth import permission_required
import logging

# 配置日志
logger = logging.getLogger(__name__)

express_bp = Blueprint('express', __name__)


# 扫描操作基础函数
def create_scan_record(waybill_no, scan_type, operator_id, location_id, batch_no=None, remark=None):
    """
    创建扫描记录并更新运单状态
    """
    # 查找运单
    waybill = Waybill.query.filter_by(waybill_no=waybill_no).first()
    if not waybill:
        return {'success': False, 'message': '运单不存在'}
    
    # 创建扫描记录
    scan_record = ScanRecord(
        waybill_id=waybill.id,
        scan_type=scan_type,
        operator_id=operator_id,
        location_id=location_id,
        batch_no=batch_no,
        remark=remark
    )
    db.session.add(scan_record)
    
    # 更新运单状态
    status_mapping = {
        'arrival': 'arrived_station',
        'departure': 'out_for_delivery',
        'delivery': 'delivered',
        'problem': 'problem',
        'return': 'in_station'
    }
    
    if scan_type in status_mapping:
        waybill.status = status_mapping[scan_type]
    
    # 处理特殊逻辑
    if scan_type == 'arrival':
        # 到件扫描：更新库位，增加库存
        waybill.location_id = location_id
        # 更新实物库存
        inventory = Inventory.query.filter_by(
            product_id=waybill.product_id,
            location_id=location_id,
            batch_no=batch_no
        ).first()
        if inventory:
            inventory.quantity += 1
        else:
            inventory = Inventory(
                product_id=waybill.product_id,
                location_id=location_id,
                quantity=1,
                batch_no=batch_no
            )
            db.session.add(inventory)
        
        # 创建库存状态
        inventory_status = InventoryStatus(
            location_id=location_id,
            waybill_id=waybill.id,
            status='normal'
        )
        db.session.add(inventory_status)
        
    elif scan_type == 'departure':
        # 派件扫描：更新快递员，减少库存
        waybill.courier_id = operator_id
        # 更新实物库存
        inventory = Inventory.query.filter_by(
            product_id=waybill.product_id,
            location_id=waybill.location_id,
            batch_no=batch_no
        ).first()
        if inventory and inventory.quantity > 0:
            inventory.quantity -= 1
        
        # 更新库存状态
        inventory_status = InventoryStatus.query.filter_by(
            waybill_id=waybill.id
        ).first()
        if inventory_status:
            db.session.delete(inventory_status)
        
    elif scan_type == 'problem':
        # 问题件扫描：更新库存状态
        inventory_status = InventoryStatus.query.filter_by(
            waybill_id=waybill.id
        ).first()
        if inventory_status:
            inventory_status.status = 'problem'
        else:
            inventory_status = InventoryStatus(
                location_id=location_id,
                waybill_id=waybill.id,
                status='problem'
            )
            db.session.add(inventory_status)
        
    elif scan_type == 'return':
        # 回流扫描：更新状态，增加库存
        waybill.location_id = location_id
        # 更新实物库存
        inventory = Inventory.query.filter_by(
            product_id=waybill.product_id,
            location_id=location_id,
            batch_no=batch_no
        ).first()
        if inventory:
            inventory.quantity += 1
        else:
            inventory = Inventory(
                product_id=waybill.product_id,
                location_id=location_id,
                quantity=1,
                batch_no=batch_no
            )
            db.session.add(inventory)
        
        # 更新库存状态
        inventory_status = InventoryStatus.query.filter_by(
            waybill_id=waybill.id
        ).first()
        if inventory_status:
            inventory_status.status = 'normal'
            inventory_status.location_id = location_id
        else:
            inventory_status = InventoryStatus(
                location_id=location_id,
                waybill_id=waybill.id,
                status='normal'
            )
            db.session.add(inventory_status)
    
    try:
        db.session.commit()
        return {'success': True, 'message': '扫描成功', 'waybill': waybill}
    except Exception as e:
        db.session.rollback()
        logger.error(f'扫描操作失败: {str(e)}')
        return {'success': False, 'message': f'扫描操作失败: {str(e)}'}


# 到件/卸车扫描
@express_bp.route('/scan/arrival', methods=['POST'])
@permission_required('inventory_manage')
@login_required
def scan_arrival():
    """
    到件/卸车扫描
    """
    waybill_no = request.json.get('waybill_no')
    location_id = request.json.get('location_id', type=int)
    batch_no = request.json.get('batch_no')
    remark = request.json.get('remark')
    
    if not waybill_no or not location_id:
        return jsonify({'success': False, 'message': '运单号和库位不能为空'})
    
    result = create_scan_record(
        waybill_no=waybill_no,
        scan_type='arrival',
        operator_id=request.user.id,
        location_id=location_id,
        batch_no=batch_no,
        remark=remark
    )
    
    return jsonify(result)


# 派件/出仓扫描
@express_bp.route('/scan/departure', methods=['POST'])
@permission_required('inventory_manage')
@login_required
def scan_departure():
    """
    派件/出仓扫描
    """
    waybill_no = request.json.get('waybill_no')
    location_id = request.json.get('location_id', type=int)
    batch_no = request.json.get('batch_no')
    remark = request.json.get('remark')
    
    if not waybill_no or not location_id:
        return jsonify({'success': False, 'message': '运单号和库位不能为空'})
    
    result = create_scan_record(
        waybill_no=waybill_no,
        scan_type='departure',
        operator_id=request.user.id,
        location_id=location_id,
        batch_no=batch_no,
        remark=remark
    )
    
    return jsonify(result)


# 签收扫描
@express_bp.route('/scan/delivery', methods=['POST'])
@permission_required('inventory_manage')
@login_required
def scan_delivery():
    """
    签收扫描
    """
    waybill_no = request.json.get('waybill_no')
    location_id = request.json.get('location_id', type=int)
    remark = request.json.get('remark')
    
    if not waybill_no or not location_id:
        return jsonify({'success': False, 'message': '运单号和库位不能为空'})
    
    result = create_scan_record(
        waybill_no=waybill_no,
        scan_type='delivery',
        operator_id=request.user.id,
        location_id=location_id,
        remark=remark
    )
    
    return jsonify(result)


# 问题件处理扫描
@express_bp.route('/scan/problem', methods=['POST'])
@permission_required('inventory_manage')
@login_required
def scan_problem():
    """
    问题件处理扫描
    """
    waybill_no = request.json.get('waybill_no')
    location_id = request.json.get('location_id', type=int)
    remark = request.json.get('remark')
    
    if not waybill_no or not location_id:
        return jsonify({'success': False, 'message': '运单号和库位不能为空'})
    
    result = create_scan_record(
        waybill_no=waybill_no,
        scan_type='problem',
        operator_id=request.user.id,
        location_id=location_id,
        remark=remark
    )
    
    return jsonify(result)


# 回流扫描
@express_bp.route('/scan/return', methods=['POST'])
@permission_required('inventory_manage')
@login_required
def scan_return():
    """
    回流扫描
    """
    waybill_no = request.json.get('waybill_no')
    location_id = request.json.get('location_id', type=int)
    batch_no = request.json.get('batch_no')
    remark = request.json.get('remark')
    
    if not waybill_no or not location_id:
        return jsonify({'success': False, 'message': '运单号和库位不能为空'})
    
    result = create_scan_record(
        waybill_no=waybill_no,
        scan_type='return',
        operator_id=request.user.id,
        location_id=location_id,
        batch_no=batch_no,
        remark=remark
    )
    
    return jsonify(result)


# 运单查询
@express_bp.route('/waybill/query', methods=['GET'])
@permission_required('inventory_manage')
@login_required
def waybill_query():
    """
    运单查询
    """
    waybill_no = request.args.get('waybill_no')
    if not waybill_no:
        return jsonify({'success': False, 'message': '运单号不能为空'})
    
    waybill = Waybill.query.filter_by(waybill_no=waybill_no).first()
    if not waybill:
        return jsonify({'success': False, 'message': '运单不存在'})
    
    # 获取扫描记录
    scan_records = waybill.scan_records.order_by(ScanRecord.scan_time.desc()).all()
    
    # 构建响应数据
    data = {
        'waybill_no': waybill.waybill_no,
        'status': waybill.status,
        'product_name': waybill.product.name if waybill.product else '未知商品',
        'location': waybill.location.code if waybill.location else '未知库位',
        'courier': waybill.courier.real_name if waybill.courier else '未分配',
        'create_time': waybill.create_time.strftime('%Y-%m-%d %H:%M:%S'),
        'update_time': waybill.update_time.strftime('%Y-%m-%d %H:%M:%S'),
        'scan_records': [
            {
                'scan_type': record.scan_type,
                'operator': record.operator.real_name if record.operator else '未知',
                'location': record.location.code if record.location else '未知',
                'scan_time': record.scan_time.strftime('%Y-%m-%d %H:%M:%S'),
                'batch_no': record.batch_no,
                'remark': record.remark
            }
            for record in scan_records
        ]
    }
    
    return jsonify({'success': True, 'data': data})


# 库存状态查询
@express_bp.route('/inventory/status', methods=['GET'])
@permission_required('inventory_manage')
@login_required
def inventory_status():
    """
    库存状态查询
    """
    location_id = request.args.get('location_id', type=int)
    status = request.args.get('status')
    
    query = InventoryStatus.query
    
    if location_id:
        query = query.filter_by(location_id=location_id)
    
    if status:
        query = query.filter_by(status=status)
    
    inventory_statuses = query.all()
    
    data = [
        {
            'waybill_no': status.waybill.waybill_no if status.waybill else '未知',
            'product_name': status.waybill.product.name if status.waybill and status.waybill.product else '未知商品',
            'location': status.location.code if status.location else '未知库位',
            'status': status.status,
            'update_time': status.update_time.strftime('%Y-%m-%d %H:%M:%S')
        }
        for status in inventory_statuses
    ]
    
    return jsonify({'success': True, 'data': data})


# 每日结账处理
@express_bp.route('/daily/checkout', methods=['POST'])
@permission_required('inventory_manage')
@login_required
def daily_checkout():
    """
    每日结账处理：将未出库包裹转入滞留库存
    """
    try:
        # 查找当日未出库的包裹
        today = datetime.now().date()
        waybills = Waybill.query.filter(
            Waybill.status.in_(['arrived_station', 'in_station']),
            db.func.date(Waybill.update_time) == today
        ).all()
        
        for waybill in waybills:
            # 更新为滞留件状态
            waybill.status = 'overnight'
            
            # 更新库存状态
            inventory_status = InventoryStatus.query.filter_by(
                waybill_id=waybill.id
            ).first()
            if inventory_status:
                inventory_status.status = 'overnight'
            else:
                inventory_status = InventoryStatus(
                    location_id=waybill.location_id,
                    waybill_id=waybill.id,
                    status='overnight'
                )
                db.session.add(inventory_status)
        
        db.session.commit()
        return jsonify({'success': True, 'message': f'每日结账完成，处理了{len(waybills)}件滞留件'})
    except Exception as e:
        db.session.rollback()
        logger.error(f'每日结账失败: {str(e)}')
        return jsonify({'success': False, 'message': f'每日结账失败: {str(e)}'})


# 批量出库
@express_bp.route('/batch/outbound', methods=['POST'])
@permission_required('inventory_manage')
@login_required
def batch_outbound():
    """
    批量出库（容差调整机制）
    """
    waybill_nos = request.json.get('waybill_nos', [])
    location_id = request.json.get('location_id', type=int)
    remark = request.json.get('remark')
    
    if not waybill_nos or not location_id:
        return jsonify({'success': False, 'message': '运单号列表和库位不能为空'})
    
    success_count = 0
    fail_count = 0
    fail_messages = []
    
    for waybill_no in waybill_nos:
        result = create_scan_record(
            waybill_no=waybill_no,
            scan_type='departure',
            operator_id=request.user.id,
            location_id=location_id,
            remark=remark
        )
        if result['success']:
            success_count += 1
        else:
            fail_count += 1
            fail_messages.append(f'{waybill_no}: {result['message']}')
    
    return jsonify({
        'success': True,
        'message': f'批量出库完成，成功{success_count}件，失败{fail_count}件',
        'fail_messages': fail_messages
    })


# 无单出库
@express_bp.route('/no-waybill/outbound', methods=['POST'])
@permission_required('inventory_manage')
@login_required
def no_waybill_outbound():
    """
    无单出库（容差调整机制）
    """
    product_id = request.json.get('product_id', type=int)
    location_id = request.json.get('location_id', type=int)
    quantity = request.json.get('quantity', type=int, default=1)
    remark = request.json.get('remark')
    
    if not product_id or not location_id or quantity <= 0:
        return jsonify({'success': False, 'message': '商品ID、库位和数量不能为空，且数量必须大于0'})
    
    try:
        # 查找库存
        inventory = Inventory.query.filter_by(
            product_id=product_id,
            location_id=location_id
        ).first()
        
        if not inventory or inventory.quantity < quantity:
            return jsonify({'success': False, 'message': '库存不足'})
        
        # 减少库存
        inventory.quantity -= quantity
        
        # 创建扫描记录（无运单）
        # 这里可以根据实际需求进行调整
        
        db.session.commit()
        return jsonify({'success': True, 'message': f'无单出库成功，数量：{quantity}'})
    except Exception as e:
        db.session.rollback()
        logger.error(f'无单出库失败: {str(e)}')
        return jsonify({'success': False, 'message': f'无单出库失败: {str(e)}'})


# 日终盘点
@express_bp.route('/daily/inventory', methods=['POST'])
@permission_required('inventory_manage')
@login_required
def daily_inventory():
    """
    日终盘点
    """
    location_id = request.json.get('location_id', type=int)
    actual_quantities = request.json.get('actual_quantities', {})  # 格式: {waybill_no: quantity}
    
    if not location_id or not actual_quantities:
        return jsonify({'success': False, 'message': '库位和实际数量不能为空'})
    
    adjustment_count = 0
    adjustment_details = []
    
    try:
        for waybill_no, actual_quantity in actual_quantities.items():
            # 查找运单
            waybill = Waybill.query.filter_by(waybill_no=waybill_no).first()
            if not waybill:
                adjustment_details.append(f'{waybill_no}: 运单不存在')
                continue
            
            # 查找库存
            inventory = Inventory.query.filter_by(
                product_id=waybill.product_id,
                location_id=location_id
            ).first()
            
            if inventory:
                # 调整库存
                inventory.quantity = actual_quantity
                adjustment_count += 1
                adjustment_details.append(f'{waybill_no}: 调整至{actual_quantity}件')
        
        db.session.commit()
        return jsonify({
            'success': True,
            'message': f'日终盘点完成，调整了{adjustment_count}件库存',
            'details': adjustment_details
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f'日终盘点失败: {str(e)}')
        return jsonify({'success': False, 'message': f'日终盘点失败: {str(e)}'})


# 快递站管理首页
@express_bp.route('/dashboard')
@permission_required('inventory_manage')
@login_required
def dashboard():
    """
    快递站管理首页
    """
    # 获取统计数据
    total_waybills = Waybill.query.count()
    today_arrival = Waybill.query.filter(
        Waybill.status.in_(['arrived_station', 'in_station']),
        db.func.date(Waybill.update_time) == datetime.now().date()
    ).count()
    today_departure = Waybill.query.filter(
        Waybill.status == 'out_for_delivery',
        db.func.date(Waybill.update_time) == datetime.now().date()
    ).count()
    problem_count = Waybill.query.filter_by(status='problem').count()
    overnight_count = Waybill.query.filter_by(status='overnight').count()
    
    # 获取今日扫描记录
    today = datetime.now().date()
    today_scans = ScanRecord.query.filter(
        db.func.date(ScanRecord.scan_time) == today
    ).order_by(ScanRecord.scan_time.desc()).limit(10).all()
    
    # 获取库位列表
    locations = WarehouseLocation.query.filter_by(status=True).all()
    
    return render_template('express/dashboard.html',
                           total_waybills=total_waybills,
                           today_arrival=today_arrival,
                           today_departure=today_departure,
                           problem_count=problem_count,
                           overnight_count=overnight_count,
                           today_scans=today_scans,
                           locations=locations)


# 到件扫描页面
@express_bp.route('/scan/arrival/page')
@permission_required('inventory_manage')
@login_required
def scan_arrival_page():
    """
    到件扫描页面
    """
    locations = WarehouseLocation.query.filter_by(status=True).all()
    return render_template('express/scan_arrival.html', locations=locations)

# 派件扫描页面
@express_bp.route('/scan/departure/page')
@permission_required('inventory_manage')
@login_required
def scan_departure_page():
    """
    派件扫描页面
    """
    locations = WarehouseLocation.query.filter_by(status=True).all()
    return render_template('express/scan_departure.html', locations=locations)

# 签收扫描页面
@express_bp.route('/scan/delivery/page')
@permission_required('inventory_manage')
@login_required
def scan_delivery_page():
    """
    签收扫描页面
    """
    locations = WarehouseLocation.query.filter_by(status=True).all()
    return render_template('express/scan_delivery.html', locations=locations)

# 问题件处理页面
@express_bp.route('/scan/problem/page')
@permission_required('inventory_manage')
@login_required
def scan_problem_page():
    """
    问题件处理页面
    """
    locations = WarehouseLocation.query.filter_by(status=True).all()
    return render_template('express/scan_problem.html', locations=locations)

# 回流扫描页面
@express_bp.route('/scan/return/page')
@permission_required('inventory_manage')
@login_required
def scan_return_page():
    """
    回流扫描页面
    """
    locations = WarehouseLocation.query.filter_by(status=True).all()
    return render_template('express/scan_return.html', locations=locations)

# 运单查询页面
@express_bp.route('/waybill/query/page')
@permission_required('inventory_manage')
@login_required
def waybill_query_page():
    """
    运单查询页面
    """
    return render_template('express/waybill_query.html')

# 库存状态查询页面
@express_bp.route('/inventory/status/page')
@permission_required('inventory_manage')
@login_required
def inventory_status_page():
    """
    库存状态查询页面
    """
    locations = WarehouseLocation.query.filter_by(status=True).all()
    return render_template('express/inventory_status.html', locations=locations)

# 每日结账页面
@express_bp.route('/daily/checkout/page')
@permission_required('inventory_manage')
@login_required
def daily_checkout_page():
    """
    每日结账页面
    """
    return render_template('express/daily_checkout.html')

# 批量出库页面
@express_bp.route('/batch/outbound/page')
@permission_required('inventory_manage')
@login_required
def batch_outbound_page():
    """
    批量出库页面
    """
    locations = WarehouseLocation.query.filter_by(status=True).all()
    return render_template('express/batch_outbound.html', locations=locations)

# 无单出库页面
@express_bp.route('/no-waybill/outbound/page')
@permission_required('inventory_manage')
@login_required
def no_waybill_outbound_page():
    """
    无单出库页面
    """
    locations = WarehouseLocation.query.filter_by(status=True).all()
    products = Product.query.all()
    return render_template('express/no_waybill_outbound.html', locations=locations, products=products)

# 日终盘点页面
@express_bp.route('/daily/inventory/page')
@permission_required('inventory_manage')
@login_required
def daily_inventory_page():
    """
    日终盘点页面
    """
    locations = WarehouseLocation.query.filter_by(status=True).all()
    return render_template('express/daily_inventory.html', locations=locations)