from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta
import logging
from app import db
from app.models.inventory_count import InventoryCountTask, InventoryCountTaskSchedule, InventoryCountTaskLog
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.inventory import WarehouseLocation
from app.utils.helpers import generate_inventory_adjustment_no, validate_virtual_inventory
from flask_login import current_user
# 配置日志
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('inventory_count_scheduler')

# 创建调度器
scheduler = BackgroundScheduler()


def run_inventory_count_task(task_id, schedule_id=None):
    """执行盘点任务"""
    logger.info(f'开始执行盘点任务 {task_id}')
    
    # 创建执行日志
    log = InventoryCountTaskLog(
        task_id=task_id,
        schedule_id=schedule_id,
        start_time=datetime.now(),
        status='running',
        execution_type='automatic'
    )
    db.session.add(log)
    db.session.commit()
    
    try:
        # 获取任务
        task = InventoryCountTask.query.get(task_id)
        if not task:
            raise ValueError(f'任务 {task_id} 不存在')
        
        # 检查任务状态
        if task.status == 'in_progress':
            raise ValueError(f'任务 {task_id} 正在执行中')
        
        # 根据任务类型获取需要盘点的库存
        query = Inventory.query
        if task.area:
            query = query.join(WarehouseLocation).filter(WarehouseLocation.area == task.area)
        if task.supplier_id:
            query = query.join(Product).filter(Product.supplier_id == task.supplier_id)
        
        inventories = query.all()
        
        # 更新任务状态为执行中
        task.status = 'in_progress'
        task.start_time = datetime.now()
        
        # 处理盘点结果
        for inventory in inventories:
            # 从虚拟库存获取预期数量
            from app.models.inventory_count import VirtualInventory
            virtual_inventory = VirtualInventory.query.filter_by(
                product_id=inventory.product_id,
                location_id=inventory.location_id,
                batch_no=inventory.batch_no
            ).first()
            expected_quantity = virtual_inventory.virtual_quantity if virtual_inventory else inventory.quantity
            
            # 实际盘点数量（当前库存）
            actual_quantity = inventory.quantity
            
            # 计算差异
            difference = actual_quantity - expected_quantity
            
            # 创建盘点结果
            from app.models.inventory_count import InventoryCountResult
            result = InventoryCountResult(
                task_id=task.id,
                inventory_id=inventory.id,
                expected_quantity=expected_quantity,
                actual_quantity=actual_quantity,
                difference=difference,
                status='auto_adjusted'
            )
            db.session.add(result)
            
            # 自动处理差异
            if difference != 0:
                # 创建库存调整
                adjustment_no = generate_inventory_adjustment_no()
                from app.models.inventory_count import InventoryAdjustment
                adjustment = InventoryAdjustment(
                    adjustment_no=adjustment_no,
                    inventory_id=inventory.id,
                    before_quantity=inventory.quantity,
                    after_quantity=expected_quantity,
                    adjustment_quantity=expected_quantity - inventory.quantity,
                    type='count_adjustment',
                    reason=f'自动周期盘点调整',
                    operator_id=current_user.id,  # 系统用户
                    count_task_id=task.id
                )
                db.session.add(adjustment)
                
                # 更新实物库存为期望库存数量
                inventory.quantity = expected_quantity
                
                # 同步更新虚拟库存的实物库存部分，使其等于库存数量
                if virtual_inventory:
                    virtual_inventory.physical_quantity = expected_quantity
                    virtual_inventory.in_transit_quantity = 0
                    virtual_inventory.allocated_quantity = 0
                    # 验证虚拟库存
                    is_valid, message = validate_virtual_inventory(virtual_inventory)
                    if not is_valid:
                        logger.warning(f'虚拟库存验证失败: {message}')
                
                # 更新盘点结果状态
                result.adjust_reason = '自动周期盘点调整'
                result.processor_id = current_user.id  # 系统用户
                result.process_time = datetime.now()
        
        # 完成任务
        task.status = 'completed'
        task.end_time = datetime.now()
        
        # 更新调度信息
        if schedule_id:
            schedule = InventoryCountTaskSchedule.query.get(schedule_id)
            if schedule:
                schedule.last_execution_time = datetime.now()
                schedule.next_execution_time = datetime.now() + timedelta(hours=schedule.interval_hours)
                schedule.execution_count += 1
                
                # 检查是否达到最大执行次数
                if schedule.max_executions > 0 and schedule.execution_count >= schedule.max_executions:
                    schedule.status = 'stopped'
                    # 移除调度任务
                    job_id = f'inventory_count_task_{task_id}_{schedule_id}'
                    if scheduler.get_job(job_id):
                        scheduler.remove_job(job_id)
        
        # 更新日志
        log.end_time = datetime.now()
        log.status = 'success'
        
        db.session.commit()
        logger.info(f'盘点任务 {task_id} 执行成功')
        
    except Exception as e:
        logger.error(f'盘点任务 {task_id} 执行失败: {str(e)}')
        # 更新日志
        log.end_time = datetime.now()
        log.status = 'failed'
        log.error_message = str(e)
        
        # 回滚事务
        db.session.rollback()
        db.session.add(log)
        db.session.commit()


def start_scheduler():
    """启动调度器"""
    logger.info('启动盘点任务调度器')
    
    # 从数据库加载调度任务
    schedules = InventoryCountTaskSchedule.query.filter_by(status='active').all()
    for schedule in schedules:
        # 计算下次执行时间
        if not schedule.next_execution_time or schedule.next_execution_time < datetime.now():
            schedule.next_execution_time = datetime.now() + timedelta(hours=schedule.interval_hours)
        
        # 添加调度任务
        job_id = f'inventory_count_task_{schedule.task_id}_{schedule.id}'
        if not scheduler.get_job(job_id):
            scheduler.add_job(
                run_inventory_count_task,
                trigger=IntervalTrigger(hours=schedule.interval_hours),
                args=[schedule.task_id, schedule.id],
                id=job_id,
                name=f'盘点任务 {schedule.task_id} 调度',
                replace_existing=True
            )
            logger.info(f'添加调度任务: {job_id}')
    
    # 启动调度器
    if not scheduler.running:
        scheduler.start()
        logger.info('调度器启动成功')


def stop_scheduler():
    """停止调度器"""
    logger.info('停止盘点任务调度器')
    if scheduler.running:
        scheduler.shutdown()
        logger.info('调度器停止成功')


def add_schedule(task_id, interval_hours=24, max_executions=0):
    """添加调度任务"""
    # 创建调度记录
    schedule = InventoryCountTaskSchedule(
        task_id=task_id,
        interval_hours=interval_hours,
        max_executions=max_executions,
        next_execution_time=datetime.now() + timedelta(hours=interval_hours)
    )
    db.session.add(schedule)
    db.session.commit()
    
    # 添加到调度器
    job_id = f'inventory_count_task_{task_id}_{schedule.id}'
    scheduler.add_job(
        run_inventory_count_task,
        trigger=IntervalTrigger(hours=interval_hours),
        args=[task_id, schedule.id],
        id=job_id,
        name=f'盘点任务 {task_id} 调度',
        replace_existing=True
    )
    
    logger.info(f'添加调度任务: {job_id}')
    return schedule


def remove_schedule(schedule_id):
    """移除调度任务"""
    schedule = InventoryCountTaskSchedule.query.get(schedule_id)
    if schedule:
        # 从调度器中移除
        job_id = f'inventory_count_task_{schedule.task_id}_{schedule.id}'
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
            logger.info(f'移除调度任务: {job_id}')
        
        # 更新状态
        schedule.status = 'stopped'
        db.session.commit()
        return True
    return False


def pause_schedule(schedule_id):
    """暂停调度任务"""
    schedule = InventoryCountTaskSchedule.query.get(schedule_id)
    if schedule:
        # 从调度器中移除
        job_id = f'inventory_count_task_{schedule.task_id}_{schedule.id}'
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
            logger.info(f'暂停调度任务: {job_id}')
        
        # 更新状态
        schedule.status = 'paused'
        db.session.commit()
        return True
    return False


def resume_schedule(schedule_id):
    """恢复调度任务"""
    schedule = InventoryCountTaskSchedule.query.get(schedule_id)
    if schedule:
        # 计算下次执行时间
        if not schedule.next_execution_time or schedule.next_execution_time < datetime.now():
            schedule.next_execution_time = datetime.now() + timedelta(hours=schedule.interval_hours)
        
        # 添加到调度器
        job_id = f'inventory_count_task_{schedule.task_id}_{schedule.id}'
        scheduler.add_job(
            run_inventory_count_task,
            trigger=IntervalTrigger(hours=schedule.interval_hours),
            args=[schedule.task_id, schedule.id],
            id=job_id,
            name=f'盘点任务 {schedule.task_id} 调度',
            replace_existing=True
        )
        
        # 更新状态
        schedule.status = 'active'
        db.session.commit()
        logger.info(f'恢复调度任务: {job_id}')
        return True
    return False