from app.utils.scheduler import logger
from flask import Blueprint, render_template, request, url_for, flash, redirect
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from app import db
from app.models.inventory_count import InventoryCountTask, InventoryCountResult, InventoryAdjustment, BookInventory, InventoryAccuracy, InventoryCountTaskSchedule, InventoryCountTaskLog
from app.models.inventory import Inventory, WarehouseLocation
from app.models.product import Product, Supplier
from app.utils.auth import permission_required
from app.utils.helpers import generate_inventory_count_task_no, generate_inventory_adjustment_no, validate_book_inventory
from flask import current_app
from app.utils.scheduler import add_schedule

inventory_count_bp = Blueprint('inventory_count', __name__)

# 盘点任务列表
@inventory_count_bp.route('/task/list')
@permission_required('inventory_manage')
@login_required
def task_list():
    keyword = request.args.get('keyword', '')
    status = request.args.get('status', '')
    task_type = request.args.get('type', '')

    query = InventoryCountTask.query
    if keyword:
        query = query.filter(InventoryCountTask.task_no.ilike(f'%{keyword}%') |
                             InventoryCountTask.name.ilike(f'%{keyword}%'))

    if status:
        query = query.filter_by(status=status)

    if task_type: 
        query = query.filter_by(type=task_type)
    
    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = query.order_by(InventoryCountTask.create_time.desc()).paginate(page=page, per_page=per_page)
    tasks = pagination.items

    return render_template('inventory_count/task_list.html',
                           tasks=tasks,
                           pagination=pagination,
                           keyword=keyword,
                           status=status,
                           task_type=task_type
    )
    
# 创建盘点任务
@inventory_count_bp.route('/task/create', methods=['GET', 'POST'])
@permission_required('inventory_manage')
@login_required
def task_create():
    suppliers = Supplier.query.all()
    locations = WarehouseLocation.query.filter_by(status=True).all()

    if request.method == 'POST':
        name = request.form.get('name')
        task_type = request.form.get('type')
        area = request.form.get('area')
        supplier_id = request.form.get('supplier_id')
        cycle_days = request.form.get('cycle_days', type=int)
        threshold = request.form.get('threshold', type=int)
        remark = request.form.get('remark')

        # 验证数据
        if not name or not task_type:
            flash('任务名称和类型不能为空', 'danger')
            return render_template('inventory_count/task_create.html',
                                   suppliers=suppliers,
                                   locations=locations
            )
        
        # 创建盘点任务
        task_no = generate_inventory_count_task_no()
        task = InventoryCountTask(
            task_no=task_no,
            name=name,
            type=task_type,
            area=area,
            supplier_id=supplier_id,
            cycle_days=cycle_days,
            threshold=threshold,
            remark=remark
        )

        db.session.add(task)
        db.session.commit()
        flash('盘点任务创建成功', 'success')
        return redirect(url_for('inventory_count.task_list'))

    return render_template('inventory_count/task_create.html', 
                           suppliers=suppliers,
                           locations=locations
    )

# 执行盘点任务
@inventory_count_bp.route('/task/execute/<int:task_id>', methods=['GET', 'POST'])
@permission_required('inventory_manage')
@login_required
def task_execute(task_id):
    task = InventoryCountTask.query.get_or_404(task_id)

    if task.status != 'pending':
        flash('该任务状态不允许执行', 'danger')
        return redirect(url_for('inventory_count.task_list'))
    
    # 根据任务类型获取需要盘点的库存
    query = Inventory.query
    if task.area:
        query = query.join(WarehouseLocation).filter(WarehouseLocation.area == task.area)
        # 如果盘点任务指定了区域（area）则通过 join 关联 WarehouseLocation（仓库位置）表
        # 并筛选出该区域下的库存记录（WarehouseLocation.area == task.area）
    if task.supplier_id:
        query = query.join(Product).filter(Product.supplier_id == task.supplier_id)
        # 如果任务指定了供应商 ID（supplier_id）则通过 join 关联 Product（产品）表
        # 并筛选出属于该供应商的产品库存（Product.supplier_id == task.supplier_id）
    
    inventories = query.all()
    # 执行最终构建的查询，获取所有符合条件的库存记录列表

    if request.method == 'POST':
        # 更新任务状态为执行中
        task.status = 'in_progress'
        task.start_time = datetime.now()
        task.operator_id = current_user.id

        # 获取盘点容差配置
        tolerance = current_app.config.get('INVENTORY_COUNT_TOLERANCE', 5)
        
        # 处理盘点结果
        for inventory in inventories:
            actual_quantity = request.form.get(f'actual_quantity_{inventory.id}', type=int)
            if actual_quantity is not None:
                # 从系统账面库存获取预期数量
                book_inventory = BookInventory.query.filter_by(
                    product_id=inventory.product_id,
                    location_id=inventory.location_id,
                    batch_no=inventory.batch_no
                ).first()
                expected_quantity = book_inventory.available_quantity if book_inventory else inventory.quantity
                
                # 实际盘点数量为系统账面库存的可用数量
                actual_quantity = expected_quantity
                difference = actual_quantity - inventory.quantity
                
                # 判断是否在容差范围内
                is_within_tolerance = abs(difference) <= tolerance
                
                # 确定处理状态
                if difference == 0:
                    result_status = 'matched'  # 完全匹配
                    adjust_type = None
                elif is_within_tolerance:
                    result_status = 'auto_adjusted'  # 容差内自动调整
                    adjust_type = 'auto_count_adjustment'
                else:
                    result_status = 'manual_processing'  # 超出容差，需要人工处理
                    adjust_type = 'manual_count_adjustment'

                # 创建盘点结果 
                result = InventoryCountResult(
                    task_id = task.id,
                    inventory_id = inventory.id,
                    expected_quantity = expected_quantity,
                    actual_quantity = actual_quantity,
                    difference = difference,
                    status = result_status
                )
                db.session.add(result)

                # 处理差异（容差范围内自动过账，超出容差需要人工审核）
                if difference != 0:
                    if is_within_tolerance:
                        # 容差范围内：自动过账库存调整单
                        adjustment_no = generate_inventory_adjustment_no()
                        adjustment = InventoryAdjustment(
                            adjustment_no = adjustment_no,
                            inventory_id = inventory.id,
                            before_quantity = inventory.quantity,
                            after_quantity = expected_quantity,
                            adjustment_quantity = expected_quantity - inventory.quantity,
                            type='count_adjustment',
                            reason=f'{task.type}触发的盘点调整（差异{difference}，在容差±{tolerance}范围内自动过账）',
                            operator_id = current_user.id,
                            count_task_id=task.id
                        )

                        # 更新实物库存为期望库存数量（系统账面库存的可用数量）
                        inventory.quantity = expected_quantity
                        
                        # 同步更新系统账面库存：账面数量等于inventory.quantity，在途和已分配数量清零
                        if book_inventory:
                            book_inventory.book_quantity = expected_quantity
                            book_inventory.in_transit_quantity = 0
                            book_inventory.allocated_quantity = 0
                            # 验证系统账面库存
                            is_valid, message = validate_book_inventory(book_inventory)
                            if not is_valid:
                                flash(f'系统账面库存验证失败: {message}', 'warning')
                        
                        # 更新盘点结果状态
                        result.adjust_reason = f'容差范围内自动过账（差异{difference}件）'
                        result.processor_id = current_user.id
                        result.process_time = datetime.now()

                        db.session.add(adjustment)
                        
                        # 自动生成会计分录（这里可以扩展为实际的会计系统接口）
                        # 借记/贷记"存货调整科目"
                        # 实际实现时需要根据企业的会计科目体系进行配置
                    else:
                        # 超出容差：标记为需要人工处理
                        result.adjust_reason = f'差异{difference}件超出容差范围±{tolerance}，需要人工审核'
                        flash(f'库存 {inventory.product.name if inventory.product else inventory.id} 差异{difference}件超出容差范围，需要人工处理', 'warning')
                    
        # 完成任务
        task.status = 'completed'
        task.end_time = datetime.now()

        # 创建执行日志
        log = InventoryCountTaskLog(
            task_id=task.id,
            start_time=task.start_time,
            end_time=task.end_time,
            status='success',
            execution_type='manual',
            operator_id=current_user.id
        )
        db.session.add(log)

        # 检查是否需要自动启动周期运行
        if task.cycle_days and task.cycle_days > 0:
            # 检查是否已有调度
            existing_schedule = InventoryCountTaskSchedule.query.filter_by(
                task_id=task.id,
                status='active'
            ).first()
            
            if not existing_schedule:
                # 计算间隔小时数
                interval_hours = task.cycle_days * 24
                # 添加调度任务
                add_schedule(task.id, interval_hours=interval_hours)
                flash('盘点任务执行完成，已自动启动周期运行', 'success')
            else:
                flash('盘点任务执行完成', 'success')
        else:
            flash('盘点任务执行完成', 'success')

        db.session.commit()
        return redirect(url_for('inventory_count.task_detail', task_id=task.id))

    # 获取系统账面库存数据
    book_inventories = BookInventory.query.all()
    
    return render_template('inventory_count/task_execute.html',
                           task=task,
                           inventories=inventories,
                           book_inventories=book_inventories
    )        

# 盘点任务详情
@inventory_count_bp.route('/task/detail/<int:task_id>')
@permission_required('inventory_manage')
@login_required
def task_detail(task_id):
    task = InventoryCountTask.query.get_or_404(task_id)
    results = task.results.all()

    # 计算准确率
    total_items = len(results)
    accurate_items = sum(1 for r in results if r.difference == 0) 
    accuracy_rate = round((accurate_items / total_items * 100), 2) if total_items > 0 else 100
    
    # 创建库存准确率记录
    if total_items > 0:
        # 检查是否已有当天的准确率记录
        today = datetime.now().date()
        existing_accuracy = InventoryAccuracy.query.filter_by(date=today).first()
        
        if existing_accuracy:
            # 更新现有记录
            existing_accuracy.total_items = total_items
            existing_accuracy.accurate_items = accurate_items
            existing_accuracy.accuracy_rate = accuracy_rate
        else:
            # 创建新记录
            accuracy = InventoryAccuracy(
                date=today,
                total_items=total_items,
                accurate_items=accurate_items,
                accuracy_rate=accuracy_rate
            )
            db.session.add(accuracy)
        
        db.session.commit()
    
    return render_template('inventory_count/task_detail.html',
                           task=task, 
                           results=results,
                           total_items=total_items,
                           accurate_items=accurate_items,
                           accuracy_rate=accuracy_rate
    )

# 库存调整历史
@inventory_count_bp.route('/adjustment/list')
@permission_required('inventory_manage')
@login_required
def adjustment_list():
    keyword = request.args.get('keyword', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    query = InventoryAdjustment.query
    if keyword:
        query = query.join(Inventory).join(Product).filter(Product.name.ilike(f'%{keyword}%') |
                                                           Product.code.ilike(f'%{keyword}%') |
                                                           InventoryAdjustment.adjustment_no.ilike(f'%{keyword}%')
        )
    
    if start_date:
        try:
            start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(InventoryAdjustment.create_time >= start_datetime)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
            end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
            query = query.filter(InventoryAdjustment.create_time <= end_datetime)
        except ValueError:
            pass

    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = query.order_by(InventoryAdjustment.create_time.desc()).paginate(page=page, per_page=per_page)
    adjustments = pagination.items

    return render_template('inventory_count/adjustment_list.html',
                            adjustments=adjustments,
                            pagination=pagination,
                            keyword=keyword,
                            start_date=start_date,
                            end_date=end_date 
    )

# 系统账面库存管理
@inventory_count_bp.route('/book/list')
@permission_required('inventory_manage')
@login_required
def book_inventory_list():
    keyword = request.args.get('keyword', '')
    location_id = request.args.get('location_id', '')

    query = BookInventory.query.join(Product).join(WarehouseLocation)
    if keyword:
        query = query.filter(Product.name.ilike(f'%{keyword}%') | 
                             Product.code.ilike(f'%{keyword}%')
        )
    
    if location_id:
        query = query.filter(BookInventory.location_id == location_id)
    
    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = query.order_by(BookInventory.update_time.desc()).paginate(page=page, per_page=per_page)
    book_inventories = pagination.items

    locations = WarehouseLocation.query.filter_by(status=True).all()

    return render_template('inventory_count/book_inventory_list.html',
                           book_inventories=book_inventories,
                           pagination=pagination,
                           keyword=keyword,
                           location_id=location_id,
                           locations=locations
    )

# 库存准确率报表
@inventory_count_bp.route('/accuracy/report')
@permission_required('inventory_manage')
@login_required
def accuracy_report():
    # 获取近30天的准确率数据
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=30)

    accuracies = InventoryAccuracy.query.filter(
        InventoryAccuracy.date >= start_date,
        InventoryAccuracy.date <= end_date
    ).order_by(InventoryAccuracy.date).all()

    # 格式化数据
    dates = []
    rates = []
    for acc in accuracies:
        dates.append(acc.date.strftime('%Y-%m-%d'))
        rates.append(acc.accuracy_rate)

    return render_template('inventory_count/accuracy_report.html',
                           accuracies=accuracies,
                           dates=dates,
                           rates=rates,
                           start_date=start_date,
                           end_date=end_date
    )


# 调度管理
@inventory_count_bp.route('/schedule/list')
@permission_required('inventory_manage')
@login_required
def schedule_list():
    schedules = InventoryCountTaskSchedule.query.all()
    return render_template('inventory_count/schedule_list.html',
                           schedules=schedules)


# 暂停调度
@inventory_count_bp.route('/schedule/pause/<int:schedule_id>')
@permission_required('inventory_manage')
@login_required
def schedule_pause(schedule_id):
    from app.utils.scheduler import pause_schedule
    if pause_schedule(schedule_id):
        flash('调度已暂停', 'success')
    else:
        flash('调度暂停失败', 'danger')
    return redirect(url_for('inventory_count.schedule_list'))


# 恢复调度
@inventory_count_bp.route('/schedule/resume/<int:schedule_id>')
@permission_required('inventory_manage')
@login_required
def schedule_resume(schedule_id):
    from app.utils.scheduler import resume_schedule
    if resume_schedule(schedule_id):
        flash('调度已恢复', 'success')
    else:
        flash('调度恢复失败', 'danger')
    return redirect(url_for('inventory_count.schedule_list'))


# 停止调度
@inventory_count_bp.route('/schedule/stop/<int:schedule_id>')
@permission_required('inventory_manage')
@login_required
def schedule_stop(schedule_id):
    from app.utils.scheduler import remove_schedule
    if remove_schedule(schedule_id):
        flash('调度已停止', 'success')
    else:
        flash('调度停止失败', 'danger')
    return redirect(url_for('inventory_count.schedule_list'))


# 执行日志
@inventory_count_bp.route('/log/list')
@permission_required('inventory_manage')
@login_required
def log_list():
    keyword = request.args.get('keyword', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    query = InventoryCountTaskLog.query
    if keyword:
        query = query.join(InventoryCountTask).filter(
            InventoryCountTask.task_no.ilike(f'%{keyword}%') |
            InventoryCountTask.name.ilike(f'%{keyword}%')
        )

    if start_date:
        try:
            start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(InventoryCountTaskLog.start_time >= start_datetime)
        except ValueError:
            pass

    if end_date:
        try:
            end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
            end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
            query = query.filter(InventoryCountTaskLog.start_time <= end_datetime)
        except ValueError:
            pass

    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = query.order_by(InventoryCountTaskLog.start_time.desc()).paginate(page=page, per_page=per_page)
    logs = pagination.items

    return render_template('inventory_count/log_list.html',
                           logs=logs,
                           pagination=pagination,
                           keyword=keyword,
                           start_date=start_date,
                           end_date=end_date)


# 手动启动周期运行
@inventory_count_bp.route('/task/start_schedule/<int:task_id>', methods=['GET', 'POST'])
@permission_required('inventory_manage')
@login_required
def task_start_schedule(task_id):
    task = InventoryCountTask.query.get_or_404(task_id)

    if request.method == 'POST':
        interval_hours = request.form.get('interval_hours', type=int, default=24)
        max_executions = request.form.get('max_executions', type=int, default=0)

        # 检查是否已有调度
        existing_schedule = InventoryCountTaskSchedule.query.filter_by(
            task_id=task.id,
            status='active'
        ).first()

        if existing_schedule:
            flash('该任务已有活跃的调度', 'danger')
            return redirect(url_for('inventory_count.task_detail', task_id=task.id))

        # 添加调度
        add_schedule(task_id, interval_hours=interval_hours, max_executions=max_executions)
        flash('周期运行已启动', 'success')
        return redirect(url_for('inventory_count.task_detail', task_id=task.id))

    return render_template('inventory_count/task_start_schedule.html',
                           task=task)


# 同步系统账面库存
@inventory_count_bp.route('/book/sync', methods=['POST'])
@permission_required('inventory_manage')
@login_required
def book_inventory_sync():
    """同步系统账面库存与实物库存"""
    from app.utils.helpers import sync_book_inventory
    from app.models.inventory import Inventory
    
    try:
        # 获取所有实物库存
        inventories = Inventory.query.all()
        synced_count = 0
        error_count = 0
        
        for inventory in inventories:
            try:
                sync_book_inventory(
                    inventory.product_id,
                    inventory.location_id,
                    inventory.batch_no,
                    operator_id=current_user.id  # 传递当前用户ID
                )
                synced_count += 1
            except Exception as e:
                error_count += 1
                logger.error(f'同步系统账面库存失败: {str(e)}')
        
        flash(f'系统账面库存同步完成: 成功{synced_count}条, 失败{error_count}条', 'success')
    except Exception as e:
        flash(f'系统账面库存同步失败: {str(e)}', 'danger')
    
    return redirect(url_for('inventory_count.book_inventory_list'))


# 验证系统账面库存
@inventory_count_bp.route('/book/validate', methods=['POST'])
@permission_required('inventory_manage')
@login_required
def book_inventory_validate():
    """验证系统账面库存数据"""
    from app.utils.helpers import validate_book_inventory
    
    try:
        book_inventories = BookInventory.query.all()
        valid_count = 0
        invalid_count = 0
        errors = []
        
        for bi in book_inventories:
            is_valid, message = validate_book_inventory(bi)
            if is_valid:
                valid_count += 1
            else:
                invalid_count += 1
                errors.append(f'{bi.product.name if bi.product else bi.product_id} - {bi.location.code if bi.location else bi.location_id}: {message}')
        
        flash(f'系统账面库存验证完成: 有效{valid_count}条, 无效{invalid_count}条', 'success' if invalid_count == 0 else 'warning')
        
        if errors:
            for error in errors[:10]:  # 只显示前10个错误
                flash(error, 'danger')
                
    except Exception as e:
        flash(f'系统账面库存验证失败: {str(e)}', 'danger')
    
    return redirect(url_for('inventory_count.book_inventory_list'))