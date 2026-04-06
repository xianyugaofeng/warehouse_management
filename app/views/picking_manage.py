"""
拣货单管理模块
核心功能: 拣货执行、库位转移（normal→picking）、库存解锁、拣货完成

关键业务流程:
1. 根据分配单创建拣货单
2. 执行库位转移：从normal库位 → picking库位
3. 创建库存变更日志记录转移过程
4. 拣货完成后解除库存锁定
5. 更新销售单为"已拣货"状态

API 端点:
- GET /picking/list - 拣货单列表
- POST /picking/create/<int:allocation_order_id> - 创建拣货单
- GET /picking/detail/<int:id> - 拣货单详情
- POST /picking/detail/<int:id>/item/<int:item_id>/complete - 完成单个拣货项
- POST /picking/detail/<int:id>/complete - 完成整个拣货单
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from app.models.allocation import AllocationOrder, AllocationItem
from app.models.picking import PickingOrder, PickingItem
from app.models.sales import SalesOrder
from app.models.inventory import Inventory, WarehouseLocation, InventoryChangeLog
from app.models.user import User
from app.utils.auth import permission_required
from app.utils.helpers import generate_picking_order_no

picking_bp = Blueprint('picking', __name__)


# ==================== 拣货单列表 ====================

@picking_bp.route('/list')
@permission_required('inventory_manage')
@login_required
def list_pickings():
    """拣货单列表"""
    status = request.args.get('status', '')
    keyword = request.args.get('keyword', '')
    
    query = PickingOrder.query
    
    if status:
        query = query.filter(PickingOrder.status == status)
    if keyword:
        query = query.filter(
            PickingOrder.picking_no.ilike(f'%{keyword}%') |
            PickingOrder.sales_order.has(SalesOrder.order_no.ilike(f'%{keyword}%'))
        )
    
    page = request.args.get('page', 1, type=int)
    pagination = query.order_by(PickingOrder.create_time.desc()).paginate(page=page, per_page=10)
    
    return render_template('picking/list.html',
                         pickings=pagination.items,
                         pagination=pagination,
                         status=status,
                         keyword=keyword)


# ==================== 创建拣货单 ====================

@picking_bp.route('/create/<int:allocation_order_id>', methods=['GET', 'POST'])
@permission_required('inventory_manage')
@login_required
def create_picking(allocation_order_id):
    """创建拣货单"""
    allocation_order = AllocationOrder.query.get_or_404(allocation_order_id)
    sales_order = allocation_order.sales_order
    
    # 检查分配单状态
    if allocation_order.status != 'completed':
        flash('只能为已完成的分配单创建拣货单', 'danger')
        return redirect(url_for('allocation.detail_allocation', id=allocation_order_id))
    
    if request.method == 'POST':
        try:
            # 获取拣货区库位（一般为"picked"类型的库位）
            picking_location_id = int(request.form.get('picking_location_id'))
            picking_location = WarehouseLocation.query.get_or_404(picking_location_id)
            
            # 创建拣货单
            picking_order = PickingOrder(
                picking_no=generate_picking_order_no(),
                allocation_order_id=allocation_order.id,
                sales_order_id=sales_order.id,
                warehouse_id=sales_order.warehouse_id,
                picking_location_id=picking_location_id,
                warehouse_staff_id=current_user.id,
                status='pending'
            )
            db.session.add(picking_order)
            db.session.flush()
            
            # 为分配单中的每一项创建拣货项
            for alloc_item in allocation_order.items.all():
                inventory = alloc_item.inventory
                source_location = inventory.location
                
                # 创建拣货项
                picking_item = PickingItem(
                    picking_id=picking_order.id,
                    allocation_item_id=alloc_item.id,
                    inventory_id=inventory.id,
                    picked_qty=alloc_item.allocated_qty,
                    source_location_id=source_location.id,
                    target_location_id=picking_location.id,
                    snapshot_quantity=inventory.quantity,
                    snapshot_locked=inventory.locked_quantity,
                    status='pending'
                )
                db.session.add(picking_item)
            
            db.session.commit()
            flash(f'拣货单 {picking_order.picking_no} 创建成功', 'success')
            return redirect(url_for('picking.detail_picking', id=picking_order.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'创建拣货单失败: {str(e)}', 'danger')
    
    # GET 请求：展示创建表单
    # 获取可用的拣货区库位
    picking_locations = WarehouseLocation.query.filter_by(
        status=True, 
        location_type='picking'
    ).all()
    
    if not picking_locations:
        flash('系统中没有拣货区库位，请先创建', 'warning')
        return redirect(url_for('allocation.detail_allocation', id=allocation_order_id))
    
    return render_template('picking/create.html',
                         allocation_order=allocation_order,
                         sales_order=sales_order,
                         picking_locations=picking_locations)


# ==================== 拣货单详情 ====================

@picking_bp.route('/detail/<int:id>')
@permission_required('inventory_manage')
@login_required
def detail_picking(id):
    """拣货单详情"""
    picking_order = PickingOrder.query.get_or_404(id)
    items = picking_order.items.all()
    
    return render_template('picking/detail.html',
                         picking_order=picking_order,
                         items=items)


# ==================== 执行拣货项 ====================

@picking_bp.route('/detail/<int:id>/item/<int:item_id>/complete', methods=['POST'])
@permission_required('inventory_manage')
@login_required
def complete_picking_item(id, item_id):
    """完成单个拣货项（库位转移）"""
    picking_order = PickingOrder.query.get_or_404(id)
    picking_item = PickingItem.query.get_or_404(item_id)
    
    if picking_item.picking_id != picking_order.id:
        flash('拣货项不匹配', 'danger')
        return redirect(url_for('picking.detail_picking', id=id))
    
    if picking_item.status == 'completed':
        flash('该拣货项已完成', 'warning')
        return redirect(url_for('picking.detail_picking', id=id))
    
    try:
        inventory = picking_item.inventory
        
        # 验证库存是否未改变（快照验证）
        if inventory.quantity != picking_item.snapshot_quantity:
            flash(f'库存已改变，无法完成拣货。当前库存：{inventory.quantity}，快照库存：{picking_item.snapshot_quantity}', 'danger')
            return redirect(url_for('picking.detail_picking', id=id))
        
        # 检查库位是否仍为源库位
        if inventory.location_id != picking_item.source_location_id:
            flash('商品库位已改变，无法完成拣货', 'danger')
            return redirect(url_for('picking.detail_picking', id=id))
        
        # 执行库位转移（创建新库存记录在目标库位）
        target_inventory = Inventory.query.filter_by(
            product_id=inventory.product_id,
            location_id=picking_item.target_location_id,
            batch_no=inventory.batch_no
        ).first()
        
        if not target_inventory:
            # 创建目标库位的库存记录
            target_inventory = Inventory(
                product_id=inventory.product_id,
                location_id=picking_item.target_location_id,
                batch_no=inventory.batch_no,
                production_date=inventory.production_date,
                expire_date=inventory.expire_date,
                supplier_batch_no=inventory.supplier_batch_no,
                quantity=0
            )
            db.session.add(target_inventory)
        
        # 从源库位减少库存（不改变物理数量，只转移库位）
        inventory.quantity -= picking_item.picked_qty
        
        # 到目标库位增加库存
        target_inventory.quantity += picking_item.picked_qty
        
        # 解锁源库位库存的锁定数量
        inventory.unlock_quantity(picking_item.picked_qty)
        
        # 更新拣货项
        picking_item.status = 'completed'
        picking_item.completed_time = datetime.utcnow()
        
        # 记录库位转移的变更日志
        log = InventoryChangeLog(
            inventory_id=inventory.id,
            change_type='location_transfer',
            quantity_before=inventory.quantity + picking_item.picked_qty,
            quantity_after=inventory.quantity,
            locked_quantity_before=inventory.locked_quantity + picking_item.picked_qty,
            locked_quantity_after=inventory.locked_quantity,
            frozen_quantity_before=inventory.frozen_quantity,
            frozen_quantity_after=inventory.frozen_quantity,
            operator=current_user.username,
            reason=f'拣货单 {picking_order.picking_no} 库位转移',
            reference_id=picking_order.id,
            reference_type='picking_order'
        )
        db.session.add(log)
        picking_item.change_log_id = log.id
        
        # 更新拣货单总数
        picking_order.total_picked_qty += picking_item.picked_qty
        
        db.session.commit()
        flash(f'拣货项已完成，已转移 {picking_item.picked_qty} 件', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'拣货失败: {str(e)}', 'danger')
    
    return redirect(url_for('picking.detail_picking', id=id))


# ==================== 完成拣货单 ====================

@picking_bp.route('/detail/<int:id>/complete', methods=['POST'])
@permission_required('inventory_manage')
@login_required
def complete_picking(id):
    """完成整个拣货单"""
    picking_order = PickingOrder.query.get_or_404(id)
    
    if picking_order.status == 'completed':
        flash('拣货单已完成', 'warning')
        return redirect(url_for('picking.detail_picking', id=id))
    
    # 检查所有拣货项是否已完成
    if not picking_order.can_complete():
        flash('还有未完成的拣货项', 'danger')
        return redirect(url_for('picking.detail_picking', id=id))
    
    try:
        picking_order.status = 'completed'
        picking_order.completed_time = datetime.utcnow()
        picking_order.manager_id = current_user.id
        
        # 更新销售单状态
        sales_order = picking_order.sales_order
        if sales_order:
            sales_order.status = 'picked'
            sales_order.picked_quantity = picking_order.total_picked_qty
        
        # 更新分配单状态
        allocation_order = picking_order.allocation_order
        if allocation_order:
            allocation_order.status = 'completed'
        
        db.session.commit()
        flash('拣货单已完成', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'完成拣货失败: {str(e)}', 'danger')
    
    return redirect(url_for('picking.detail_picking', id=id))


# ==================== API 端点 ====================

@picking_bp.route('/api/picking/<int:id>/status')
@login_required
def api_picking_status(id):
    """获取拣货单状态 API"""
    picking_order = PickingOrder.query.get_or_404(id)
    items = picking_order.items.all()
    
    items_data = []
    for item in items:
        product = item.inventory.product if item.inventory else None
        items_data.append({
            'id': item.id,
            'product_name': product.name if product else 'Unknown',
            'picked_qty': item.picked_qty,
            'status': item.status,
            'source_location': item.source_location.name if item.source_location else '',
            'target_location': item.target_location.name if item.target_location else ''
        })
    
    return jsonify({
        'picking_no': picking_order.picking_no,
        'status': picking_order.status,
        'total_picked': picking_order.total_picked_qty,
        'items': items_data,
        'can_complete': picking_order.can_complete()
    })
