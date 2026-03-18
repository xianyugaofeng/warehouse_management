from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user, login_required
from datetime import datetime
import logging
from app import db
from app.models.inbound import InboundOrder, InboundItem
from app.models.inventory import WarehouseLocation, Inventory
from app.models.product import Product, Supplier
from app.models.inspection import InspectionOrder, InspectionItem

from app.utils.auth import permission_required
from app.utils.helpers import update_inventory, recommend_location

# 配置日志记录器
logger = logging.getLogger(__name__)

putaway_bp = Blueprint('putaway', __name__)

# 上架操作 - 为指定入库单进行上架
@putaway_bp.route('/putaway/<int:id>', methods=['GET', 'POST'])
@permission_required('inbound_manage')
@login_required
def putaway(id):
    inbound_order = InboundOrder.query.get_or_404(id)
    locations = WarehouseLocation.query.filter_by(location_type='normal', status=True).all()

    if request.method == 'POST':
        # 接收上架数据
        signature = request.form.get('signature')
        if not signature:
            flash('请仓库管理员签字确认', 'danger')
            return render_template('putaway/putaway.html', inbound_order=inbound_order, locations=locations)

        # 检查是否有正常库位
        if not locations:
            flash('未设置正常库位，请先配置仓库位置', 'danger')
            return render_template('putaway/putaway.html', inbound_order=inbound_order, locations=locations)

        try:
            # 处理每个入库明细的上架
            for item in inbound_order.items:
                # 获取用户选择的库位或自动推荐
                location_id = request.form.get(f'location_id_{item.id}')
                if not location_id:
                    # 自动推荐最佳库位
                    recommended_location = recommend_location(item.product_id, locations)
                    location_id = recommended_location.id if recommended_location else locations[0].id
                    logger.info(f'为入库单 {inbound_order.order_no} 的商品 {item.product_id} 自动推荐库位 {location_id}')
                else:
                    location_id = int(location_id)
                    logger.info(f'为入库单 {inbound_order.order_no} 的商品 {item.product_id} 手动选择库位 {location_id}')

                # 更新入库明细的库位和签字
                item.location_id = location_id
                item.signature = signature
                
                # 查找并更新库存记录的库位（从等待区转移到正常库位）
                # 库存状态会根据库位类型自动更新：waiting -> normal
                inventory = Inventory.query.filter_by(
                    product_id=item.product_id,
                    batch_no=item.batch_no
                ).first()
                
                if inventory:
                    # 更新库存记录的库位，状态会自动从"等待"变为"正常"
                    old_location_id = inventory.location_id
                    inventory.location_id = location_id
                    inventory.remark = '已上架'
                    logger.info(f'上架操作：库存记录 {inventory.id} 从库位 {old_location_id} 转移至库位 {location_id}，状态从"等待"变为"正常"')
                    
                    try:
                        # 记录库存转移的变更日志
                        from app.models.inventory import InventoryChangeLog
                        log = InventoryChangeLog(
                            inventory_id=inventory.id,
                            change_type='transfer',
                            quantity_before=inventory.quantity,
                            quantity_after=inventory.quantity,
                            locked_quantity_before=inventory.locked_quantity,
                            locked_quantity_after=inventory.locked_quantity,
                            frozen_quantity_before=inventory.frozen_quantity,
                            frozen_quantity_after=inventory.frozen_quantity,
                            operator=current_user.username if current_user.is_authenticated else 'system',
                            reason='上架操作，从等待区转移到正常库位',
                            reference_id=inbound_order.id,
                            reference_type='inbound_order'
                        )
                        db.session.add(log)
                        logger.info(f'上架操作：为库存记录 {inventory.id} 创建转移变更日志')
                    except Exception as e:
                        logger.error(f'上架操作：创建库存变更日志失败: {str(e)}')
                        # 继续执行上架操作，不因为日志记录失败而中断
                else:
                    # 如果库存记录不存在，创建新的库存记录
                    try:
                        # 使用update_inventory函数创建库存记录，它会自动触发库存变更日志
                        inventory = update_inventory(item.product_id, location_id, item.batch_no, item.quantity, is_bound=True)
                        logger.info(f'上架操作：创建新的库存记录，商品:{item.product_id}, 库位:{location_id}, 数量:{item.quantity}')
                    except Exception as e:
                        logger.error(f'上架操作：创建库存记录失败: {str(e)}')
                        raise

            # 更新入库单状态为已完成
            inbound_order.status = 'completed'
            logger.info(f'入库单 {inbound_order.order_no} 状态更新为"已完成"')
            
            db.session.commit()
            flash('上架成功，库存已更新', 'success')
            return redirect(url_for('inbound.list'))
        except Exception as e:
            db.session.rollback()
            flash(f'操作失败:{str(e)}', 'danger')

    return render_template('putaway/putaway.html', inbound_order=inbound_order, locations=locations)

# 上架管理首页 - 显示待上架的入库单
@putaway_bp.route('/list')
@permission_required('inbound_manage')
@login_required
def list():
    keyword = request.args.get('keyword', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    # 查找待上架的入库单（状态为pending）
    query = InboundOrder.query.filter_by(status='pending')
    if keyword:
        query = query.filter(InboundOrder.order_no.ilike(f'%{keyword}%') |
                             InboundOrder.inspection_cert_no.ilike(f'%{keyword}%'))
    if start_date:
        query = query.filter(InboundOrder.create_time >= start_date)
    if end_date:
        query = query.filter(InboundOrder.create_time <= end_date)

    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = query.order_by(InboundOrder.create_time.desc()).paginate(page=page, per_page=per_page)
    orders = pagination.items

    return render_template('putaway/list.html',
                           orders=orders,
                           pagination=pagination,
                           keyword=keyword,
                           start_date=start_date,
                           end_date=end_date
    )
