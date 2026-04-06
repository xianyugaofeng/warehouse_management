# 入库相关视图模块
from app.views.inbound_views.inbound_manage import inbound_bp
from app.views.inbound_views.inspection_manage import inspection_bp
from app.views.inbound_views.purchase_manage import purchase_bp
from app.views.inbound_views.putaway_manage import putaway_bp
from app.views.inbound_views.return_manage import return_bp

__all__ = ['inbound_bp', 'inspection_bp', 'purchase_bp', 'putaway_bp', 'return_bp']