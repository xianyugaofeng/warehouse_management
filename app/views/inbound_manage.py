from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user, login_required
from datetime import datetime
from app import db
from app.models.inbound import InboundOrder, InboundItem
from app.models.product import Product, Supplier
from app.models.inventory import WarehouseLocation
from app.utils.auth import permission_required
from app.utils.helpers import generate_inbound_no, update_inventory

inbound_bp = Blueprint('inbound', __name__)

# 入库单列表
@inbound_bp.route('/list')
@permission_required('inbound_manage')
@login_required
def list():
    keyword = request.args.get('keyword', '')     # 接收参数keyword supplier_id start_date end_date page
    supplier_id = request.args.get('supplier_id', '')
    inbound_type = request.args.get('inbound_type', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    query = InboundOrder.query
    if keyword:
        query = query.filter(InboundOrder.order_no.ilike(f'%{keyword}%'))
    if supplier_id:
        query = query.filter_by(supplier_id=supplier_id)
    if inbound_type:
        query = query.filter_by(inbound_type=inbound_type)
    if start_date:
        query = query.filter(InboundOrder.inbound_date >= start_date)
    if end_date:
        query = query.filter(InboundOrder.inbound_date <= end_date)

    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = query.order_by(InboundOrder.create_time.desc()).paginate(page=page, per_page=per_page)
    orders = pagination.items

    suppliers = Supplier.query.all()
    return render_template('inbound/list.html',
                           orders=orders,
                           pagination=pagination,
                           keyword=keyword,
                           supplier_id=supplier_id,
                           inbound_type=inbound_type,
                           start_date=start_date,
                           end_date=end_date,
                           suppliers=suppliers
    )

# 添加入库单
@inbound_bp.route('/add', methods=['GET', 'POST'])
@permission_required('inbound_manage')
@login_required
def add():
    products = Product.query.all()
    suppliers = Supplier.query.all()
    locations = WarehouseLocation.query.filter_by(status=True).all()

    if request.method == 'POST':
        # 接收表单数据
        inbound_type = request.form.get('inbound_type', 'replenish')
        supplier_id = request.form.get('supplier_id')
        inbound_date = request.form.get('inbound_date', datetime.now().strftime('%Y-%m-%d'))
        remark = request.form.get('remark')

        # 接收明细数据(前端通过JS添加多条明细)
        product_ids = request.form.getlist('product_id[]')
        location_ids = request.form.getlist('location_id[]')
        batch_nos = request.form.getlist('batch_no[]')
        quantities = request.form.getlist('quantity[]')
        production_dates = request.form.getlist('production_date[]')
        expire_dates = request.form.getlist('expire_date[]')

        # 验证数据
        if not product_ids or len(product_ids) != len(quantities):
            flash('请添加至少一条入库明细', 'danger')
            return render_template('inbound/add.html',
                                   products=products,
                                   suppliers=suppliers,
                                   locations=locations,
                                   now=datetime.now()
            )

        # 创建入库单
        order_no = generate_inbound_no()
        total_amount = sum(int(qty) for qty in quantities if qty.isdigit())
        inbound_order = InboundOrder(
            order_no=order_no,
            inbound_type=inbound_type,
            supplier_id=supplier_id,
            operator_id=current_user.id,
            inbound_date=inbound_date,
            total_amount=total_amount,
            status='draft',
            remark=remark
        )
        db.session.add(inbound_order)
        db.session.flush()

        # 创建入库明细（不更新库存）
        try:
            for i in range(len(product_ids)):
                product_id = product_ids[i]
                location_id = location_ids[i]
                batch_no = batch_nos[i] or f'B{datetime.now().strftime("%Y%m%d")}{i+1}'
                quantity = int(quantities[i]) if quantities[i].isdigit() else 0
                production_date = production_dates[i] if production_dates[i] else None
                expire_date = expire_dates[i] if expire_dates[i] else None

                if quantity <= 0:
                    flash('数量必须大于0', 'danger')
                    return render_template('inbound/add.html',
                                           products=products,
                                           suppliers=suppliers,
                                           locations=locations,
                                           now=datetime.now()
                    )

                # 创建入库明细
                item = InboundItem(
                    order_id=inbound_order.id,
                    product_id=product_id,
                    location_id=location_id,
                    quantity=quantity,
                    batch_no=batch_no,
                    production_date=production_date,
                    expire_date=expire_date
                )
                db.session.add(item)

            db.session.commit()
            flash('入库单创建成功，请确认入库', 'success')
            return redirect(url_for('inbound.detail', id=inbound_order.id))
        except Exception as e:
            db.session.rollback()
            flash(f'创建失败:{str(e)}', 'danger')

    return render_template('inbound/add.html',
                           products=products,
                           suppliers=suppliers,
                           locations=locations,
                           now=datetime.now()
    )

# 审核入库单
@inbound_bp.route('/audit/<int:id>', methods=['POST'])
@permission_required('inbound_manage')
@login_required
def audit(id):
    order = InboundOrder.query.get_or_404(id)
    
    if order.status != 'draft':
        flash('只有草稿状态的入库单才能审核', 'warning')
        return redirect(url_for('inbound.detail', id=id))
    
    if not order.items.first():
        flash('入库单没有明细，无法审核', 'warning')
        return redirect(url_for('inbound.detail', id=id))
    
    # 获取审核结果
    audit_result = request.form.get('audit_result')
    
    try:
        if audit_result == 'approved':
            # 审核通过：更新库存
            for item in order.items:
                try:
                    update_inventory(item.product_id, item.location_id, item.batch_no, item.quantity, is_bound=True)
                except ValueError as e:
                    # 捕获库位冲突等错误
                    flash(f'入库失败: {str(e)}', 'danger')
                    return redirect(url_for('inbound.detail', id=id))
            
            # 更新入库单状态为已完成
            order.status = 'completed'
            db.session.commit()
            
            flash('审核通过，库存已更新', 'success')
            return redirect(url_for('inbound.list'))
        
        elif audit_result == 'rejected':
            # 审核未通过：删除入库单（级联删除明细）
            db.session.delete(order)
            db.session.commit()
            
            flash('审核未通过，入库单已删除', 'warning')
            return redirect(url_for('inbound.list'))
        
        else:
            flash('无效的审核结果', 'danger')
            return redirect(url_for('inbound.detail', id=id))
            
    except Exception as e:
        db.session.rollback()
        flash(f'审核失败: {str(e)}', 'danger')
        return redirect(url_for('inbound.detail', id=id))


# 入库明细查询
@inbound_bp.route('/items')
@permission_required('inbound_manage')
@login_required
def items():
    # 接收查询参数
    keyword = request.args.get('keyword', '')
    product_id = request.args.get('product_id', '')
    location_id = request.args.get('location_id', '')
    supplier_id = request.args.get('supplier_id', '')
    inbound_type = request.args.get('inbound_type', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    order_id = request.args.get('order_id', '')

    # 构建查询
    query = InboundItem.query.join(InboundOrder).join(Supplier, InboundOrder.supplier_id == Supplier.id).join(Product).join(WarehouseLocation)
    
    # 应用过滤条件
    if keyword:
        query = query.filter(
            Product.name.ilike(f'%{keyword}%') |
            Product.code.ilike(f'%{keyword}%') |
            InboundOrder.order_no.ilike(f'%{keyword}%') |
            Supplier.name.ilike(f'%{keyword}%')
        )
    
    if supplier_id:
        query = query.filter(InboundOrder.supplier_id == supplier_id)

    if inbound_type:
        query = query.filter(InboundOrder.inbound_type == inbound_type)

    if product_id:
        query = query.filter(InboundItem.product_id == product_id)
    
    if location_id:
        query = query.filter(InboundItem.location_id == location_id)
    
    if order_id:
        query = query.filter(InboundItem.order_id == order_id)
    
    if start_date:
        query = query.filter(InboundOrder.inbound_date >= start_date)
    
    if end_date:
        query = query.filter(InboundOrder.inbound_date <= end_date)

    # 分页
    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = query.order_by(InboundItem.id.desc()).paginate(page=page, per_page=per_page)
    items = pagination.items

    # 获取所有商品和库位用于筛选
    products = Product.query.all()
    locations = WarehouseLocation.query.filter_by(status=True).all()
    suppliers = Supplier.query.all()

    return render_template('inbound/items.html',
                           items=items,
                           pagination=pagination,
                           keyword=keyword,
                           product_id=product_id,
                           location_id=location_id,
                           inbound_type=inbound_type,
                           start_date=start_date,
                           end_date=end_date,
                           order_id=order_id,
                           products=products,
                           locations=locations,
                           suppliers=suppliers
    )

# 入库单详情
@inbound_bp.route('/detail/<int:id>')
@permission_required('inbound_manage')
@login_required
def detail(id):
    order = InboundOrder.query.get_or_404(id)
    return render_template('inbound/detail.html', order=order)

# 入库单审核列表
@inbound_bp.route('/audit_list')
@permission_required('inbound_manage')
@login_required
def audit_list():
    keyword = request.args.get('keyword', '')
    supplier_id = request.args.get('supplier_id', '')
    status = request.args.get('status', 'draft')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    query = InboundOrder.query
    if keyword:
        query = query.filter(InboundOrder.order_no.ilike(f'%{keyword}%'))
    if supplier_id:
        query = query.filter_by(supplier_id=supplier_id)
    if status:
        query = query.filter_by(status=status)
    if start_date:
        query = query.filter(InboundOrder.inbound_date >= start_date)
    if end_date:
        query = query.filter(InboundOrder.inbound_date <= end_date)

    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = query.order_by(InboundOrder.create_time.desc()).paginate(page=page, per_page=per_page)
    orders = pagination.items

    # 统计待审核和已通过的数量
    draft_count = InboundOrder.query.filter_by(status='draft').count()
    completed_count = InboundOrder.query.filter_by(status='completed').count()

    suppliers = Supplier.query.all()
    return render_template('inbound/audit_list.html',
                           orders=orders,
                           pagination=pagination,
                           keyword=keyword,
                           supplier_id=supplier_id,
                           status=status,
                           start_date=start_date,
                           end_date=end_date,
                           suppliers=suppliers,
                           draft_count=draft_count,
                           completed_count=completed_count
    )