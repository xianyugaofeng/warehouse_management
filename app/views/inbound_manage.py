from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user, login_required
from datetime import datetime
import logging
from app import db
from app.models.inbound import InboundOrder, InboundItem
from app.models.product import Product, Supplier
from app.models.inventory import WarehouseLocation, Inventory
from app.models.purchase import PurchaseOrder
from app.models.inspection import InspectionOrder
from app.utils.auth import permission_required
from app.utils.helpers import generate_inbound_no, update_inventory, recommend_location

# 配置日志记录器
logger = logging.getLogger(__name__)

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
    
    # 验证采购单状态
    if inspection.purchase_order and inspection.purchase_order.status != 'completed':
        flash('采购单未完成，无法办理入库', 'danger')
        return render_template('inbound/add.html',
                               products=products,
                               suppliers=suppliers,
                               locations=locations,
                               now=datetime.now(),
                               inspection_orders=InspectionOrder.query.filter_by(status='completed').all(),
                               selected_inspection=inspection)
    
    # 查找等待区库位
    waiting_locations = WarehouseLocation.query.filter_by(location_type='waiting', status=True).all()
    if not waiting_locations:
        flash('未设置等待区域，请先配置仓库位置', 'danger')
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
        # 处理检验合格的商品（一个采购单对应一种商品）
        if inspection.qualified_quantity > 0:
            # 获取采购单中商品的单价
            unit_price = inspection.purchase_order.unit_price if inspection.purchase_order else 0
            
            # 创建批次号
            batch_no = f'B{datetime.now().strftime("%Y%m%d")}{inspection.id}'
            
            # 使用等待区库位
            waiting_location = waiting_locations[0]  # 使用第一个等待区库位
            
            # 查找待处理区库位
            pending_locations = WarehouseLocation.query.filter_by(location_type='pending', status=True).all()
            if not pending_locations:
                flash('未设置待处理区域，请先配置仓库位置', 'danger')
                return render_template('inbound/add.html',
                                       products=products,
                                       suppliers=suppliers,
                                       locations=locations,
                                       now=datetime.now(),
                                       inspection_orders=InspectionOrder.query.filter_by(status='completed').all(),
                                       selected_inspection=inspection)
            
            # 从待处理区查找与检验合格单关联的库存记录
            pending_inventories = Inventory.query.filter(
                Inventory.product_id == inspection.purchase_order.product_id,
                Inventory.location_id.in_([loc.id for loc in pending_locations]),
                Inventory.inspection_order_id == inspection.id
            ).all()
            
            if pending_inventories:
                # 从待处理区找到库存记录，将其转移到等待区
                total_quantity = 0
                for inventory in pending_inventories:
                    # 更新库存记录的库位，从待处理区转移到等待区
                    old_location_id = inventory.location_id
                    inventory.location_id = waiting_location.id
                    inventory.remark = '入库待上架'
                    total_quantity += inventory.quantity
                    logger.info(f'从待处理区转移库存记录 {inventory.id} 至等待区，商品:{inventory.product_id}, 数量:{inventory.quantity}')
                
                # 创建入库明细
                inbound_item = InboundItem(
                    order_id=inbound_order.id,
                    product_id=inspection.purchase_order.product_id,
                    location_id=waiting_location.id,
                    quantity=total_quantity,
                    batch_no=batch_no,
                    unit_price=unit_price,
                    subtotal=unit_price * total_quantity
                )
                db.session.add(inbound_item)
                logger.info(f'从检验单创建入库单 {inbound_order.order_no}，商品已从待处理区转移至等待区库位 {waiting_location.code}，库存状态为"等待"')
            else:
                # 如果待处理区没有找到库存记录，创建新的库存记录
                # 创建入库明细
                inbound_item = InboundItem(
                    order_id=inbound_order.id,
                    product_id=inspection.purchase_order.product_id,
                    location_id=waiting_location.id,
                    quantity=inspection.qualified_quantity,
                    batch_no=batch_no,
                    unit_price=unit_price,
                    subtotal=unit_price * inspection.qualified_quantity
                )
                db.session.add(inbound_item)
                
                # 创建库存记录（处于等待状态，对应入库管理模块的"待上架"状态）
                inventory = Inventory(
                    product_id=inspection.purchase_order.product_id,
                    location_id=waiting_location.id,
                    quantity=inspection.qualified_quantity,
                    batch_no=batch_no,
                    inspection_order_id=inspection.id,
                    remark='入库待上架'
                )
                db.session.add(inventory)
                logger.info(f'从检验单创建入库单 {inbound_order.order_no}，商品已存放至等待区库位 {waiting_location.code}，库存状态为"等待"')
        
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
    product_id = request.form.get('product_id')
    related_order = request.form.get('related_order')
    delivery_order_no = request.form.get('delivery_order_no')
    inspection_cert_no = request.form.get('inspection_cert_no')
    inbound_date = request.form.get('inbound_date', datetime.now().strftime('%Y-%m-%d'))
    quantity = int(request.form.get('quantity', 0))
    unit_price = float(request.form.get('unit_price', 0))
    batch_no = request.form.get('batch_no', '')
    production_date = request.form.get('production_date')
    expire_date = request.form.get('expire_date')
    remark = request.form.get('remark')

    # 验证数据
    if not product_id:
        flash('请选择商品', 'danger')
        return render_template('inbound/add.html',
                               products=products,
                               suppliers=suppliers,
                               locations=locations,
                               now=datetime.now()
        )

    if quantity <= 0:
        flash('数量必须大于0', 'danger')
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

    # 查找采购单
    purchase_order = None
    if related_order:
        purchase_order = PurchaseOrder.query.filter_by(order_no=related_order).first()
        # 验证采购单状态
        if purchase_order and purchase_order.status != 'completed':
            flash('采购单未完成，无法办理入库', 'danger')
            return render_template('inbound/add.html',
                                   products=products,
                                   suppliers=suppliers,
                                   locations=locations,
                                   now=datetime.now()
            )
    
    # 查找检验合格单
    inspection_order = None
    if inspection_cert_no:
        inspection_order = InspectionOrder.query.filter_by(order_no=inspection_cert_no).first()
    
    # 创建入库单
    order_no = generate_inbound_no()
    subtotal = quantity * unit_price
    
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
        total_amount=quantity,
        status='pending',  # 初始状态为待上架
        remark=remark
    )
    db.session.add(inbound_order)
    db.session.flush()

    # 处理入库明细并更新库存
    try:
        # 查找等待区库位
        waiting_locations = WarehouseLocation.query.filter_by(location_type='waiting', status=True).all()
        if not waiting_locations:
            flash('未设置等待区域，请先配置仓库位置', 'danger')
            return render_template('inbound/add.html',
                                   products=products,
                                   suppliers=suppliers,
                                   locations=locations,
                                   now=datetime.now()
            )

        # 如果没有指定批次号，自动生成
        if not batch_no:
            batch_no = f'B{datetime.now().strftime("%Y%m%d")}{inbound_order.id}'

        # 使用等待区库位
        waiting_location = waiting_locations[0]  # 使用第一个等待区库位
        location_id = waiting_location.id

        # 创建入库明细
        item = InboundItem(
            order_id=inbound_order.id,
            product_id=product_id,
            location_id=location_id,
            quantity=quantity,
            batch_no=batch_no,
            production_date=production_date if production_date else None,
            expire_date=expire_date if expire_date else None,
            unit_price=unit_price,
            subtotal=subtotal
        )
        db.session.add(item)
        
        # 创建库存记录（处于等待状态，对应入库管理模块的"待上架"状态）
        # 规则：入库单创建初期，商品存放至"等待区"库位，库存状态为"等待"
        inventory = Inventory(
            product_id=product_id,
            location_id=location_id,
            quantity=quantity,
            batch_no=batch_no,
            production_date=production_date if production_date else None,
            expire_date=expire_date if expire_date else None,
            remark='入库待上架'
        )
        db.session.add(inventory)
        logger.info(f'手动创建入库单 {inbound_order.order_no}，商品已存放至等待区库位 {waiting_location.code}，库存状态为"等待"')

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