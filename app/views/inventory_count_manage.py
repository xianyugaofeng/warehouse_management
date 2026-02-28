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
        query = query.filter(InventoryCountTask.task_no.ilike(f'%{keyword}%') | InventoryCountTask.name.ilike(f'%{keyword}%'))
    
    if status:
        query = query.filter_by(status=status)
    
