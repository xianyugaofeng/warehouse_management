from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from datetime import datetime
import logging
from app import db
from app.models import ReturnOrder, ReturnItem, WarehouseLocation
from app.models.inventory import Inventory
from app.utils.helpers import generate_return_no
from app.utils.auth import permission_required

logger = logging.getLogger(__name__)

return_bp = Blueprint('return', __name__)


@return_bp.route('/list', methods=['GET'])
@permission_required('outbound_manage')
@login_required
def return_list():
    """退货单列表"""
    page = request.args.get('page', 1, type=int)
    order_no = request.args.get('order_no', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    query = ReturnOrder.query
    
    if order_no:
        query = query.filter(ReturnOrder.order_no.like(f'%{order_no}%'))
    
    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(ReturnOrder.return_date >= start)
        except ValueError:
            pass
    
    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(ReturnOrder.return_date <= end)
        except ValueError:
            pass
    
    pagination = query.order_by(ReturnOrder.create_time.desc()).paginate(
        page=page, per_page=10, error_out=False
    )
    return_orders = pagination.items
    
    return render_template('return/list.html', 
                           return_orders=return_orders, 
                           pagination=pagination, 
                           order_no=order_no, 
                           start_date=start_date, 
                           end_date=end_date)


@return_bp.route('/add', methods=['GET', 'POST'])
@permission_required('outbound_manage')
@login_required
def return_add():
    """
    创建退货单
    
    业务说明：
    - 退货单用于处理不合格商品的退货流程
    - 不合格商品存放在不合格区（location_type='reject'）
    - 不合格商品不参与正常的库存流转，不需要考虑可用库存、锁定库存、冻结库存
    - 退货时直接扣减物理库存数量
    """
    if request.method == 'POST':
        remark = request.form.get('remark')
        
        product_ids = request.form.getlist('product_id')
        location_ids = request.form.getlist('location_id')
        batch_nos = request.form.getlist('batch_no')
        quantities = request.form.getlist('quantity')
        unit_prices = request.form.getlist('unit_price')
        defect_reasons = request.form.getlist('defect_reason')
        item_remarks = request.form.getlist('item_remark')
        
        valid_items = []
        for i, product_id in enumerate(product_ids):
            if not product_id or not location_ids[i] or not quantities[i] or not unit_prices[i] or not defect_reasons[i]:
                continue
            
            try:
                quantity = int(quantities[i])
                unit_price = float(unit_prices[i])
                if quantity <= 0 or unit_price <= 0:
                    continue
            except ValueError:
                flash(f'商品{product_id}的数量或单价格式不正确', 'warning')
                continue
            
            valid_items.append({
                'product_id': int(product_id),
                'location_id': int(location_ids[i]),
                'batch_no': batch_nos[i],
                'quantity': quantity,
                'unit_price': unit_price,
                'defect_reason': defect_reasons[i],
                'item_remark': item_remarks[i]
            })
        
        if not valid_items:
            flash('请至少添加一个有效的退货明细', 'danger')
            return redirect(url_for('return.return_add'))
        
        order_no = generate_return_no()
        return_order = ReturnOrder(
            order_no=order_no,
            operator_id=current_user.id,
            remark=remark
        )
        
        total_amount = 0.0
        processed_items = []
        
        for item in valid_items:
            inventory = Inventory.query.filter_by(
                product_id=item['product_id'],
                location_id=item['location_id'],
                batch_no=item['batch_no']
            ).with_for_update().first()
            
            if not inventory:
                db.session.rollback()
                flash(f"商品{item['product_id']}的库存记录不存在", 'danger')
                return redirect(url_for('return.return_add'))
            
            if not inventory.location or inventory.location.location_type != 'reject':
                db.session.rollback()
                flash(f"商品{item['product_id']}不在不合格区，无法进行退货操作", 'danger')
                return redirect(url_for('return.return_add'))
            
            if inventory.quantity < item['quantity']:
                db.session.rollback()
                flash(f"商品{item['product_id']}的库存不足，当前库存{inventory.quantity}件，需要{item['quantity']}件", 'danger')
                return redirect(url_for('return.return_add'))
            
            amount = item['quantity'] * item['unit_price']
            total_amount += amount
            
            return_item = ReturnItem(
                return_order=return_order,
                product_id=item['product_id'],
                location_id=item['location_id'],
                inspection_order_id=inventory.inspection_order_id,
                batch_no=item['batch_no'],
                quantity=item['quantity'],
                unit_price=item['unit_price'],
                amount=amount,
                defect_reason=item['defect_reason'],
                remark=item['item_remark']
            )
            db.session.add(return_item)
            processed_items.append((inventory, item['quantity']))
            logger.info(f"退货明细：商品{item['product_id']}, 数量{item['quantity']}, 批次{item['batch_no']}")
        
        for inventory, quantity in processed_items:
            inventory.quantity -= quantity
            logger.info(f"扣减不合格品库存：商品{inventory.product_id}, 扣减{quantity}件, 剩余{inventory.quantity}件")
            if inventory.quantity == 0:
                db.session.delete(inventory)
                logger.info(f"删除库存记录：商品{inventory.product_id}, 库存已清零")
        
        return_order.total_amount = total_amount
        return_order.status = 'completed'
        
        try:
            db.session.add(return_order)
            db.session.commit()
            logger.info(f"退货单创建成功：{order_no}, 共{len(processed_items)}项商品, 总金额{total_amount}")
            flash(f'退货单创建成功，共{len(processed_items)}项商品', 'success')
            return redirect(url_for('return.return_list'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"创建退货单失败: {str(e)}")
            flash(f'创建退货单失败: {str(e)}', 'danger')
            return redirect(url_for('return.return_add'))
    
    reject_locations = WarehouseLocation.query.filter(
        WarehouseLocation.location_type == 'reject',
        WarehouseLocation.status == True
    ).all()
    
    defective_products = []
    for location in reject_locations:
        inventories = Inventory.query.filter_by(location_id=location.id).all()
        for inventory in inventories:
            if inventory.defect_reason:
                defective_products.append(inventory)
    
    defect_reasons = ['质量问题', '包装损坏', '规格不符', '过期', '其他']
    
    return render_template('return/add.html', 
                           defective_products=defective_products, 
                           defect_reasons=defect_reasons)


@return_bp.route('/detail/<int:order_id>', methods=['GET'])
@permission_required('outbound_manage')
@login_required
def return_detail(order_id):
    """退货单详情"""
    return_order = ReturnOrder.query.get_or_404(order_id)
    return render_template('return/detail.html', return_order=return_order)