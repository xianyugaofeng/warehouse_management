from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from app.models.outbound import OutboundOrder, OutboundItem
from app.models.product import Product
from app.models.inventory import WarehouseLocation, Inventory
from app.utils.auth import permission_required
from app.utils.helpers import generate_outbound_no, update_inventory


outbound_bp = Blueprint('outbound', __name__)

# 出库单列表
@outbound_bp.route('/list')
@permission_required('outbound_manage')
@login_required
def list():
    keyword = request.args.get('keyword', '')
    receiver = request.args.get('receiver', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    query = OutboundOrder.query
    if keyword:
        query = query.filter(OutboundOrder.order_no.ilike(f'%{keyword}%') |
                             OutboundOrder.related_order.ilike(f'%{keyword}%')
        )
    if receiver:
        query = query.filter(OutboundOrder.receiver.ilike(f'%{receiver}%'))
    if start_date:
        query = query.filter(OutboundOrder.outbound_date >= start_date)
    if end_date:
        query = query.filter(OutboundOrder.outbound_date <= end_date)

    page = request.args.get('page', 1, type=int)
    pagination = query.order_by(OutboundOrder.create_time.desc()).paginate(page=page, perpage=10)
    orders = pagination.items

    return render_template('outbound/list.html',
                           orders=orders,
                           pagination=pagination,
                           keyword=keyword,
                           receiver=receiver,
                           start_date=start_date,
                           end_date=end_date
    )

# 添加出库单
@outbound_bp.route('/add', methods=['GET', 'POST'])
@permission_required('outbound_manage')
@login_required
def add():
    products = Product.query.all()
    locations = WarehouseLocation.query.filter_by(status=True).all()

    if request.method == 'POST':
        # 接收表单数据
        related_order = request.form.get('related_order')
        receiver = request.form.get('receiver')
        receive_phone = request.form.get('receive_phone')
        outbound_date = request.form.get('outbound_date', datetime.now().strftime('%Y-%m-%d'))
        purpose = request.form.get('purpose')
        remark = request.form.get('remark')

        # 接收明细数据
        product_ids = request.form.getlist('product_id[]')
        location_ids = request.form.getlist('location_id[]')
        batch_nos = request.form.getlist('batch_no[]')
        quantities = request.form.getlist('quantity[]')

        # 验证数据
        if not product_ids or len(product_ids) != len(quantities):
            flash('请添加至少一条入库明细', 'danger')
            return render_template('outbound/add.html',
                                   products=products,
                                   locations=locations
            )
        if not receiver:
            flash('请填写领用人', 'danger')
            return render_template('outbound/add.html',
                                   products=products,
                                   locations=locations
            )

        # 创建出库单
        order_no = generate_outbound_no()
        total_amount = sum(int(qty) for qty in quantities if qty.isdigit())
        outbound_order = OutboundOrder(
            order_no=order_no,
            related_order=related_order,
            receiver=receiver,
            operator_id=current_user.id,
            receive_phone=receive_phone,
            outbound_date=outbound_date,
            purpose=purpose,
            total_amount=total_amount,
            remark=remark
        )
        db.session.add(outbound_order)
        db.session.flush()

        # 处理出库明细并更新缓存
        try:
            for i in range(len(product_ids)):
                product_id = product_ids[i]
                location_id = location_ids[i]
                batch_no = batch_nos[i] or f'B{datetime.now().strftime("%Y%m%d")}{i+1}'
                quantity = int(quantities[i]) if quantities[i].isdigit() else 0

                if quantity <=0:
                    continue

                # 创建出库明细
                item = OutboundItem(
                    order_id=outbound_order.id,
                    product_id=product_id,
                    location_id=location_id,
                    batch_no=batch_no,
                    quantity=quantity
                )
                db.session.add(item)

                # 更新库存(减少)
                update_inventory(product_id, location_id, batch_no, quantity, is_bound=False)

            db.session.commit()
            flash('出库单创建成功', 'success')
            return redirect(url_for('outbound.list'))
        except Exception as e:
            db.session.rollback()
            flash(f'创建失败：{str(e)}', 'danger')

    return render_template('outbound/add.html',
                           products=products,
                           locations=locations
    )

