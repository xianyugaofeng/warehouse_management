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
            
            # 检查目标库位是否有其他商品的库存
            target_inventory = Inventory.query.filter_by(
                product_id=product_id,
                location_id=target_location_id
            ).first()
            if not target_inventory:
                existing_inventory = Inventory.query.filter_by(
                    location_id=target_location_id
                ).first()
                if existing_inventory:
                    flash(f'第{i+1}行：目标库位已存在其他商品 {existing_inventory.product.name if existing_inventory.product else "未知"}，无法移库', 'danger')
                    return render_template('stock_move/add.html',
                                           products=products,
                                           locations=locations,
                                           now=datetime.now()
                    )

        # 创建移库单并执行移库操作
        order_no = generate_stock_move_no()
        total_quantity = sum(int(qty) for qty in quantities if qty.isdigit())
        stock_move_order = StockMoveOrder(
            order_no=order_no,
            operator_id=current_user.id,
            move_date=datetime.now().date(),
            total_quantity=total_quantity,
            status='completed',
            reason=reason,
            remark=remark
        )
        db.session.add(stock_move_order)
        db.session.flush()

        # 创建移库明细并执行库存移动
        try:
            for i in range(len(product_ids)):
                product_id = int(product_ids[i])
                source_location_id = int(source_location_ids[i])
                target_location_id = int(target_location_ids[i])
                quantity = int(quantities[i]) if quantities[i].isdigit() else 0

                if quantity <= 0:
                    continue

                # 创建移库明细
                item = StockMoveItem(
                    order_id=stock_move_order.id,
                    product_id=product_id,
                    source_location_id=source_location_id,
                    target_location_id=target_location_id,
                    quantity=quantity
                )
                db.session.add(item)
                db.session.flush()

                # 执行库存移动
                source_inventory = Inventory.query.filter_by(
                    product_id=product_id,
                    location_id=source_location_id
                ).first()

                target_inventory = Inventory.query.filter_by(
                    product_id=product_id,
                    location_id=target_location_id
                ).first()

                # 记录变更前的数量
                source_quantity_before = source_inventory.quantity
                source_inventory_id = source_inventory.id
                target_quantity_before = target_inventory.quantity if target_inventory else 0

                # 更新目标库位库存
                if target_inventory:
                    target_inventory.quantity += quantity
                    logger.info(f'移库：目标库位库存增加，商品:{product_id}, 数量:{quantity}')
                else:
                    target_inventory = Inventory(
                        product_id=product_id,
                        location_id=target_location_id,
                        quantity=quantity,
                        production_date=source_inventory.production_date,
                        expire_date=source_inventory.expire_date,
                        remark='移库创建'
                    )
                    db.session.add(target_inventory)
                    db.session.flush()
                    logger.info(f'移库：创建目标库位库存记录，商品:{product_id}, 数量:{quantity}')

                # 更新源库位库存
                source_inventory.quantity -= quantity
                logger.info(f'移库：源库位库存减少，商品:{product_id}, 数量:{quantity}')

                # 判断是否需要删除源库位库存记录
                should_delete_source = source_inventory.quantity == 0
                if should_delete_source:
                    db.session.delete(source_inventory)
                    logger.info(f'移库：源库位库存减少到0，删除库存记录 {source_inventory_id}')

                # 记录源库位库存变更日志
                try:
                    log = InventoryChangeLog(
                        inventory_id=source_inventory_id if not should_delete_source else None,
                        change_type='move',
                        quantity_before=source_quantity_before,
                        quantity_after=0 if should_delete_source else source_inventory.quantity,
                        locked_quantity_before=0,
                        locked_quantity_after=0,
                        frozen_quantity_before=0,
                        frozen_quantity_after=0,
                        operator=current_user.username if current_user.is_authenticated else 'system',
                        reason=f'移库：{reason or "库位调拨"}',
                        reference_id=stock_move_order.id,
                        reference_type='stock_move_order'
                    )
                    db.session.add(log)
                except Exception as e:
                    logger.error(f'移库：创建源库位变更日志失败: {str(e)}')

                # 记录目标库位库存变更日志
                try:
                    log = InventoryChangeLog(
                        inventory_id=target_inventory.id,
                        change_type='move_in',
                        quantity_before=target_quantity_before,
                        quantity_after=target_inventory.quantity,
                        locked_quantity_before=0,
                        locked_quantity_after=0,
                        frozen_quantity_before=0,
                        frozen_quantity_after=0,
                        operator=current_user.username if current_user.is_authenticated else 'system',
                        reason=f'移库入库：{reason or "库位调拨"}',
                        reference_id=stock_move_order.id,
                        reference_type='stock_move_order'
                    )
                    db.session.add(log)
                except Exception as e:
                    logger.error(f'移库：创建目标库位变更日志失败: {str(e)}')

            db.session.commit()
            flash('移库成功，库存已更新', 'success')
            return redirect(url_for('stock_move.list'))
        except Exception as e:
            db.session.rollback()
            flash(f'移库失败：{str(e)}', 'danger')

    return render_template('stock_move/add.html',
                           products=products,
                           locations=locations,
                           now=datetime.now()
    )

# 库存移动单详情
@stock_move_bp.route('/detail/<int:order_id>')
@permission_required('inventory_manage')
@login_required
def detail(order_id):
    stock_move_order = StockMoveOrder.query.get_or_404(order_id)
    return render_template('stock_move/detail.html', order=stock_move_order)