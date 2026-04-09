# 基于Flask的仓库管理系统 

## 项目介绍

本仓库管理系统是基于Flask框架开发的Web应用，旨在为企业提供高效、便捷的仓库管理解决方案。系统支持产品管理、库存管理、入库管理、出库管理、报表分析等核心功能，帮助企业实现仓库运营的数字化管理。

### 主要功能
- **用户管理**：基于角色的权限控制，支持用户登录、注册和权限管理
- **产品管理**：产品信息的增删改查，支持分类管理和参数配置
- **库存管理**：实时库存监控，库存预警，库位管理
- **入库管理**：入库单创建、明细管理，自动更新库存
- **出库管理**：出库单创建、明细管理，自动更新库存
- **报表分析**：库存健康报表、库存趋势分析、热销产品分析
- **客户与供应商管理**：客户和供应商信息的管理

## 软件架构

### 技术栈
- **后端**：Python 3.6+, Flask, SQLAlchemy, Flask-Login, Flask-Migrate
- **前端**：HTML, CSS, JavaScript, Bootstrap
- **数据库**：SQLite (默认)，支持MySQL/PostgreSQL

### 架构设计
- **MVC模式**：
  - Model：数据模型层，定义数据库表结构
  - View：视图层，处理HTTP请求和响应
  - Controller：控制器层，业务逻辑处理
- **Blueprint组织**：按功能模块划分蓝图，如产品管理、库存管理等
- **模块化设计**：代码结构清晰，便于维护和扩展

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

### 5. 数据库初始化
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

### 6. 启动应用
```bash
# 开发模式
flask run --host=0.0.0.0 --port=5000 --debug

# 或直接运行
python app/run.py
```

## 使用说明

### 1. 登录系统
访问 `http://localhost:5000`，使用管理员账号登录（默认账号密码可在系统初始化时设置）。

### 2. 系统功能使用
- **产品管理**：在左侧菜单点击"产品管理"，可进行产品的增删改查操作。
- **库存管理**：在左侧菜单点击"库存管理"，查看库存状态和库存预警。
- **入库管理**：在左侧菜单点击"入库管理"，创建入库单并添加入库明细。
- **出库管理**：在左侧菜单点击"出库管理"，创建出库单并添加出库明细。
- **报表分析**：在左侧菜单点击"报表"，查看各类库存报表。
- **客户与供应商管理**：在左侧菜单点击"客户管理"或"供应商管理"，管理相关信息。

### 3. 权限管理
系统支持基于角色的权限控制，管理员可在"用户管理"中设置用户角色和权限。

## 参与贡献

1.  Fork 本仓库
2.  新建 Feat_xxx 分支
3.  提交代码
4.  新建 Pull Request

## 注意事项

- 本系统默认使用SQLite数据库，生产环境建议使用MySQL或PostgreSQL。
- 系统运行需要Python 3.6或以上版本。
- 首次运行时需要初始化数据库和创建管理员账号。
- 系统支持通过环境变量配置数据库连接信息和其他参数。

## 许可证

本项目采用MIT许可证，详见LICENSE文件。
