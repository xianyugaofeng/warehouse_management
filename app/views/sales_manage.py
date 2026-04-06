"""
销售单管理模块
核心功能: 销售单创建、分配触发、状态跟踪、历史记录

API 端点:
- GET/POST /sales/create - 创建销售单
- GET /sales/list - 销售单列表
- GET /sales/detail/<int:id> - 销售单详情
- POST /sales/detail/<int:id>/update - 修改销售单
- POST /sales/detail/<int:id>/allocate - 触发分配
- DELETE /sales/detail/<int:id> - 删除销售单（仅草稿）
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from app.models.sales import SalesOrder, SalesOrderItem
from app.models.product import Product, Customer
from app.models.inventory import WarehouseLocation
from app.models.user import User
from app.utils.auth import permission_required
from app.utils.helpers import generate_sales_order_no

sales_bp = Blueprint('sales', __name__)


# ==================== 销售单列表与搜索 ====================

@sales_bp.route('/list')
@permission_required('inventory_manage')
@login_required
def list_sales():
    """销售单列表"""
    keyword = request.args.get('keyword', '')
    customer_id = request.args.get('customer_id', '')
    status = request.args.get('status', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    query = SalesOrder.query
    
    if keyword:
        query = query.filter(
            SalesOrder.order_no.ilike(f'%{keyword}%') |
            SalesOrder.related_order.ilike(f'%{keyword}%')
        )
    if customer_id:
        query = query.filter(SalesOrder.customer_id == int(customer_id))
    if status:
        query = query.filter(SalesOrder.status == status)
    if date_from:
        query = query.filter(SalesOrder.create_time >= date_from)
    if date_to:
        query = query.filter(SalesOrder.create_time <= date_to)
    
    page = request.args.get('page', 1, type=int)
    pagination = query.order_by(SalesOrder.create_time.desc()).paginate(page=page, per_page=10)
    
    customers = Customer.query.filter_by(status=True).all()
    
    return render_template('sales/list.html',
                         orders=pagination.items,
                         pagination=pagination,
                         customers=customers,
                         keyword=keyword,
                         customer_id=customer_id,
                         status=status,
                         date_from=date_from,
                         date_to=date_to)


# ==================== 销售单创建 ====================

@sales_bp.route('/create', methods=['GET', 'POST'])
@permission_required('inventory_manage')
@login_required
def create_sales():
    """创建销售单"""
    if request.method == 'POST':
        try:
            # 获取表单数据
            customer_id = int(request.form.get('customer_id'))
            outbound_type = request.form.get('outbound_type', 'normal')
            expected_date = request.form.get('expected_outbound_date')
            related_order = request.form.get('related_order', '')
            remark = request.form.get('remark', '')
            
            # 获取销售单明细
            product_ids = request.form.getlist('product_id[]')
            quantities = request.form.getlist('quantity[]')
            unit_prices = request.form.getlist('unit_price[]')
            
            # 数据验证
            if not customer_id:
                flash('请选择客户', 'danger')
                return redirect(url_for('sales.create_sales'))
            
            if not product_ids or len(product_ids) != len(quantities):
                flash('请添加至少一条销售明细', 'danger')
                return redirect(url_for('sales.create_sales'))
            
            # 创建销售单
            order_no = generate_sales_order_no()
            total_qty = sum(int(q) for q in quantities if q.isdigit())
            
            sales_order = SalesOrder(
                order_no=order_no,
                customer_id=customer_id,
                outbound_type=outbound_type,
                expected_outbound_date=expected_date,
                related_order=related_order,
                remark=remark,
                operator_id=current_user.id,
                total_quantity=total_qty,
                status='pending_allocation'
            )
            db.session.add(sales_order)
            db.session.flush()
            
            # 添加销售单明细
            for i in range(len(product_ids)):
                product_id = int(product_ids[i])
                quantity = int(quantities[i]) if quantities[i].isdigit() else 0
                unit_price = float(unit_prices[i]) if unit_prices[i] else None
                
                if quantity > 0:
                    item = SalesOrderItem(
                        order_id=sales_order.id,
                        product_id=product_id,
                        quantity=quantity,
                        unit_price=unit_price
                    )
                    db.session.add(item)
            
            db.session.commit()
            flash(f'销售单 {order_no} 创建成功', 'success')
            return redirect(url_for('sales.detail_sales', id=sales_order.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'创建失败: {str(e)}', 'danger')
    
    # GET 请求：展示创建表单
    customers = Customer.query.filter_by(status=True).all()
    locations = WarehouseLocation.query.filter_by(status=True, location_type='normal').all()
    products = Product.query.all()
    
    return render_template('sales/create.html',
                         customers=customers,
                         warehouses=locations,
                         products=products,
                         today=datetime.now().strftime('%Y-%m-%d'))


# ==================== 销售单详情 ====================

@sales_bp.route('/detail/<int:id>')
@permission_required('inventory_manage')
@login_required
def detail_sales(id):
    """销售单详情"""
    sales_order = SalesOrder.query.get_or_404(id)
    items = sales_order.items.all()
    
    # 获取相关的分配单、拣货单、复核单、出库单
    allocation = sales_order.allocation_order
    picking = sales_order.picking_order
    inspection = sales_order.inspection_order
    shipping = sales_order.shipping_order
    
    return render_template('sales/detail.html',
                         order=sales_order,
                         items=items,
                         allocation=allocation,
                         picking=picking,
                         inspection=inspection,
                         shipping=shipping)


# ==================== 销售单更新 ====================

@sales_bp.route('/detail/<int:id>/update', methods=['POST'])
@permission_required('inventory_manage')
@login_required
def update_sales(id):
    """修改销售单信息（仅限待分配状态）"""
    sales_order = SalesOrder.query.get_or_404(id)
    
    if sales_order.status != 'pending_allocation':
        flash('只能修改待分配状态的销售单', 'danger')
        return redirect(url_for('sales.detail_sales', id=id))
    
    try:
        # 更新可修改字段
        sales_order.expected_outbound_date = request.form.get('expected_outbound_date', sales_order.expected_outbound_date)
        sales_order.remark = request.form.get('remark', '')
        
        db.session.commit()
        flash('销售单已更新', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'更新失败: {str(e)}', 'danger')
    
    return redirect(url_for('sales.detail_sales', id=id))


# ==================== 删除销售单 ====================

@sales_bp.route('/detail/<int:id>/delete', methods=['POST'])
@permission_required('inventory_manage')
@login_required
def delete_sales(id):
    """删除销售单（仅限待分配状态）"""
    sales_order = SalesOrder.query.get_or_404(id)
    
    if sales_order.status != 'pending_allocation':
        flash('只能删除待分配状态的销售单', 'danger')
        return redirect(url_for('sales.list_sales'))
    
    try:
        db.session.delete(sales_order)
        db.session.commit()
        flash(f'销售单 {sales_order.order_no} 已删除', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'删除失败: {str(e)}', 'danger')
    
    return redirect(url_for('sales.list_sales'))


# ==================== 状态查询与统计 ====================

@sales_bp.route('/statistics')
@permission_required('inventory_manage')
@login_required
def statistics():
    """销售单统计"""
    total = SalesOrder.query.count()
    pending = SalesOrder.query.filter_by(status='pending_allocation').count()
    allocated = SalesOrder.query.filter_by(status='allocated').count()
    picked = SalesOrder.query.filter_by(status='picked').count()
    inspected = SalesOrder.query.filter_by(status='inspected').count()
    shipped = SalesOrder.query.filter_by(status='shipped').count()
    
    return render_template('sales/statistics.html',
                         total=total,
                         pending=pending,
                         allocated=allocated,
                         picked=picked,
                         inspected=inspected,
                         shipped=shipped)


# ==================== API 端点 ====================

@sales_bp.route('/api/customer/<int:customer_id>')
@login_required
def api_get_customer(customer_id):
    """获取客户信息 API"""
    customer = Customer.query.get_or_404(customer_id)
    return jsonify({
        'id': customer.id,
        'name': customer.name,
        'code': customer.code,
        'phone': customer.phone,
        'email': customer.email,
        'address': customer.address
    })


@sales_bp.route('/api/product/<int:product_id>')
@login_required
def api_get_product(product_id):
    """获取商品信息 API"""
    product = Product.query.get_or_404(product_id)
    return jsonify({
        'id': product.id,
        'code': product.code,
        'name': product.name,
        'spec': product.spec,
        'unit': product.unit,
        'warning_stock': product.warning_stock
    })
