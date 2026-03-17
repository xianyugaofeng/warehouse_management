from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user, login_required
from datetime import datetime
from app import db
from app.models.inbound import InboundOrder, InboundItem
from app.models.product import Product, Supplier
from app.models.inventory import WarehouseLocation
from app.models.purchase import PurchaseItem
from app.models.inspection import InspectionOrder
from app.utils.auth import permission_required
from app.utils.helpers import generate_inbound_no, update_inventory, recommend_location

inbound_bp = Blueprint('inbound', __name__)

# 入库单列表
@inbound_bp.route('/list')
@permission_required('inbound_manage')
@login_required
def list():
    keyword = request.args.get('keyword', '')     # 接收参数keyword supplier_id start_date end_date page
    supplier_id = request.args.get('supplier_id', '')
    status = request.args.get('status', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    query = InboundOrder.query
    if keyword:
        query = query.filter(InboundOrder.order_no.ilike(f'%{keyword}%') |
                             InboundOrder.related_order.ilike(f'%{keyword}%'))
    if supplier_id:
        try:
            supplier_id_int = int(supplier_id)
            query = query.filter_by(supplier_id=supplier_id_int)
        except ValueError:
            pass
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

    suppliers = Supplier.query.all()
    status_options = [('pending', '待上架'), ('completed', '已完成')]
    return render_template('inbound/list.html',
                           orders=orders,
                           pagination=pagination,
                           keyword=keyword,
                           supplier_id=supplier_id,
                           status=status,
                           status_options=status_options,
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
    
    # 获取已完成的检验单（用于选择检验单创建入库单）
    inspection_orders = InspectionOrder.query.filter_by(status='completed').all()

    # 检查是否选择了检验单
    selected_inspection_id = request.args.get('inspection_id') or request.form.get('inspection_id')
    selected_inspection = None
    if selected_inspection_id:
        selected_inspection = InspectionOrder.query.get(selected_inspection_id)
        # 预加载采购明细以便在模板中显示单价
        if selected_inspection and selected_inspection.purchase_order:
            for item in selected_inspection.items:
                item.purchase_item = PurchaseItem.query.filter_by(
                    order_id=selected_inspection.purchase_order_id,
                    product_id=item.product_id
                ).first()

    if request.method == 'POST':
        # 检查是否从检验单创建入库
        inspection_id = request.form.get('inspection_id')
        if inspection_id:
            return create_inbound_from_inspection(inspection_id, request, products, suppliers, locations)
        
        # 手动创建入库单
        return create_inbound_manual(request, products, suppliers, locations)

    return render_template('inbound/add.html',
                           products=products,
                           suppliers=suppliers,
                           locations=locations,
                           now=datetime.now(),
                           inspection_orders=inspection_orders,
                           selected_inspection=selected_inspection
    )


def create_inbound_from_inspection(inspection_id, request, products, suppliers, locations):
    """从检验单创建入库单"""
    inspection = InspectionOrder.query.get_or_404(inspection_id)
    
    # 验证单据是否齐全
    if not inspection.delivery_order_no:
        flash('送货单号缺失，无法办理入库', 'danger')
        return render_template('inbound/add.html',
                               products=products,
                               suppliers=suppliers,
                               locations=locations,
                               now=datetime.now(),
                               inspection_orders=InspectionOrder.query.filter_by(status='completed').all(),
                               selected_inspection=inspection)
    
    # 查找正常库位
    normal_locations = WarehouseLocation.query.filter_by(location_type='normal', status=True).all()
    if not normal_locations:
        flash('未设置正常区域，请先配置仓库位置', 'danger')
        return render_template('inbound/add.html',
                               products=products,
                               suppliers=suppliers,
                               locations=locations,
                               now=datetime.now(),
                               inspection_orders=InspectionOrder.query.filter_by(status='completed').all(),
                               selected_inspection=inspection)
    
    # 创建入库单
    order_no = generate_inbound_no()
    inbound_order = InboundOrder(
        order_no=order_no,
        supplier_id=inspection.supplier_id,
        related_order=inspection.purchase_order.order_no if inspection.purchase_order else '',
        delivery_order_no=inspection.purchase_order.order_no if inspection.purchase_order else '',  # 送货单号即采购单号
        inspection_cert_no=inspection.order_no,
        purchase_order_id=inspection.purchase_order_id,
        inspection_order_id=inspection.id,
        operator_id=current_user.id,
        inbound_date=datetime.now().date(),
        total_amount=inspection.qualified_quantity,
        status='pending',  # 初始状态为待上架
        remark=request.form.get('remark', '')
    )
    db.session.add(inbound_order)
    db.session.flush()
    
    try:
        # 处理每个检验合格的商品
        for item in inspection.items:
            if item.quality_status == 'passed' and item.qualified_quantity > 0:
                # 获取采购单中商品的单价
                purchase_item = PurchaseItem.query.filter_by(
                    order_id=inspection.purchase_order_id,
                    product_id=item.product_id
                ).first()
                unit_price = purchase_item.unit_price if purchase_item else 0
                
                # 自动推荐最佳库位
                recommended_location = recommend_location(item.product_id, normal_locations)
                
                # 创建批次号
                batch_no = f'B{datetime.now().strftime("%Y%m%d")}{item.id}'
                
                # 创建入库明细
                inbound_item = InboundItem(
                    order_id=inbound_order.id,
                    product_id=item.product_id,
                    location_id=recommended_location.id,
                    quantity=item.qualified_quantity,
                    batch_no=batch_no,
                    unit_price=unit_price,
                    subtotal=unit_price * item.qualified_quantity
                )
                db.session.add(inbound_item)
                

        
        db.session.commit()
        flash('入库单创建成功，商品已入库并增加库存', 'success')
        return redirect(url_for('inbound.list'))
    except Exception as e:
        db.session.rollback()
        flash(f'创建失败:{str(e)}', 'danger')
    
    return render_template('inbound/add.html',
                           products=products,
                           suppliers=suppliers,
                           locations=locations,
                           now=datetime.now(),
                           inspection_orders=InspectionOrder.query.filter_by(status='completed').all(),
                           selected_inspection=inspection)


def create_inbound_manual(request, products, suppliers, locations):
    """手动创建入库单"""
    # 接收表单数据
    supplier_id = request.form.get('supplier_id')
    related_order = request.form.get('related_order')
    delivery_order_no = request.form.get('delivery_order_no')
    inspection_cert_no = request.form.get('inspection_cert_no')
    signature = request.form.get('signature')
    inbound_date = request.form.get('inbound_date', datetime.now().strftime('%Y-%m-%d'))
    remark = request.form.get('remark')

    # 接收明细数据
    product_ids = request.form.getlist('product_id[]')
    location_ids = request.form.getlist('location_id[]')
    batch_nos = request.form.getlist('batch_no[]')
    quantities = request.form.getlist('quantity[]')
    unit_prices = request.form.getlist('unit_price[]')
    subtotals = request.form.getlist('subtotal[]')
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
    


    # 验证单据是否齐全
    if not related_order or not delivery_order_no or not inspection_cert_no:
        flash('入库所需单据不齐全（采购单号、送货单号、检验合格单号），暂停办理入库手续', 'danger')
        return render_template('inbound/add.html',
                               products=products,
                               suppliers=suppliers,
                               locations=locations,
                               now=datetime.now()
        )

    # 创建入库单
    order_no = generate_inbound_no()
    total_amount = sum(int(qty) for qty in quantities if qty.isdigit())
    
    # 查找采购单
    purchase_order = None
    if related_order:
        purchase_order = PurchaseOrder.query.filter_by(order_no=related_order).first()
    
    # 查找检验合格单
    inspection_order = None
    if inspection_cert_no:
        inspection_order = InspectionOrder.query.filter_by(order_no=inspection_cert_no).first()
    
    inbound_order = InboundOrder(
        order_no=order_no,
        supplier_id=supplier_id,
        related_order=related_order,
        delivery_order_no=related_order,  # 送货单号即采购单号
        inspection_cert_no=inspection_cert_no,
        purchase_order_id=purchase_order.id if purchase_order else None,
        inspection_order_id=inspection_order.id if inspection_order else None,
        operator_id=current_user.id,
        inbound_date=inbound_date,
        total_amount=total_amount,
        status='pending',  # 初始状态为待上架
        remark=remark
    )
    db.session.add(inbound_order)
    db.session.flush()

    # 处理入库明细并更新库存
    try:
        # 查找正常库位
        normal_locations = WarehouseLocation.query.filter_by(location_type='normal', status=True).all()
        if not normal_locations:
            flash('未设置正常区域，请先配置仓库位置', 'danger')
            return render_template('inbound/add.html',
                                   products=products,
                                   suppliers=suppliers,
                                   locations=locations,
                                   now=datetime.now()
            )

        for i in range(len(product_ids)):
            quantity = int(quantities[i]) if quantities[i].isdigit() else 0
            if quantity <= 0:
                flash('数量必须大于0', 'danger')
                return render_template('inbound/add.html',
                               products=products,
                               suppliers=suppliers,
                               locations=locations,
                               now=datetime.now()
                )

            product_id = product_ids[i]
            location_id = location_ids[i] if i < len(location_ids) and location_ids[i] else None
            batch_no = batch_nos[i] if i < len(batch_nos) and batch_nos[i] else f'B{datetime.now().strftime("%Y%m%d")}{i+1}'
            unit_price = float(unit_prices[i]) if i < len(unit_prices) and unit_prices[i] else 0.0
            subtotal = float(subtotals[i]) if i < len(subtotals) and subtotals[i] else 0.0
            production_date = production_dates[i] if i < len(production_dates) and production_dates[i] else None
            expire_date = expire_dates[i] if i < len(expire_dates) and expire_dates[i] else None

            # 如果没有指定库位，自动推荐
            if not location_id:
                recommended_location = recommend_location(int(product_id), normal_locations)
                location_id = recommended_location.id if recommended_location else normal_locations[0].id
            else:
                location_id = int(location_id)

            # 创建入库明细
            item = InboundItem(
                order_id=inbound_order.id,
                product_id=product_id,
                location_id=location_id,
                quantity=quantity,
                batch_no=batch_no,
                production_date=production_date,
                expire_date=expire_date,
                unit_price=unit_price,
                subtotal=subtotal
            )
            db.session.add(item)



        db.session.commit()
        flash('入库单创建成功，商品已入库并增加库存', 'success')
        return redirect(url_for('inbound.list'))
    except Exception as e:
        db.session.rollback()
        flash(f'创建失败:{str(e)}', 'danger')

    return render_template('inbound/add.html',
                           products=products,
                           suppliers=suppliers,
                           locations=locations,
                           now=datetime.now()
    )