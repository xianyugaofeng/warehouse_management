from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from app.models import ReturnOrder, ReturnItem, DefectiveProduct, WarehouseLocation, Product
from app.utils.helpers import generate_return_no

return_bp = Blueprint('return', __name__)


@return_bp.route('/list', methods=['GET'])
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
@login_required
def return_add():
    """创建退货单"""
    if request.method == 'POST':
        # 获取表单数据
        return_reason = request.form.get('return_reason')
        remark = request.form.get('remark')
        
        # 检查必填字段
        if not return_reason:
            flash('退货原因不能为空', 'danger')
            return redirect(url_for('return.return_add'))
        
        # 创建退货单
        order_no = generate_return_no()
        return_order = ReturnOrder(
            order_no=order_no,
            return_reason=return_reason,
            operator_id=current_user.id,
            remark=remark
        )
        
        # 处理退货明细
        product_ids = request.form.getlist('product_id')
        location_ids = request.form.getlist('location_id')
        batch_nos = request.form.getlist('batch_no')
        quantities = request.form.getlist('quantity')
        unit_prices = request.form.getlist('unit_price')
        defect_reasons = request.form.getlist('defect_reason')
        item_remarks = request.form.getlist('item_remark')
        
        total_amount = 0.0
        
        for i, product_id in enumerate(product_ids):
            if not product_id or not location_ids[i] or not quantities[i] or not unit_prices[i] or not defect_reasons[i]:
                continue
            
            try:
                quantity = int(quantities[i])
                unit_price = float(unit_prices[i])
                if quantity <= 0 or unit_price <= 0:
                    continue
            except ValueError:
                continue
            
            # 计算金额
            amount = quantity * unit_price
            total_amount += amount
            
            # 创建退货明细
            return_item = ReturnItem(
                return_order=return_order,
                product_id=int(product_id),
                location_id=int(location_ids[i]),
                batch_no=batch_nos[i],
                quantity=quantity,
                unit_price=unit_price,
                amount=amount,
                defect_reason=defect_reasons[i],
                remark=item_remarks[i]
            )
            
            # 更新不合格商品数量
            defective_product = DefectiveProduct.query.filter_by(
                product_id=int(product_id),
                location_id=int(location_ids[i]),
                batch_no=batch_nos[i]
            ).first()
            
            if defective_product and defective_product.quantity >= quantity:
                defective_product.quantity -= quantity
                # 如果数量为0，删除记录
                if defective_product.quantity == 0:
                    db.session.delete(defective_product)
            
        # 设置总金额
        return_order.total_amount = total_amount
        return_order.status = 'completed'
        
        # 保存到数据库
        db.session.add(return_order)
        db.session.commit()
        
        flash('退货单创建成功', 'success')
        return redirect(url_for('return.return_list'))
    
    # 获取不合格商品库位的不合格商品
    inspection_locations = WarehouseLocation.query.filter(
        WarehouseLocation.location_type == 'reject'
    ).all()
    
    defective_products = []
    for location in inspection_locations:
        location_defective = DefectiveProduct.query.filter_by(location_id=location.id).all()
        defective_products.extend(location_defective)
    
    # 不合格原因选项
    defect_reasons = [
        '质量问题', '包装损坏', '规格不符', '过期', '其他'
    ]
    
    return render_template('return/add.html', 
                           defective_products=defective_products, 
                           defect_reasons=defect_reasons)


@return_bp.route('/detail/<int:order_id>', methods=['GET'])
def return_detail(order_id):
    """退货单详情"""
    return_order = ReturnOrder.query.get_or_404(order_id)
    return render_template('return/detail.html', return_order=return_order)