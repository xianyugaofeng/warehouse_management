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
    keyword = request.args.get('keyword', '')
    supplier_id = request.args.get('supplier_id', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    query = InboundOrder.query
    if keyword:
        query = query.filter(InboundOrder.order_no.ilike(f'%{keyword}%') |
                             InboundOrder.related_order.ilike(f'%{keyword}%'))
    if supplier_id:
        query = query.filter_by(supplier_id=supplier_id)
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
        supplier_id = request.form.get('supplier_id')
        related_order = request.form.get('related_order')
        inbound_date = request.form.get('inbound_date', datetime.now().strftime('%Y-%m-%d'))
        # 默认值为当前时间
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
                                   location=locations
            )

        # 创建入库单
        order_no = generate_inbound_no()
        total_amount = sum(int(qty) for qty in quantities if qty.isdigit())
        # isdigit()检查字符串中是否只包含数字 负数会返回False
        # 生成器表达式
        inbound_order = InboundOrder(
            order_no=order_no,
            supplier_id=supplier_id,
            related_order=related_order,
            operator_id=current_user.id,
            inbound_date=inbound_date,
            total_amount=total_amount,
            remark=remark
        )
        db.session.add(inbound_order)
        db.session.flush()      # 刷新获取order_id,用于明细关联

        # 处理入库明细并更新库存
        try:
            for i in range(len(product_ids)):
                product_id = product_ids[i]
                location_id = location_ids[i]
                batch_no = batch_nos[i] or f'B{datetime.now().strftime("%Y%m%d")}{i+1}'
                quantity = int(quantities[i]) if quantities[i].isdigit() else 0
                production_date = production_dates[i] if production_dates[i] else None
                expire_date = expire_dates[i] if expire_dates[i] else None

                if quantity <= 0:
                    return None

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

                # 更新库存
                update_inventory(product_id, location_id, batch_no, quantity, is_bound=True)

            db.session.commit()
            flash('入库单创建成功', 'success')
            return redirect(url_for('inbound.list'))
        except Exception as e:
            db.session.rollback()
            flash(f'创建失败:{str(e)}', 'danger')

    return render_template('inbound/add.html',
                           products=products,
                           suppliers=suppliers,
                           locations=locations
    )  # GET请求或POST请求添加入库单失败