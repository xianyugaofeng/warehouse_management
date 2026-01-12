from app import create_app, db
from app.models import User, Role, Permission
from app.models import Product, Category, Supplier
from app.models import Inventory, WarehouseLocation
from app.models import InboundOrder, OutboundOrder

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
        InboundOrder=InboundOrder, OutboundOrder=OutboundOrder
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)