# 库存相关视图模块
from app.views.inventory_views.inventory_manage import inventory_bp
from app.views.inventory_views.stock_move_manage import stock_move_bp
from app.views.inventory_views.count_manage import count_bp

__all__ = ['inventory_bp', 'stock_move_bp', 'count_bp']