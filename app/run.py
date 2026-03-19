import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User, Role, Permission
from app.models import Product, Category, Supplier
from app.models import Inventory, WarehouseLocation
from app.models import InboundItem, InboundOrder
from app.models import OutboundItem, OutboundOrder
from app.models import PurchaseOrder
from app.models import InspectionOrder, InspectionItem
from app.models import ReturnOrder, ReturnItem
from app.models import InventoryCount, InventoryCountDetail, VarianceDocument, VarianceDetail, InventoryFreezeRecord


app = create_app()

# 命令行处理器（用于数据库初始化）
@app.shell_context_processor    # 它将其下方的函数 make_shell_context 注册为 Flask 的 Shell 上下文处理器
def make_shell_context():   # 在命令行使用flask shell命令启动Flask交互式环境时
                            # 这个处理器会自动运行，并将其返回的变量（字典）注入到Shell的全局命名空间中
                            # 函数返回一个Python字典dict()构造函数内的关键字参数会被创建为键值对
    return dict(
        db=db, User=User, Role=Role, Permission=Permission,
        Product=Product, Category=Category, Supplier=Supplier,
        Inventory=Inventory, WarehouseLocation=WarehouseLocation,
        InboundItem=InboundItem, InboundOrder=InboundOrder,
        OutboundItem=OutboundItem, OutboundOrder=OutboundOrder,
        PurchaseOrder=PurchaseOrder,
        InspectionOrder=InspectionOrder, InspectionItem=InspectionItem,
        ReturnOrder=ReturnOrder, ReturnItem=ReturnItem,
        InventoryCount=InventoryCount, InventoryCountDetail=InventoryCountDetail,
        VarianceDocument=VarianceDocument, VarianceDetail=VarianceDetail,
        InventoryFreezeRecord=InventoryFreezeRecord
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)