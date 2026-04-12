# 基于Flask的仓库管理系统

## 项目介绍

本仓库管理系统是基于Flask框架开发的B/S架构Web应用，旨在为企业提供高效、便捷的仓库数字化管理解决方案。系统采用MVC设计模式，实现了从商品信息管理到库存监控、出入库业务处理、盘点调拨、数据分析报表等完整的仓库业务闭环。

### 主要功能
- **用户权限管理**：基于RBAC模型的权限控制，支持用户、角色、权限的多对多关联管理
- **基础信息管理**：商品信息管理、分类管理、动态参数配置、供应商与客户管理
- **库位管理**：库位编码、区域划分、启用/禁用状态控制
- **库存管理**：实时库存监控、库存预警、库存状态管理（正常/损坏/冻结）
- **入库管理**：支持补货、退货、采购三种入库类型，入库审核流程，自动更新库存
- **出库管理**：支持发货、退购、报废三种出库类型，出库审核流程，库存校验
- **库存调拨**：库位间商品调拨，先进先出(FIFO)原则，审核流程
- **库存盘点**：盘点单创建、盘点冻结机制、盘盈盘亏处理、库存自动调整
- **报表分析**：出入库趋势分析、库存健康度评估、综合数据可视化展示

## 软件架构

### 技术栈
- **后端框架**：Flask 2.3.3
- **ORM框架**：Flask-SQLAlchemy 3.1.1
- **用户认证**：Flask-Login 0.6.3
- **数据库迁移**：Flask-Migrate 4.0.5
- **表单处理**：Flask-WTF 1.2.1
- **数据库**：MySQL (通过 PyMySQL 1.1.0 连接)
- **前端框架**：Bootstrap 5.3.0
- **图表可视化**：ECharts 5.4.3
- **图标库**：Font Awesome 4.7.0

### 架构设计
- **MVC模式**：
  - Model：数据模型层，定义数据库表结构与关联关系
  - View：视图层，处理HTTP请求和响应
  - Controller：业务逻辑层，封装核心业务处理
- **Blueprint组织**：按功能模块划分蓝图（auth、user、product、inbound、outbound、inventory、transfer、check、report等）
- **应用工厂模式**：支持多配置环境，延迟初始化扩展
- **RBAC权限模型**：用户-角色-权限三层关联，实现细粒度权限控制

## 目录结构
```
warehouse_management/
├── app/
│   ├── models/         # 数据模型
│   ├── shells/         # 命令行工具
│   ├── templates/      # 模板文件
│   ├── utils/          # 工具函数
│   ├── views/          # 视图函数
│   ├── __init__.py     # 应用初始化
│   ├── config.py       # 配置文件
│   ├── requirements.txt # 依赖文件
│   └── run.py          # 应用入口
├── .gitignore
└── README.md
```

## 安装教程

### 1. 环境准备
确保系统已安装Python 3.6或以上版本。

### 2. 克隆仓库
```bash
git clone <仓库地址>
cd warehouse_management
```

### 3. 创建虚拟环境
```bash
# Windows
python -m venv venv
# 激活虚拟环境
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 4. 安装依赖
```bash
pip install -r app/requirements.txt
```

### 5. 数据库配置
系统默认使用MySQL数据库，请确保已安装并启动MySQL服务。

创建数据库：
```sql
CREATE DATABASE warehouse_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

修改数据库连接配置（app/config.py）：
```python
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://用户名:密码@localhost/warehouse_db'
```

### 6. 数据库初始化
```bash
# 设置环境变量
# Windows
set FLASK_APP=app/run.py
# Linux/Mac
export FLASK_APP=app/run.py

# 初始化数据库迁移
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

### 7. 启动应用
```bash
# 开发模式
flask run --host=0.0.0.0 --port=5000 --debug

# 或直接运行
python app/run.py
```

## 使用说明

### 1. 登录系统
访问 `http://localhost:5000`，使用管理员账号登录。

首次使用需要通过注册页面创建账号，然后由管理员分配角色和权限。

### 2. 系统功能使用
- **产品管理**：左侧菜单「信息管理」→「产品管理」，进行产品的增删改查、分类管理、参数配置
- **库存管理**：左侧菜单「库存管理」，查看库存详情、库存预警、库存状态管理
- **入库管理**：左侧菜单「入库管理」，创建入库单→添加明细→提交审核
- **出库管理**：左侧菜单「出库管理」，创建出库单→添加明细→提交审核
- **库存调拨**：左侧菜单「库存调拨」，创建调拨单→审核通过→执行调拨
- **库存盘点**：左侧菜单「库存盘点」，创建盘点单→冻结库存→录入实盘→完成盘点
- **报表分析**：左侧菜单「报表中心」，查看综合仪表盘、入库报表、出库报表
- **客户与供应商**：左侧菜单「客户管理」「供应商管理」，维护往来单位信息

### 3. 权限管理
系统采用RBAC权限模型，包含6大核心权限：
- `user_manage`：用户管理权限
- `information_manage`：基础信息管理权限
- `inbound_manage`：入库管理权限
- `outbound_manage`：出库管理权限
- `inventory_manage`：库存管理权限
- `report_view`：报表查看权限

管理员可在「用户管理」中创建用户、分配角色、配置权限。

## 参与贡献

1.  Fork 本仓库
2.  新建 Feat_xxx 分支
3.  提交代码
4.  新建 Pull Request

## 系统特色

- **完整的业务闭环**：覆盖入库→库存管理→出库→盘点→调拨→报表分析全流程
- **灵活的权限体系**：基于RBAC模型，支持细粒度权限控制
- **动态商品参数**：分类关联参数模板，商品继承参数并填写具体值
- **批次管理**：支持批次号、生产日期、过期日期，出库按批次精确扣减
- **库位管理创新**：一个库位只能存放一种商品，防止混淆
- **盘点冻结机制**：盘点期间自动冻结库存，确保数据准确
- **库存健康度分析**：创新性引入健康度评分，可视化展示库存状态
- **现代化UI设计**：赛博朋克科技风格，霓虹发光效果

## 注意事项

- 本系统使用MySQL数据库，需提前安装并创建数据库
- 系统运行需要Python 3.6或以上版本
- 首次运行时需要初始化数据库迁移
- 生产环境请修改SECRET_KEY和数据库密码
- 建议配置HTTPS以增强安全性

## 许可证

本项目采用MIT许可证，详见LICENSE文件。
