"""
出库单管理模块（货运单 ShippingOrder）
核心功能: 最终出库执行、库存扣减、库位清理、部分出库支持

关键业务流程:
1. 由复核单（inspection_order）触发自动创建或手工创建出库单
2. 支持部分出库，自动更新剩余可出库数量
3. 出库时扣减拣货区库存
4. 库存为0时自动删除库存记录，标记库位为"空闲"
5. 生成完整的库存变更日志用于审计

API 端点:
- GET /shipping/list - 出库单列表
- POST /shipping/create/<int:inspection_order_id> - 创建出库单
- GET /shipping/detail/<int:id> - 出库单详情
- POST /shipping/detail/<int:id>/item/<int:item_id>/ship - 出库单个商品
- POST /shipping/detail/<int:id>/complete - 完成出库单
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from app.models.sales import SalesOrder
from app.models.inspection import InspectionOrder
from app.models.picking import PickingOrder, PickingItem
from app.models.outbound import ShippingOrder, ShippingItem
from app.models.inventory import Inventory, WarehouseLocation, InventoryChangeLog
from app.models.user import User
from app.utils.auth import permission_required
from app.utils.helpers import generate_shipping_order_no

shipping_bp = Blueprint('shipping', __name__)


# ==================== 出库单列表 ====================

@shipping_bp.route('/list')
@permission_required('inventory_manage')
@login_required
def list_shipping():
    """出库单列表"""
    status = request.args.get('status', '')
    keyword = request.args.get('keyword', '')
    
    query = ShippingOrder.query
    
    if status:
        query = query.filter(ShippingOrder.status == status)
    if keyword:
        query = query.filter(
            ShippingOrder.shipping_no.ilike(f'%{keyword}%') |
            ShippingOrder.sales_order.has(SalesOrder.order_no.ilike(f'%{keyword}%'))
        )
    
    page = request.args.get('page', 1, type=int)
    pagination = query.order_by(ShippingOrder.create_time.desc()).paginate(page=page, per_page=10)
    
    return render_template('shipping/list.html',
                         shippings=pagination.items,
                         pagination=pagination,
                         status=status,
                         keyword=keyword)


# ==================== 创建出库单 ====================

@shipping_bp.route('/create/<int:inspection_order_id>', methods=['GET', 'POST'])
@permission_required('inventory_manage')
@login_required
def create_shipping(inspection_order_id):
    """创建出库单"""
    inspection_order = InspectionOrder.query.get_or_404(inspection_order_id)
    
    # 检查检验单类型与状态
    if not inspection_order.is_outbound():
        flash('只能为出库检验单创建出库单', 'danger')
        return redirect(url_for('inspection.detail_inspection', id=inspection_order_id))
    
    if inspection_order.status != 'passed':
        flash('只能为复核通过的检验单创建出库单', 'danger')
        return redirect(url_for('inspection.detail_inspection', id=inspection_order_id))
    
    sales_order = inspection_order.sales_order
    picking_order = inspection_order.picking_order
    
    if not sales_order or not picking_order:
        flash('检验单关联信息不完整', 'danger')
        return redirect(url_for('inspection.detail_inspection', id=inspection_order_id))
    
    if request.method == 'POST':
        try:
            # 获取收货信息
            receiver = request.form.get('receiver')
            receiver_phone = request.form.get('receiver_phone', '')
            receiver_address = request.form.get('receiver_address', '')
            purpose = request.form.get('purpose', '')
            remark = request.form.get('remark', '')
            
            if not receiver:
                flash('请填写收货人信息', 'danger')
                return redirect(url_for('shipping.create_shipping', inspection_order_id=inspection_order_id))
            
            # 计算出库总数量
            total_qty = 0
            for picking_item in picking_order.items.all():
                if picking_item.status == 'completed':
                    total_qty += picking_item.picked_qty
            
            # 创建出库单
            shipping_order = ShippingOrder(
                shipping_no=generate_shipping_order_no(),
                inspection_order_id=inspection_order.id,
                sales_order_id=sales_order.id,
                picking_order_id=picking_order.id,
                receiver=receiver,
                receiver_phone=receiver_phone,
                receiver_address=receiver_address,
                purpose=purpose,
                remark=remark,
                operator_id=current_user.id,
                total_quantity=total_qty,
                remaining_quantity=total_qty,
                outbound_date=datetime.utcnow().date(),
                status='pending'
            )
            db.session.add(shipping_order)
            db.session.flush()
            
            # 为拣货单中的每一项创建出库单明细
            for picking_item in picking_order.items.all():
                if picking_item.status != 'completed':
                    continue
                
                # 获取拣货区的库存
                picking_location = picking_order.picking_location
                target_inventory = Inventory.query.filter_by(
                    product_id=picking_item.inventory.product_id,
                    location_id=picking_location.id,
                    batch_no=picking_item.inventory.batch_no
                ).first()
                
                if not target_inventory:
                    flash(f'拣货区库存缺失，无法创建出库单', 'danger')
                    db.session.rollback()
                    return redirect(url_for('shipping.create_shipping', inspection_order_id=inspection_order_id))
                
                # 创建出库单明细
                shipping_item = ShippingItem(
                    shipping_id=shipping_order.id,
                    picking_item_id=picking_item.id,
                    inventory_id=target_inventory.id,
                    location_id=picking_location.id,
                    product_id=picking_item.inventory.product_id,
                    planned_quantity=picking_item.picked_qty,
                    remaining_quantity=picking_item.picked_qty,
                    snapshot_quantity=target_inventory.quantity
                )
                db.session.add(shipping_item)
            
            db.session.commit()
            flash(f'出库单 {shipping_order.shipping_no} 创建成功', 'success')
            return redirect(url_for('shipping.detail_shipping', id=shipping_order.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'创建出库单失败: {str(e)}', 'danger')
    
    # GET 请求：展示创建表单
    # 获取客户信息作为默认收货人
    default_receiver = sales_order.customer.name if sales_order.customer else ''
    
    return render_template('shipping/create.html',
                         inspection_order=inspection_order,
                         sales_order=sales_order,
                         picking_order=picking_order,
                         default_receiver=default_receiver)


# ==================== 出库单详情 ====================

@shipping_bp.route('/detail/<int:id>')
@permission_required('inventory_manage')
@login_required
def detail_shipping(id):
    """出库单详情"""
    shipping_order = ShippingOrder.query.get_or_404(id)
    items = shipping_order.items.all()
    
    return render_template('shipping/detail.html',
                         shipping_order=shipping_order,
                         items=items)


# ==================== 执行单个出库项 ====================

@shipping_bp.route('/detail/<int:id>/item/<int:item_id>/ship', methods=['POST'])
@permission_required('inventory_manage')
@login_required
def ship_item(id, item_id):
    """出库单个商品（支持部分出库）"""
    shipping_order = ShippingOrder.query.get_or_404(id)
    shipping_item = ShippingItem.query.get_or_404(item_id)
    
    if shipping_item.shipping_id != shipping_order.id:
        flash('出库项不匹配', 'danger')
        return redirect(url_for('shipping.detail_shipping', id=id))
    
    try:
        # 获取出库数量（支持部分出库）
        ship_qty = int(request.form.get('ship_qty', shipping_item.remaining_quantity))
        
        # 验证出库数量
        if ship_qty <= 0 or ship_qty > shipping_item.remaining_quantity:
            flash('出库数量无效', 'danger')
            return redirect(url_for('shipping.detail_shipping', id=id))
        
        inventory = shipping_item.inventory
        
        # 检查库存是否充足
        if inventory.quantity < ship_qty:
            flash(f'库存不足。库存量: {inventory.quantity}, 出库数: {ship_qty}', 'danger')
            return redirect(url_for('shipping.detail_shipping', id=id))
        
        # 扣减库存
        inventory.quantity -= ship_qty
        shipping_item.shipped_quantity += ship_qty
        shipping_item.remaining_quantity -= ship_qty
        
        # 更新出库单数据
        shipping_order.shipped_quantity += ship_qty
        shipping_order.remaining_quantity -= ship_qty
        
        if shipping_order.remaining_quantity > 0:
            shipping_order.status = 'partialShipped'
        elif shipping_order.remaining_quantity == 0:
            shipping_order.status = 'completed'
            shipping_order.completed_time = datetime.utcnow()
        
        # 记录库存变更日志
        log = InventoryChangeLog(
            inventory_id=inventory.id,
            change_type='outbound',
            quantity_before=inventory.quantity + ship_qty,
            quantity_after=inventory.quantity,
            locked_quantity_before=inventory.locked_quantity,
            locked_quantity_after=inventory.locked_quantity,
            frozen_quantity_before=inventory.frozen_quantity,
            frozen_quantity_after=inventory.frozen_quantity,
            operator=current_user.username,
            reason=f'出库单 {shipping_order.shipping_no} 出库',
            reference_id=shipping_order.id,
            reference_type='shipping_order'
        )
        db.session.add(log)
        shipping_item.change_log_id = log.id
        
        # 如果库存为0，删除库存记录，标记库位为空闲
        if inventory.quantity == 0:
            # 检查该库位是否还有其他商品
            other_inventories = Inventory.query.filter(
                Inventory.location_id == inventory.location_id,
                Inventory.id != inventory.id
            ).count()
            
            if other_inventories == 0:
                # 库位已空，删除库存记录
                db.session.delete(inventory)
        
        db.session.commit()
        flash(f'已出库 {ship_qty} 件', 'success')
        
        # 检查是否整单出库完成
        if shipping_order.status == 'completed':
            # 更新销售单状态
            sales_order = shipping_order.sales_order
            if sales_order:
                sales_order.status = 'shipped'
                sales_order.shipped_quantity = sales_order.total_quantity
            flash('出库单已完成，销售单已标记为已出库', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'出库失败: {str(e)}', 'danger')
    
    return redirect(url_for('shipping.detail_shipping', id=id))


# ==================== 完成出库单 ====================

@shipping_bp.route('/detail/<int:id>/complete', methods=['POST'])
@permission_required('inventory_manage')
@login_required
def complete_shipping(id):
    """完成出库单"""
    shipping_order = ShippingOrder.query.get_or_404(id)
    
    if shipping_order.status == 'completed':
        flash('出库单已完成', 'warning')
        return redirect(url_for('shipping.detail_shipping', id=id))
    
    # 检查是否全部出库
    if shipping_order.remaining_quantity > 0:
        flash('还有部分商品未出库', 'danger')
        return redirect(url_for('shipping.detail_shipping', id=id))
    
    try:
        shipping_order.status = 'completed'
        shipping_order.completed_time = datetime.utcnow()
        shipping_order.approver_id = current_user.id
        shipping_order.approved_time = datetime.utcnow()
        
        # 更新销售单状态
        sales_order = shipping_order.sales_order
        if sales_order:
            sales_order.status = 'shipped'
            sales_order.shipped_quantity = sales_order.total_quantity
        
        db.session.commit()
        flash('出库单已完成', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'完成出库失败: {str(e)}', 'danger')
    
    return redirect(url_for('shipping.detail_shipping', id=id))


# ==================== API 端点 ====================

@shipping_bp.route('/api/shipping/<int:id>/status')
@login_required
def api_shipping_status(id):
    """获取出库单状态 API"""
    shipping_order = ShippingOrder.query.get_or_404(id)
    items = shipping_order.items.all()
    
    items_data = []
    for item in items:
        product = item.product
        items_data.append({
            'id': item.id,
            'product_name': product.name if product else 'Unknown',
            'product_code': product.code if product else '',
            'planned_qty': item.planned_quantity,
            'shipped_qty': item.shipped_quantity,
            'remaining_qty': item.remaining_quantity,
            'location': item.location.name if item.location else ''
        })
    
    return jsonify({
        'shipping_no': shipping_order.shipping_no,
        'status': shipping_order.status,
        'total_qty': shipping_order.total_quantity,
        'shipped_qty': shipping_order.shipped_quantity,
        'remaining_qty': shipping_order.remaining_quantity,
        'receiver': shipping_order.receiver,
        'items': items_data
    })
