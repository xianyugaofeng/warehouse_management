from app.models import inventory
from flask import Blueprint, render_template, request, url_for, flash, redirect
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from app import db
from app.models.inventory_count import InventoryCountTask, InventoryCountResult, InventoryAdjustment, VirtualInventory, InventoryAccuracy
from app.models.inventory import Inventory, WarehouseLocation
from app.models.product import Product, Supplier
from app.utils.auth import perission_required, permission_required
from app.utils.helps import generate_inventory_count_task_no, generate_inventory_adjustment_no

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
    pagination = query.order_by(InventoryCountTask.create_time.desc().paginate(page=page, per_page=per_page))
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
@permission_required
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
        query = query.join(Product).filter(Product.supplier_id == task.suppplier_id)
        # 如果任务指定了供应商 ID（supplier_id）则通过 join 关联 Product（产品）表
        # 并筛选出属于该供应商的产品库存（Product.supplier_id == task.supplier_id）
    
    inventories = query.all()
    # 执行最终构建的查询，获取所有符合条件的库存记录列表

    if request.method == 'POST':
        # 更新任务状态为执行中
        task.status = 'in_progress'
        task.start_time = datetime.now()
        task.operator_id = current_user.id

        # 处理盘点结果
        for inventory in inventories:
            actual_quantity = request.form.get(f'actual_quantity_{inventory.id}', type=int)
            if actual_quantity is not None:
                expected_quantity = inventory.quantity
                difference = actual_quantity - excepted_quantity

                # 创建盘点结果 
                result = InventoryCountResult(
                    task_id = task.id,
                    inventory_id = inventory.id,
                    expected_quantity = expected_quantity,
                    actual_quantity = actual_quantity,
                    difference = difference,
                    status = 'pending'
                )
                db.session.add(result)
        
        # 完成任务
        task.status = 'completed'
        task.end_time = datetime.now()

        db.session.commit()
        flash('盘点任务执行完成', 'success')
        return redirect(url_for('inventory_count.task_detail', task_id=task.id))

    return render_template('inventory_count/task_execute.html',
                           task=task,
                           inventories=inventories
    )        

# 盘点任务详情
@inventory_count_bp.route('/task/detail/<int:task_id>')
@permission_required('inventory_manage')
@login_required
def task_detail(task_id):
    task = InventoryCountTask.query.get_or_404(task_id)
    results = task.results.all()    
    # 特别标注：无法得知task是如何与results建立对应引用的

    # 计算准确率
    total_items = len(results)
    accurate_items = sum(1 for r in results if r.difference == 0) 
    accuracy_rate = (accurate_items / total_items * 100) if total_items > 0 else 100
    return render_template('inventory_count/task_detail.html',
                           task=task, 
                           results=results,
                           total_items=total_items,
                           accurate_items=accurate_items,
                           accuracy_rate=accuracy_rate
    )

# 处理盘点差异
# 对InventoryCountResult进行处理
@inventory_count_bp.route('/result/process/<int:result_id>', methods=['GET', 'POST'])
@permission_required('inventory_manage')
@login_required
def process_result(result_id):
    result = InventoryCountResult.query.get_or_404(result_id)
    inventory = result.inventory

    if request.method == 'POST':
        adjust = request.form.get('adjust') == '1'
        reason = request.form.get('reason')

        if adjust:
            # 创建库存调整
            adjustment_no = generate_inventory_adjustment_no()
            adjustment = InventoryAdjustment(
                adjustment_no = adjustment_no,
                inventory_id = inventory.id,
                before_quantity=inventory.quantity,
                after_quantity=result.actual_quantity,
                adjustment_quantiy=result.difference,
                type='count_adjustment',
                reason=reason or '盘点调整',
                operator_id=current_user.id,
                count_task_id=result.task_id
            )

            # 更新库存数量
            inventory.quantity = result.actual_quantity
            
            # 更新盘点结果状态
            result.status = 'processed'
            result.adjust_reason = reason
            result.processor_id = current_user.id
            result.process_time = datetime.now()

            db.session.add(adjustment)
            db.session.commit()
            flash('差异处理完成', 'success')
        else:
            # 标记已处理但不调整
            result.status = 'processed' + (reason or '差异在容差范围内')
            result.processor_id = current_user.id
            result.process_time = datetime.now()

            db.session.commit()
            flash('差异已标记为处理', 'success')

        return redirect(url_for('inventory_count.task_detail', task_id=result.task_id))

    return render_template('inventory_count/process_result.html',
                            result=result,
                            inventory=inventory
    )

# 库存调整历史
@inventory_count_bp.route('/adjustment/list')
@permission_required('inventory_manage')
@login_required
def adjustment_list():
    keyword = request.args.get('keyword', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    