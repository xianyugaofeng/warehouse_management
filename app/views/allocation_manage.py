"""
分配单管理模块
核心功能: 库存验证、库存分配（FIFO/近期过期）、库存锁定、分配单审批

关键业务规则:
1. 分配前验证库存可用量 >= 销售单需求量
2. 库存分配策略: FIFO(按生产日期) 或 临近过期优先
3. 分配后自动锁定相应库存数量
4. 支持部分分配（库存不足可进行部分分配并预警）

API 端点:
- GET /allocation/list - 分配单列表
- POST /allocation/create/<int:sales_order_id> - 创建分配单
- GET /allocation/detail/<int:id> - 分配单详情
- POST /allocation/detail/<int:id>/approve - 审批分配单
- POST /allocation/detail/<int:id>/reject - 拒绝分配单
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from sqlalchemy import and_, or_
from app import db
from app.models.sales import SalesOrder, SalesOrderItem
from app.models.allocation import AllocationOrder, AllocationItem
from app.models.inventory import Inventory, WarehouseLocation, InventoryChangeLog
from app.models.product import Product
from app.models.user import User
from app.utils.auth import permission_required
from app.utils.helpers import generate_allocation_order_no

allocation_bp = Blueprint('allocation', __name__)


# ==================== 库存分配策略 ====================

def allocate_by_fifo(product_id, location_id, required_qty, preferred_batch_no=None):
    """
    FIFO分配策略：按生产日期升序排列
    优先分配生产日期最早的库存
    """
    query = Inventory.query.filter(
        Inventory.product_id == product_id,
        Inventory.location_id == location_id,
        Inventory.available_quantity > 0,
        Inventory.location.has(location_type='normal')
    )
    
    # 如果指定了批次号，优先使用指定批次
    if preferred_batch_no:
        preferred = query.filter(Inventory.batch_no == preferred_batch_no).first()
        if preferred and preferred.available_quantity >= required_qty:
            return [(preferred, required_qty)]
    
    # 按生产日期排序（FIFO）
    inventories = query.order_by(
        Inventory.production_date.asc().nullslast(),
        Inventory.create_time.asc()
    ).all()
    
    result = []
    remaining = required_qty
    
    for inv in inventories:
        if remaining <= 0:
            break
        
        allocate_qty = min(inv.available_quantity, remaining)
        result.append((inv, allocate_qty))
        remaining -= allocate_qty
    
    return result if remaining == 0 else None  # 返回None表示库存不足


def allocate_by_near_expiry(product_id, location_id, required_qty, preferred_batch_no=None):
    """
    近期过期优先分配策略：按过期日期升序排列
    优先分配快要过期的库存，防止过期损失
    """
    query = Inventory.query.filter(
        Inventory.product_id == product_id,
        Inventory.location_id == location_id,
        Inventory.available_quantity > 0,
        Inventory.location.has(location_type='normal')
    )
    
    # 如果指定了批次号，优先使用指定批次
    if preferred_batch_no:
        preferred = query.filter(Inventory.batch_no == preferred_batch_no).first()
        if preferred and preferred.available_quantity >= required_qty:
            return [(preferred, required_qty)]
    
    # 按过期日期排序（近期优先）
    inventories = query.order_by(
        Inventory.expire_date.asc().nullslast(),
        Inventory.production_date.asc().nullslast()
    ).all()
    
    result = []
    remaining = required_qty
    
    for inv in inventories:
        if remaining <= 0:
            break
        
        allocate_qty = min(inv.available_quantity, remaining)
        result.append((inv, allocate_qty))
        remaining -= allocate_qty
    
    return result if remaining == 0 else None  # 返回None表示库存不足


def validate_allocation(sales_order):
    """
    验证销售单是否可以进行分配
    返回: (can_allocate: bool, missing_details: list, message: str)
    """
    missing_details = []
    
    for item in sales_order.items.all():
        available_qty = db.session.query(
            db.func.sum(Inventory.available_quantity)
        ).filter(
            Inventory.product_id == item.product_id
        ).scalar() or 0
        
        if available_qty < item.quantity:
            missing_details.append({
                'product_id': item.product_id,
                'product_name': item.product.name,
                'product_code': item.product.code,
                'required_qty': item.quantity,
                'available_qty': available_qty,
                'shortage': item.quantity - available_qty
            })
    
    if missing_details:
        shortage_info = '；'.join([f"{d['product_name']}缺少{d['shortage']}件" for d in missing_details])
        message = f"库存不足，无法完成分配。{shortage_info}"
        return False, missing_details, message
    
    return True, [], "库存充足，可以分配"


# ==================== 分配单列表 ====================

@allocation_bp.route('/list')
@permission_required('inventory_manage')
@login_required
def list_allocations():
    """分配单列表"""
    status = request.args.get('status', '')
    strategy = request.args.get('strategy', '')
    keyword = request.args.get('keyword', '')
    
    query = AllocationOrder.query
    
    if status:
        query = query.filter(AllocationOrder.status == status)
    if strategy:
        query = query.filter(AllocationOrder.allocation_strategy == strategy)
    if keyword:
        query = query.filter(
            AllocationOrder.allocation_no.ilike(f'%{keyword}%') |
            AllocationOrder.sales_order.has(SalesOrder.order_no.ilike(f'%{keyword}%'))
        )
    
    page = request.args.get('page', 1, type=int)
    pagination = query.order_by(AllocationOrder.create_time.desc()).paginate(page=page, per_page=10)
    
    return render_template('allocation/list.html',
                         allocations=pagination.items,
                         pagination=pagination,
                         status=status,
                         strategy=strategy,
                         keyword=keyword)


# ==================== 创建分配单 ====================

@allocation_bp.route('/create/<int:sales_order_id>', methods=['GET', 'POST'])
@permission_required('inventory_manage')
@login_required
def create_allocation(sales_order_id):
    """创建分配单"""
    sales_order = SalesOrder.query.get_or_404(sales_order_id)
    
    # 检查销售单状态
    if not sales_order.can_allocate():
        flash('销售单状态不允许分配', 'danger')
        return redirect(url_for('sales.detail_sales', id=sales_order_id))
    
    if request.method == 'POST':
        try:
            allocation_strategy = request.form.get('allocation_strategy', 'fifo')
            remark = request.form.get('remark', '')
            
            # 验证库存
            can_allocate, missing, message = validate_allocation(sales_order)
            if not can_allocate:
                flash(message, 'danger')
                return redirect(url_for('allocation.create_allocation', sales_order_id=sales_order_id))
            
            # 创建分配单
            allocation_order = AllocationOrder(
                allocation_no=generate_allocation_order_no(),
                sales_order_id=sales_order.id,
                allocation_strategy=allocation_strategy,
                operator_id=current_user.id,
                remark=remark,
                status='pending'
            )
            db.session.add(allocation_order)
            db.session.flush()
            
            # 执行分配逻辑
            total_allocated = 0
            
            for sale_item in sales_order.items.all():
                # 选择分配策略
                if allocation_strategy == 'fifo':
                    allocations = allocate_by_fifo(
                        sale_item.product_id,
                        sale_item.location_id,
                        sale_item.quantity,
                        sale_item.preferred_batch_no
                    )
                else:  # near_expiry
                    allocations = allocate_by_near_expiry(
                        sale_item.product_id,
                        sale_item.location_id,
                        sale_item.quantity,
                        sale_item.preferred_batch_no
                    )
                
                if not allocations:
                    db.session.rollback()
                    flash(f'商品 {sale_item.product.name} 分配失败', 'danger')
                    return redirect(url_for('allocation.create_allocation', sales_order_id=sales_order_id))
                
                # 创建分配明细并锁定库存
                for inventory, alloc_qty in allocations:
                    allocation_item = AllocationItem(
                        allocation_id=allocation_order.id,
                        sales_order_item_id=sale_item.id,
                        location_id=sale_item.location.id,
                        inventory_id=inventory.id,
                        allocated_qty=alloc_qty,
                        snapshot_quantity=inventory.quantity,
                        snapshot_batch_no=inventory.batch_no,
                        snapshot_expire_date=inventory.expire_date
                    )
                    db.session.add(allocation_item)
                    
                    # 锁定库存
                    inventory.lock_quantity(alloc_qty)
                    total_allocated += alloc_qty
                    
                    # 记录变更日志
                    log = InventoryChangeLog(
                        inventory_id=inventory.id,
                        change_type='lock',
                        quantity_before=inventory.quantity,
                        quantity_after=inventory.quantity,
                        locked_quantity_before=inventory.locked_quantity - alloc_qty,
                        locked_quantity_after=inventory.locked_quantity,
                        frozen_quantity_before=inventory.frozen_quantity,
                        frozen_quantity_after=inventory.frozen_quantity,
                        operator=current_user.username,
                        reason=f'分配单 {allocation_order.allocation_no} 锁定库存',
                        reference_id=allocation_order.id,
                        reference_type='allocation_order'
                    )
                    db.session.add(log)
            
            # 更新分配单总数
            allocation_order.total_allocated_qty = total_allocated
            allocation_order.status = 'completed'
            
            # 更新销售单状态
            sales_order.status = 'allocated'
            sales_order.allocated_quantity = total_allocated
            
            db.session.commit()
            flash(f'分配单 {allocation_order.allocation_no} 创建成功', 'success')
            return redirect(url_for('allocation.detail_allocation', id=allocation_order.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'创建分配单失败: {str(e)}', 'danger')
    
    # GET 请求：展示创建页面与验证结果
    can_allocate, missing, message = validate_allocation(sales_order)
    
    return render_template('allocation/create.html',
                         sales_order=sales_order,
                         can_allocate=can_allocate,
                         missing_details=missing,
                         message=message)


# ==================== 分配单详情 ====================

@allocation_bp.route('/detail/<int:id>')
@permission_required('inventory_manage')
@login_required
def detail_allocation(id):
    """分配单详情"""
    allocation_order = AllocationOrder.query.get_or_404(id)
    items = allocation_order.items.all()
    
    return render_template('allocation/detail.html',
                         allocation=allocation_order,
                         items=items)


# ==================== 分配单审批 ====================

@allocation_bp.route('/detail/<int:id>/approve', methods=['POST'])
@permission_required('inventory_manage')
@login_required
def approve_allocation(id):
    """审批分配单"""
    allocation_order = AllocationOrder.query.get_or_404(id)
    
    if allocation_order.status != 'pending':
        flash('只能审批待审批的分配单', 'danger')
        return redirect(url_for('allocation.detail_allocation', id=id))
    
    try:
        allocation_order.status = 'completed'
        allocation_order.manager_id = current_user.id
        allocation_order.approved_time = datetime.utcnow()
        
        db.session.commit()
        flash('分配单已审批', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'审批失败: {str(e)}', 'danger')
    
    return redirect(url_for('allocation.detail_allocation', id=id))


# ==================== 分配单拒绝 ====================

@allocation_bp.route('/detail/<int:id>/reject', methods=['POST'])
@permission_required('inventory_manage')
@login_required
def reject_allocation(id):
    """拒绝分配单（解锁库存）"""
    allocation_order = AllocationOrder.query.get_or_404(id)
    
    if allocation_order.status == 'completed':
        flash('已完成的分配单无法拒绝', 'danger')
        return redirect(url_for('allocation.detail_allocation', id=id))
    
    try:
        # 解锁所有锁定的库存
        for alloc_item in allocation_order.items.all():
            inventory = alloc_item.inventory
            if inventory:
                inventory.unlock_quantity(alloc_item.allocated_qty)
                
                # 记录变更日志
                log = InventoryChangeLog(
                    inventory_id=inventory.id,
                    change_type='unlock',
                    quantity_before=inventory.quantity,
                    quantity_after=inventory.quantity,
                    locked_quantity_before=inventory.locked_quantity + alloc_item.allocated_qty,
                    locked_quantity_after=inventory.locked_quantity,
                    frozen_quantity_before=inventory.frozen_quantity,
                    frozen_quantity_after=inventory.frozen_quantity,
                    operator=current_user.username,
                    reason=f'分配单 {allocation_order.allocation_no} 被拒绝，解锁库存',
                    reference_id=allocation_order.id,
                    reference_type='allocation_order'
                )
                db.session.add(log)
        
        # 更新分配单状态
        allocation_order.status = 'failed'
        
        # 恢复销售单状态
        sales_order = allocation_order.sales_order
        if sales_order:
            sales_order.status = 'pending_allocation'
            sales_order.allocated_quantity = 0
        
        db.session.commit()
        flash('分配单已拒绝，库存已解锁', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'拒绝失败: {str(e)}', 'danger')
    
    return redirect(url_for('allocation.detail_allocation', id=id))
