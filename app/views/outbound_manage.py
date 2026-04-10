from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from app.models.outbound import OutboundOrder, OutboundItem
from app.models.product import Product, Customer
from app.models.inventory import WarehouseLocation
from app.utils.auth import permission_required
from app.utils.helpers import generate_outbound_no, update_inventory


outbound_bp = Blueprint('outbound', __name__)

# 出库单列表
@outbound_bp.route('/list')
@permission_required('outbound_manage')
@login_required
def list():
    keyword = request.args.get('keyword', '')
    customer_id = request.args.get('customer_id', '')
    outbound_type = request.args.get('outbound_type', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    query = OutboundOrder.query
    if keyword:
        query = query.filter(OutboundOrder.order_no.ilike(f'%{keyword}%'))
    if customer_id:
        query = query.filter(OutboundOrder.customer_id == customer_id)
    if outbound_type:
        query = query.filter_by(outbound_type=outbound_type)
    if start_date:
        query = query.filter(OutboundOrder.outbound_date >= start_date)
    if end_date:
        query = query.filter(OutboundOrder.outbound_date <= end_date)

    page = request.args.get('page', 1, type=int)
    pagination = query.order_by(OutboundOrder.create_time.desc()).paginate(page=page, per_page=10)
    orders = pagination.items

    # 获取所有客户用于筛选
    customers = Customer.query.all()

    return render_template('outbound/list.html',
                           orders=orders,
                           pagination=pagination,
                           keyword=keyword,
                           customer_id=customer_id,
                           outbound_type=outbound_type,
                           start_date=start_date,
                           end_date=end_date,
                           customers=customers
    )

# 添加出库单
@outbound_bp.route('/add', methods=['GET', 'POST'])
@permission_required('outbound_manage')
@login_required
def add():
    products = Product.query.all()
    locations = WarehouseLocation.query.filter_by(status=True).all()
    customers = Customer.query.all()

    if request.method == 'POST':
        # 接收表单数据
        outbound_type = request.form.get('outbound_type', 'delivery')
        customer_id = request.form.get('customer_id')
        receive_phone = request.form.get('receive_phone')
        outbound_date = request.form.get('outbound_date', datetime.now().strftime('%Y-%m-%d'))
        remark = request.form.get('remark')

        # 接收明细数据
        product_ids = request.form.getlist('product_id[]')
        location_ids = request.form.getlist('location_id[]')
        batch_nos = request.form.getlist('batch_no[]')
        quantities = request.form.getlist('quantity[]')

        # 验证数据
        if not product_ids or len(product_ids) != len(quantities):
            flash('请添加至少一条出库明细', 'danger')
            return render_template('outbound/add.html',
                                   products=products,
                                   locations=locations,
                                   customers=customers,
                                   now=datetime.now()
            )
        if not customer_id:
            flash('请选择客户', 'danger')
            return render_template('outbound/add.html',
                                   products=products,
                                   locations=locations,
                                   customers=customers,
                                   now=datetime.now()
            )

        # 创建出库单
        order_no = generate_outbound_no()
        total_amount = sum(int(qty) for qty in quantities if qty.isdigit())
        outbound_order = OutboundOrder(
            order_no=order_no,
            outbound_type=outbound_type,
            customer_id=customer_id,
            operator_id=current_user.id,
            receive_phone=receive_phone,
            outbound_date=outbound_date,
            total_amount=total_amount,
            status='draft',
            remark=remark
        )
        db.session.add(outbound_order)
        db.session.flush()

        # 创建出库明细（不更新库存）
        try:
            for i in range(len(product_ids)):
                product_id = product_ids[i]
                location_id = location_ids[i]
                batch_no = batch_nos[i] or f'B{datetime.now().strftime("%Y%m%d")}{i+1}'
                quantity = int(quantities[i]) if quantities[i].isdigit() else 0

                if quantity <= 0:
                    flash('数量必须大于0', 'danger')
                    return render_template('outbound/add.html',
                                           products=products,
                                           locations=locations,
                                           customers=customers,
                                           now=datetime.now()
                    )

                # 创建出库明细
                item = OutboundItem(
                    order_id=outbound_order.id,
                    product_id=product_id,
                    location_id=location_id,
                    batch_no=batch_no,
                    quantity=quantity
                )
                db.session.add(item)

            db.session.commit()
            flash('出库单创建成功，请审核出库', 'success')
            return redirect(url_for('outbound.detail', id=outbound_order.id))
        except Exception as e:
            db.session.rollback()
            flash(f'创建失败：{str(e)}', 'danger')

    return render_template('outbound/add.html',
                           products=products,
                           locations=locations,
                           customers=customers,
                           now=datetime.now()
    )

# 审核出库单
@outbound_bp.route('/audit/<int:id>', methods=['POST'])
@permission_required('outbound_manage')
@login_required
def audit(id):
    order = OutboundOrder.query.get_or_404(id)
    
    if order.status != 'draft':
        flash('只有草稿状态的出库单才能审核', 'warning')
        return redirect(url_for('outbound.detail', id=id))
    
    if not order.items.first():
        flash('出库单没有明细，无法审核', 'warning')
        return redirect(url_for('outbound.detail', id=id))
    
    # 获取审核结果
    audit_result = request.form.get('audit_result')
    
    try:
        if audit_result == 'approved':
            # 审核通过：更新库存（减少）
            for item in order.items:
                update_inventory(item.product_id, item.location_id, item.batch_no, item.quantity, is_bound=False)
            
            # 更新出库单状态为已完成
            order.status = 'completed'
            db.session.commit()
            
            flash('审核通过，库存已更新', 'success')
            return redirect(url_for('outbound.list'))
        
        elif audit_result == 'rejected':
            # 审核未通过：删除出库单（级联删除明细）
            db.session.delete(order)
            db.session.commit()
            
            flash('审核未通过，出库单已删除', 'warning')
            return redirect(url_for('outbound.list'))
        
        else:
            flash('无效的审核结果', 'danger')
            return redirect(url_for('outbound.detail', id=id))
            
    except Exception as e:
        db.session.rollback()
        flash(f'审核失败:{str(e)}', 'danger')
        return redirect(url_for('outbound.detail', id=id))


# 出库明细查询
@outbound_bp.route('/items')
@permission_required('outbound_manage')
@login_required
def items():
    # 接收查询参数
    keyword = request.args.get('keyword', '')
    product_id = request.args.get('product_id', '')
    location_id = request.args.get('location_id', '')
    customer_id = request.args.get('customer_id', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    order_id = request.args.get('order_id', '')

    # 构建查询
    query = OutboundItem.query.join(OutboundOrder).join(Customer, OutboundOrder.customer_id == Customer.id).join(Product).join(WarehouseLocation)
    
    # 应用过滤条件
    if keyword:
        query = query.filter(
            Product.name.ilike(f'%{keyword}%') |
            Product.code.ilike(f'%{keyword}%') |
            OutboundOrder.order_no.ilike(f'%{keyword}%') |
            Customer.name.ilike(f'%{keyword}%')
        )
    
    if customer_id:
        query = query.filter(OutboundOrder.customer_id == customer_id)
    
    if product_id:
        query = query.filter(OutboundItem.product_id == product_id)
    
    if location_id:
        query = query.filter(OutboundItem.location_id == location_id)
    
    if order_id:
        query = query.filter(OutboundItem.order_id == order_id)
    
    if start_date:
        query = query.filter(OutboundOrder.outbound_date >= start_date)
    
    if end_date:
        query = query.filter(OutboundOrder.outbound_date <= end_date)

    # 分页
    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = query.order_by(OutboundItem.id.desc()).paginate(page=page, per_page=per_page)
    items = pagination.items

    # 获取所有商品、库位和客户用于筛选
    products = Product.query.all()
    locations = WarehouseLocation.query.filter_by(status=True).all()
    customers = Customer.query.all()

    return render_template('outbound/items.html',
                           items=items,
                           pagination=pagination,
                           keyword=keyword,
                           product_id=product_id,
                           location_id=location_id,
                           customer_id=customer_id,
                           start_date=start_date,
                           end_date=end_date,
                           order_id=order_id,
                           products=products,
                           locations=locations,
                           customers=customers
    )

# 出库单详情
@outbound_bp.route('/detail/<int:id>')
@permission_required('outbound_manage')
@login_required
def detail(id):
    order = OutboundOrder.query.get_or_404(id)
    return render_template('outbound/detail.html', order=order)

