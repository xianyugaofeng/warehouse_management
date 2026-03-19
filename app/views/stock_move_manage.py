from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
import logging
from app import db
from app.models.inventory import Inventory, WarehouseLocation, StockMoveOrder, StockMoveItem, InventoryChangeLog
from app.models.product import Product
from app.utils.auth import permission_required
from app.utils.helpers import generate_stock_move_no

# 配置日志记录器
logger = logging.getLogger(__name__)

stock_move_bp = Blueprint('stock_move', __name__)


# 库存移动单列表
@stock_move_bp.route('/list')
@permission_required('inventory_manage')
@login_required
def list():
    keyword = request.args.get('keyword', '')
    status = request.args.get('status', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    query = StockMoveOrder.query
    if keyword:
        query = query.filter(StockMoveOrder.order_no.ilike(f'%{keyword}%'))
    if status:
        query = query.filter_by(status=status)
    if start_date:
        query = query.filter(StockMoveOrder.move_date >= start_date)
    if end_date:
        query = query.filter(StockMoveOrder.move_date <= end_date)

    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = query.order_by(StockMoveOrder.create_time.desc()).paginate(page=page, per_page=per_page)
    orders = pagination.items

    status_options = [('pending', '待确认'), ('completed', '已完成'), ('canceled', '已取消')]
    return render_template('stock_move/list.html',
                           orders=orders,
                           pagination=pagination,
                           keyword=keyword,
                           status=status,
                           status_options=status_options,
                           start_date=start_date,
                           end_date=end_date
    )


# 添加库存移动单
@stock_move_bp.route('/add', methods=['GET', 'POST'])
@permission_required('inventory_manage')
@login_required
def add():
    products = Product.query.all()
    locations = WarehouseLocation.query.filter_by(status=True).all()

    if request.method == 'POST':
        # 接收表单数据
        reason = request.form.get('reason', '')
        remark = request.form.get('remark', '')

        # 接收明细数据
        product_ids = request.form.getlist('product_id[]')
        source_location_ids = request.form.getlist('source_location_id[]')
        target_location_ids = request.form.getlist('target_location_id[]')
        batch_nos = request.form.getlist('batch_no[]')
        quantities = request.form.getlist('quantity[]')

        # 验证数据
        if not product_ids or len(product_ids) != len(quantities):
            flash('请添加至少一条移库明细', 'danger')
            return render_template('stock_move/add.html',
                                   products=products,
                                   locations=locations,
                                   now=datetime.now()
            )

        # 验证每个明细
        for i in range(len(product_ids)):
            product_id = product_ids[i]
            source_location_id = source_location_ids[i]
            target_location_id = target_location_ids[i]
            quantity = int(quantities[i]) if quantities[i].isdigit() else 0

            if quantity <= 0:
                flash('移库数量必须大于0', 'danger')
                return render_template('stock_move/add.html',
                                       products=products,
                                       locations=locations,
                                       now=datetime.now()
                )

            if source_location_id == target_location_id:
                flash('源库位和目标库位不能相同', 'danger')
                return render_template('stock_move/add.html',
                                       products=products,
                                       locations=locations,
                                       now=datetime.now()
                )

            # 检查库位类型是否相同
            source_location = WarehouseLocation.query.get(source_location_id)
            target_location = WarehouseLocation.query.get(target_location_id)
            if not source_location or not target_location:
                flash(f'第{i+1}行：库位不存在', 'danger')
                return render_template('stock_move/add.html',
                                       products=products,
                                       locations=locations,
                                       now=datetime.now()
                )
            
            if source_location.location_type != target_location.location_type:
                flash(f'第{i+1}行：只能在同类型库位间移动（源库位类型：{source_location.location_type}，目标库位类型：{target_location.location_type}）', 'danger')
                return render_template('stock_move/add.html',
                                       products=products,
                                       locations=locations,
                                       now=datetime.now()
                )

            # 检查源库位库存是否充足
            move_batch_no = batch_nos[i] if i < len(batch_nos) else None
            inventory = Inventory.query.filter_by(
                product_id=product_id,
                location_id=source_location_id
            ).first()

            if not inventory or inventory.quantity < quantity:
                flash(f'第{i+1}行：源库位库存不足', 'danger')
                return render_template('stock_move/add.html',
                                       products=products,
                                       locations=locations,
                                       now=datetime.now()
                )

        # 创建移库单
        order_no = generate_stock_move_no()
        total_quantity = sum(int(qty) for qty in quantities if qty.isdigit())
        stock_move_order = StockMoveOrder(
            order_no=order_no,
            operator_id=current_user.id,
            move_date=datetime.now().date(),
            total_quantity=total_quantity,
            status='pending',
            reason=reason,
            remark=remark
        )
        db.session.add(stock_move_order)
        db.session.flush()

        # 创建移库明细
        try:
            for i in range(len(product_ids)):
                product_id = product_ids[i]
                source_location_id = source_location_ids[i]
                target_location_id = target_location_ids[i]
                move_batch_no = batch_nos[i] if i < len(batch_nos) else None
                quantity = int(quantities[i]) if quantities[i].isdigit() else 0

                if quantity <= 0:
                    continue

                # 创建移库明细
                item = StockMoveItem(
                    order_id=stock_move_order.id,
                    product_id=product_id,
                    source_location_id=source_location_id,
                    target_location_id=target_location_id,
                    quantity=quantity,
                    move_batch_no=move_batch_no
                )
                db.session.add(item)

            db.session.commit()
            flash('移库单创建成功，请确认后执行', 'success')
            return redirect(url_for('stock_move.list'))
        except Exception as e:
            db.session.rollback()
            flash(f'创建失败：{str(e)}', 'danger')

    return render_template('stock_move/add.html',
                           products=products,
                           locations=locations,
                           now=datetime.now()
    )


# 确认库存移动单
@stock_move_bp.route('/confirm/<int:order_id>', methods=['POST'])
@permission_required('inventory_manage')
@login_required
def confirm(order_id):
    stock_move_order = StockMoveOrder.query.get_or_404(order_id)

    if stock_move_order.status != 'pending':
        flash('该移库单已处理，无法重复确认', 'danger')
        return redirect(url_for('stock_move.list'))

    try:
        # 处理每个移库明细
        for item in stock_move_order.items:
            # 检查库位类型是否相同
            if item.source_location.location_type != item.target_location.location_type:
                flash(f'商品 {item.product.name if item.product else "未知"} 的源库位和目标库位类型不同，无法移库', 'danger')
                return redirect(url_for('stock_move.list'))
            
            # 查找源库位库存
            source_inventory = Inventory.query.filter_by(
                product_id=item.product_id,
                location_id=item.source_location_id
            ).first()

            if not source_inventory or source_inventory.quantity < item.quantity:
                flash(f'商品 {item.product.name if item.product else "未知"} 在源库位库存不足', 'danger')
                return redirect(url_for('stock_move.list'))

            # 查找目标库位库存
            target_inventory = Inventory.query.filter_by(
                product_id=item.product_id,
                location_id=item.target_location_id
            ).first()

            # 记录变更前的数量
            source_quantity_before = source_inventory.quantity
            target_quantity_before = target_inventory.quantity if target_inventory else 0
            
            if target_inventory:
                # 目标库位已有库存，增加数量
                target_inventory.quantity += item.quantity
                logger.info(f'移库确认：目标库位库存增加，商品:{item.product_id}, 数量:{item.quantity}')
            else:
                # 目标库位没有库存，创建新记录
                target_inventory = Inventory(
                    product_id=item.product_id,
                    location_id=item.target_location_id,
                    quantity=item.quantity,
                    batch_no=source_inventory.batch_no,
                    production_date=source_inventory.production_date,
                    expire_date=source_inventory.expire_date,
                    supplier_batch_no=source_inventory.supplier_batch_no,
                    remark='移库创建'
                )
                db.session.add(target_inventory)
                logger.info(f'移库确认：创建目标库位库存记录，商品:{item.product_id}, 数量:{item.quantity}')

            # 减少源库位库存
            source_inventory.quantity -= item.quantity
            logger.info(f'移库确认：源库位库存减少，商品:{item.product_id}, 数量:{item.quantity}')
            
            # 如果源库位库存减少到0，删除该库存记录
            if source_inventory.quantity == 0:
                db.session.delete(source_inventory)
                logger.info(f'移库确认：源库位库存减少到0，删除库存记录 {source_inventory.id}')

            # 记录源库位库存变更日志
            try:
                log = InventoryChangeLog(
                    inventory_id=source_inventory.id if source_inventory.quantity > 0 else None,
                    change_type='move_out',
                    quantity_before=source_quantity_before,
                    quantity_after=source_inventory.quantity if source_inventory.quantity > 0 else 0,
                    locked_quantity_before=source_inventory.locked_quantity,
                    locked_quantity_after=source_inventory.locked_quantity,
                    frozen_quantity_before=source_inventory.frozen_quantity,
                    frozen_quantity_after=source_inventory.frozen_quantity,
                    operator=current_user.username if current_user.is_authenticated else 'system',
                    reason=f'移库出库：{stock_move_order.reason or "库位调拨"}',
                    reference_id=stock_move_order.id,
                    reference_type='stock_move_order'
                )
                db.session.add(log)
            except Exception as e:
                logger.error(f'移库确认：创建源库位变更日志失败: {str(e)}')

            # 记录目标库位库存变更日志
            try:
                log = InventoryChangeLog(
                    inventory_id=target_inventory.id,
                    change_type='move_in',
                    quantity_before=target_quantity_before,
                    quantity_after=target_inventory.quantity,
                    locked_quantity_before=target_inventory.locked_quantity,
                    locked_quantity_after=target_inventory.locked_quantity,
                    frozen_quantity_before=target_inventory.frozen_quantity,
                    frozen_quantity_after=target_inventory.frozen_quantity,
                    operator=current_user.username if current_user.is_authenticated else 'system',
                    reason=f'移库入库：{stock_move_order.reason or "库位调拨"}',
                    reference_id=stock_move_order.id,
                    reference_type='stock_move_order'
                )
                db.session.add(log)
            except Exception as e:
                logger.error(f'移库确认：创建目标库位变更日志失败: {str(e)}')

        # 更新移库单状态为已完成
        stock_move_order.status = 'completed'
        logger.info(f'移库单 {stock_move_order.order_no} 状态更新为"已完成"')

        db.session.commit()
        flash('移库单确认成功，库存已更新', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'确认失败：{str(e)}', 'danger')

    return redirect(url_for('stock_move.list'))


# 取消库存移动单
@stock_move_bp.route('/cancel/<int:order_id>', methods=['POST'])
@permission_required('inventory_manage')
@login_required
def cancel(order_id):
    stock_move_order = StockMoveOrder.query.get_or_404(order_id)

    if stock_move_order.status != 'pending':
        flash('该移库单已处理，无法取消', 'danger')
        return redirect(url_for('stock_move.list'))

    try:
        stock_move_order.status = 'canceled'
        db.session.commit()
        flash('移库单已取消', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'取消失败：{str(e)}', 'danger')

    return redirect(url_for('stock_move.list'))


# 库存移动单详情
@stock_move_bp.route('/detail/<int:order_id>')
@permission_required('inventory_manage')
@login_required
def detail(order_id):
    stock_move_order = StockMoveOrder.query.get_or_404(order_id)
    return render_template('stock_move/detail.html', order=stock_move_order)