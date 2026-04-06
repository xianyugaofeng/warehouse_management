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
from app.utils.helpers import generate_inbound_no

# 配置日志记录器
logger = logging.getLogger(__name__)

inbound_bp = Blueprint('inbound', __name__)

# 入库单列表
@inbound_bp.route('/list')
@permission_required('inbound_manage')
@login_required
def list():
    keyword = request.args.get('keyword', '')     
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

    if request.method == 'POST':
        return create_inbound_manual(request, products, suppliers, locations)

    return render_template('inbound/add.html',
                           products=products,
                           suppliers=suppliers,
                           locations=locations,
                           now=datetime.now()
    )



def create_inbound_manual(request, products, suppliers, locations):
    """手动创建入库单"""
    supplier_id = request.form.get('supplier_id')
    product_id = request.form.get('product_id')
    related_order = request.form.get('related_order')
    delivery_order_no = request.form.get('delivery_order_no')
    inspection_cert_no = request.form.get('inspection_cert_no')
    inbound_date = request.form.get('inbound_date', datetime.now().strftime('%Y-%m-%d'))
    quantity = int(request.form.get('quantity', 0))
    unit_price = float(request.form.get('unit_price', 0))
    remark = request.form.get('remark')

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

    if not related_order or not delivery_order_no or not inspection_cert_no:
        flash('入库所需单据不齐全（采购单号、送货单号、检验合格单号），暂停办理入库手续', 'danger')
        return render_template('inbound/add.html',
                               products=products,
                               suppliers=suppliers,
                               locations=locations,
                               now=datetime.now()
        )

    purchase_order = None
    if related_order:
        purchase_order = PurchaseOrder.query.filter_by(order_no=related_order).first()
        if not purchase_order:
            flash(f'采购单号 {related_order} 不存在', 'danger')
            return render_template('inbound/add.html',
                                   products=products,
                                   suppliers=suppliers,
                                   locations=locations,
                                   now=datetime.now()
            )
        if purchase_order.status != 'completed':
            flash('采购单未完成，无法办理入库', 'danger')
            return render_template('inbound/add.html',
                                   products=products,
                                   suppliers=suppliers,
                                   locations=locations,
                                   now=datetime.now()
            )
    
    inspection_order = None
    if inspection_cert_no:
        inspection_order = InspectionOrder.query.filter_by(order_no=inspection_cert_no).first()
        if not inspection_order:
            flash(f'检验合格单号 {inspection_cert_no} 不存在', 'danger')
            return render_template('inbound/add.html',
                                   products=products,
                                   suppliers=suppliers,
                                   locations=locations,
                                   now=datetime.now()
            )
        if inspection_order.status != 'completed':
            flash('检验单未完成，无法办理入库', 'danger')
            return render_template('inbound/add.html',
                                   products=products,
                                   suppliers=suppliers,
                                   locations=locations,
                                   now=datetime.now()
            )
        if purchase_order and inspection_order.purchase_order_id != purchase_order.id:
            flash('检验单与采购单不匹配，无法办理入库', 'danger')
            return render_template('inbound/add.html',
                                   products=products,
                                   suppliers=suppliers,
                                   locations=locations,
                                   now=datetime.now()
            )
    
    # 创建入库单
    order_no = generate_inbound_no()
    subtotal = quantity * unit_price
    
    inbound_order = InboundOrder(
        order_no=order_no,
        supplier_id=supplier_id,
        related_order=related_order,
        delivery_order_no=delivery_order_no,
        inspection_cert_no=inspection_cert_no,
        purchase_order_id=purchase_order.id if purchase_order else None,
        inspection_order_id=inspection_order.id if inspection_order else None,
        operator_id=current_user.id,
        inbound_date=inbound_date,
        total_amount=quantity,
        status='pending',
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

        # 查找待处理区库位
        pending_locations = WarehouseLocation.query.filter_by(location_type='pending', status=True).all()
        if not pending_locations:
            flash('未设置待处理区域，请先配置仓库位置', 'danger')
            return render_template('inbound/add.html',
                                    products=products,
                                    suppliers=suppliers,
                                    locations=locations,
                                    now=datetime.now()
            )

        # 使用等待区库位
        waiting_location = waiting_locations[0]  # 使用第一个等待区库位
        location_id = waiting_location.id

        # 从待处理区查找与商品对应的库存记录
        pending_inventory = Inventory.query.filter(
            Inventory.product_id == product_id,
            Inventory.location_id.in_([loc.id for loc in pending_locations]),
            Inventory.inspection_order_id == inspection_order.id if inspection_order else None
        ).first()
        
        if pending_inventory:
            # 从待处理区找到库存记录，将其转移到等待区
            total_quantity = pending_inventory.quantity
            old_location_id = pending_inventory.location_id
            pending_inventory.location_id = waiting_location.id
            pending_inventory.remark = '入库待上架'
            
            logger.info(f'从待处理区转移库存记录 {pending_inventory.id} 至等待区，商品:{pending_inventory.product_id}, 数量:{pending_inventory.quantity}')
            
            # 记录库存转移的变更日志
            try:
                from app.models.inventory import InventoryChangeLog
                log = InventoryChangeLog(
                    inventory_id=pending_inventory.id,
                    change_type='inbound',
                    quantity_before=pending_inventory.quantity,
                    quantity_after=pending_inventory.quantity,
                    locked_quantity_before=pending_inventory.locked_quantity,
                    locked_quantity_after=pending_inventory.locked_quantity,
                    frozen_quantity_before=pending_inventory.frozen_quantity,
                    frozen_quantity_after=pending_inventory.frozen_quantity,
                    operator=current_user.username if current_user.is_authenticated else 'system',
                    reason='入库操作，从待处理区转移到等待区',
                    reference_id=inbound_order.id,
                    reference_type='inbound_order'
                )
                db.session.add(log)
                logger.info(f'入库操作：为库存记录 {pending_inventory.id} 创建转移变更日志')
            except Exception as e:
                logger.error(f'入库操作：创建库存变更日志失败: {str(e)}')
            
            # 更新入库单的总数量为实际转移的数量
            inbound_order.total_amount = total_quantity
            logger.info(f'更新入库单 {inbound_order.order_no} 总数量为 {total_quantity}')
            
            # 更新小计为实际转移数量的金额
            subtotal = total_quantity * unit_price

            # 创建入库明细
            item = InboundItem(
                order_id=inbound_order.id,
                product_id=product_id,
                location_id=location_id,
                quantity=total_quantity,
                production_date=pending_inventory.production_date,
                expire_date=pending_inventory.expire_date,
                unit_price=unit_price,
                subtotal=subtotal
            )
            db.session.add(item)
            logger.info(f'手动创建入库单 {inbound_order.order_no}，商品已从待处理区转移至等待区库位 {waiting_location.code}，库存状态为"等待"')
        else:
            flash('待处理区没有找到对应库存记录，请确认质检流程是否完成', 'danger')
            return render_template('inbound/add.html',
                                    products=products,
                                    suppliers=suppliers,
                                    locations=locations,
                                    now=datetime.now()
            )

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