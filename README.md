<div align="center">

# warehouse_management · Flask 仓库管理系统

**基于 Flask 框架的 B/S 架构仓库管理系统，采用 MVC 设计模式与 RBAC 权限体系，覆盖入库→库存管理→出库→盘点→调拨→报表分析全业务闭环**

[![License](https://img.shields.io/badge/license-LGPL--2.1-blue?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.6%2B-blue?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.3.3-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Database](https://img.shields.io/badge/database-MySQL-lightgrey?style=flat-square)](https://www.mysql.com/)
[![Frontend](https://img.shields.io/badge/frontend-Bootstrap%205%20%7C%20ECharts-lightgrey?style=flat-square)](.)

[快速开始](#快速开始) · [模块介绍](#模块介绍) · [核心特性](#核心特性) · [使用示例](#使用示例) · [API 参考](#api-参考) · [项目结构](#项目结构) · [数据初始化](#数据初始化) · [常见问题](#常见问题) · [参与贡献](#参与贡献)

</div>

---

warehouse_management 是一个面向企业仓库数字化管理的轻量级 Web 应用，全部基于 Python Flask 框架开发，无需复杂的前端构建工具。系统采用 MVC 设计模式和 Flask Blueprint 按功能模块组织，支持多配置环境，可快速部署到本地或服务器。

- **完整业务闭环**：覆盖商品信息管理、库位管理、库存监控、入库管理、出库管理、库存调拨、库存盘点、报表分析等完整仓库业务流程。
- **RBAC 权限控制**：用户-角色-权限三层关联，支持细粒度权限管理（用户管理、信息管理、入库/出库/库存管理、审核管理、报表查看等）。
- **应用工厂与蓝图组织**：Flask 应用工厂模式支持多配置环境；按功能模块划分 Blueprint，便于代码拆分与维护.
- **库存安全与并发控制**：出入库调拨使用行级锁防止并发冲突；出库支持按批次 FIFO 精确扣减；盘点期间自动冻结库存，确保数据准确.
- **零前端构建**：基于 Jinja2 模板 + Bootstrap 5 + ECharts 服务端渲染，无需 Node.js 或前端构建工具，克隆后配置数据库即可直接运行.
- **丰富的样例数据**：提供信息初始化、商品、出入库、调拨、盘点等多个 shell 脚本，快速生成体验数据.

> **项目状态**：核心仓库业务（入库/出库/库存/调拨/盘点/报表）、RBAC 权限、Flask Blueprint 视图、Jinja2 模板已实现，附带数据初始化脚本与样例数据，适合作为仓库管理系统学习参考或课程项目基础.

> **已知限制**：
> - 系统默认使用 MySQL 数据库，需提前安装并创建数据库；
> - 生产环境请修改 `SECRET_KEY` 与数据库密码，建议通过环境变量注入敏感信息；
> - 当前为教学演示级实现，生产环境使用前建议补充日志、监控、HTTPS、API 接口与单元测试.

**目录**：[快速开始](#快速开始) · [模块介绍](#模块介绍) · [核心特性](#核心特性) · [使用示例](#使用示例) · [API 参考](#api-参考) · [项目结构](#项目结构) · [数据初始化](#数据初始化) · [常见问题](#常见问题) · [参与贡献](#参与贡献) · [开源许可](#开源许可)

## 快速开始

### 环境要求

- Python 3.6+
- MySQL 数据库（需提前安装并启动）
- 仅需 Python 标准库 + `app/requirements.txt` 中的第三方依赖

### 运行方式

```bash
# 1. 克隆仓库
git clone <仓库地址>
cd warehouse_management

# 2. 创建并激活虚拟环境
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate

# 3. 安装依赖
pip install -r app/requirements.txt

# 4. 创建数据库
# 登录 MySQL 后执行：
# CREATE DATABASE warehouse_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

# 5. 修改数据库连接配置（app/config.py）
# SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://用户名:密码@localhost/warehouse_db'

# 6. 数据库迁移初始化
# Windows
set FLASK_APP=app/run.py
flask db init
flask db migrate -m "Initial migration"
flask db upgrade

# Linux/Mac
export FLASK_APP=app/run.py
flask db init
flask db migrate -m "Initial migration"
flask db upgrade

# 7. 启动应用
python app/run.py
# 或
flask run --host=0.0.0.0 --port=5000 --debug
```

启动后访问 `http://localhost:5000`，默认进入登录页面。管理员账号为 `admin` / `123456`（需先运行数据初始化脚本）。

## 模块介绍

| 目录/文件 | 语言/风格 | 核心特点 | 适用场景 |
|-----------|-----------|----------|----------|
| `app/models/` | Python，SQLAlchemy ORM | 用户/角色/权限、商品/分类/参数、供应商/客户、库位/库存、入库/出库、调拨、盘点等全部数据模型 | 数据层，定义数据库表结构与关联 |
| `app/views/` | Python，Flask Blueprint | 按功能划分蓝图：auth、user、product、inbound、outbound、inventory、transfer、check、report、category、location、customer、supplier | 控制层，处理 HTTP 请求与业务逻辑 |
| `app/templates/` | HTML + Jinja2 + Bootstrap 5 | 基础模板 base.html 及 auth/category/check/inbound/inventory/location/outbound/product/report/supplier/transfer/user 等子模板 | 视图层，服务端渲染的前端页面 |
| `app/utils/` | Python 工具函数 | `auth.py` 权限装饰器、`helpers.py` 单号生成/库存更新/调拨执行 | 通用工具与权限控制 |
| `app/shells/` | Python 脚本 | `information_shell.py` 基础信息初始化、`product_shell.py` 商品样例、`inventory_shell.py` 出入库样例、`transfer_shell.py` 调拨样例、`check_shell.py` 盘点样例 | 命令行数据初始化与样例数据 |
| `app/run.py` | Python 应用入口 | 工厂函数 `create_app()`，shell 上下文处理器，直接运行启动 Flask 开发服务器 | 项目启动入口 |
| `app/config.py` | Python 配置 | 开发/生产环境配置、数据库 URI、分页、库存预警阈值、会话安全 | 配置管理 |
| `app/requirements.txt` | 依赖清单 | Flask、Flask-SQLAlchemy、Flask-Login、Flask-Migrate、Flask-WTF、PyMySQL 等 | 项目依赖 |

## 核心特性

### 1. 完整的仓库业务闭环

系统覆盖从商品信息管理到库存监控、出入库业务处理、盘点调拨、数据分析报表的完整闭环：

- **商品与分类管理**：支持商品编码、名称、单位、分类、预警阈值、动态参数模板（如屏幕尺寸、品牌、显卡型号等）
- **供应商与客户管理**：维护往来单位信息，用于入库/出库单关联
- **库位管理**：库位编码（如 A-01-01）、区域划分、最大容量、启用/禁用状态，一个库位只能存放一种商品
- **库存管理**：实时库存监控、库存预警、库存状态管理（正常/损坏/冻结）、批次号与生产/过期日期管理
- **入库管理**：支持补货、退货、采购三种入库类型，入库审核流程，审核后自动更新库存
- **出库管理**：支持发货、退购、报废三种出库类型，出库审核流程，支持按批次 FIFO 精确扣减库存
- **库存调拨**：库位间商品调拨，先进先出 (FIFO) 原则，审核流程，执行后自动转移库存
- **库存盘点**：盘点单创建、盘点冻结机制、盘盈盘亏处理、库存自动调整、已完成/待录入/已取消状态
- **报表分析**：出入库趋势分析（近30天）、库存健康度评估、综合数据可视化（ECharts）

### 2. RBAC 权限模型

基于用户-角色-权限三层关联，实现细粒度权限控制：

- 6 大核心权限：`user_manage`（用户管理）、`information_manage`（基础信息管理）、`inbound_manage`（入库管理）、`outbound_manage`（出库管理）、`inventory_manage`（库存管理）、`report_view`（报表查看），以及 `audit_manage`（审核管理）
- 预置角色：管理员、仓库管理员、普通用户、出入库操作员
- 预置账号：`admin`（管理员，密码 123456）、`tandingqi`（仓库管理员）、`wuwangxi`（出入库操作员）、`wuwangwang`（普通用户）
- 权限通过 `@permission_required('xxx')` 装饰器保护视图函数

### 3. 应用工厂与蓝图组织

- 采用 Flask 应用工厂模式 `create_app()`，支持 `default` / `development` / `production` 多配置环境
- 按功能模块划分 Flask Blueprint，便于代码拆分与维护
- 使用 Flask-SQLAlchemy 作为 ORM，Flask-Migrate 管理数据库迁移，Flask-Login 处理用户认证

### 4. 库存安全与并发控制

- 出入库调拨均使用行级锁（`with_for_update()`）防止并发冲突
- 出库支持按批次号 FIFO 自动扣减，优先消耗生产日期早的批次
- 盘点期间自动冻结库存，确保盘点数据准确；取消盘点自动解冻
- 库位容量校验：入库/调拨时检查是否超过库位最大可存放数量

### 5. 零前端构建，直接运行

全部前端基于 Jinja2 模板 + Bootstrap 5 + ECharts 服务端渲染，无需 Node.js 或前端构建工具，克隆后配置数据库即可直接运行。

## 使用示例

### 启动应用并登录

```bash
# 进入项目目录
cd warehouse_management

# 激活虚拟环境（Windows）
venv\Scripts\activate

# 启动 Flask 开发服务器
python app/run.py
```

浏览器访问 `http://localhost:5000`，使用管理员账号 `admin` / `123456` 登录（需先完成数据初始化）。

### 创建入库单（通过 Web 界面）

1. 登录后进入「入库管理」→「入库单列表」
2. 点击「添加入库单」，选择入库类型（补货/退货/采购）、供应商、入库日期
3. 添加入库明细：选择商品、库位、填数量、批次号、生产日期、过期日期
4. 提交后入库单状态为「草稿」，进入「审核列表」审核通过后，库存自动更新

### 创建出库单（FIFO 批次扣减）

1. 进入「出库管理」→「出库单列表」，点击「添加出库单」
2. 选择出库类型（发货/退购/报废）、客户、联系电话
3. 添加出库明细：系统自动按生产日期 FIFO 从库位中扣减库存
4. 审核通过后，库存数量相应减少

### 库存调拨

1. 进入「库存调拨」→「调拨单列表」，点击「添加调拨单」
2. 选择商品、源库位、目标库位、数量
3. 提交后状态为「待审核」，审核通过后执行 `execute_transfer`，库存从源库位转移到目标库位

### 库存盘点

1. 进入「库存盘点」→「盘点单列表」，点击「添加盘点单」
2. 选择自动（按商品/分类/库位筛选）或手动添加盘点明细
3. 创建后库存自动冻结，进入「待录入」状态
4. 在「盘点结果录入」页面填入实际数量，系统自动计算盘盈/盘亏并更新库存

### 报表分析

- 综合仪表盘：近30天出入库趋势、库存健康度评分、库存状态分布（正常/损坏/冻结）
- 入库报表 / 出库报表：按商品汇总入库/出库总量与当前库存

### 数据初始化脚本（命令行）

```bash
# 按顺序运行，生成基础信息与样例数据
python -m app.shells.information_shell   # 分类、参数、供应商、客户、库位、角色权限、管理员账号
python -m app.shells.product_shell        # 商品样例（华硕天选6、机械革命极光X、小米 REDMI K90、vivo iQOO 15）
python -m app.shells.inventory_shell      # 入库单与出库单样例
python -m app.shells.transfer_shell       # 调拨单样例
python -m app.shells.check_shell          # 盘点单样例（已完成/待录入/已取消）
```

## API 参考

### 权限装饰器（app/utils/auth.py）

| 接口 | 说明 |
|------|------|
| `@permission_required(permission_name)` | 权限检查装饰器，未登录重定向登录页，无权限返回 403 |
| `@admin_required` | 管理员权限装饰器（等价于 `permission_required('user_manage')`） |

### 辅助函数（app/utils/helpers.py）

| 接口 | 说明 |
|------|------|
| `generate_inbound_no()` | 生成入库单号（IN + 日期 + 3位随机数） |
| `generate_outbound_no()` | 生成出库单号（OUT + 日期 + 3位随机数） |
| `generate_transfer_no()` | 生成调拨单号（TF + 日期 + 3位随机数） |
| `generate_check_no()` | 生成盘点单号（CK + 日期 + 3位随机数） |
| `update_inventory(product_id, location_id, batch_no, quantity, is_bound=True)` | 库存更新：入库增加 / 出库减少，包含库位冲突与库存不足校验 |
| `execute_transfer(product_id, source_location_id, target_location_id, quantity)` | 执行调拨：FIFO 扣减源库位库存，增加目标库位库存 |

### 数据模型（app/models/）

| 模型 | 说明 |
|------|------|
| `User / Role / Permission` | 用户、角色、权限，RBAC 多对多关联 |
| `Product / Category / Supplier / Customer` | 商品、分类、供应商、客户 |
| `ProductParamKey / CategoryParam / ProductParamValue` | 商品动态参数模板与值 |
| `WarehouseLocation / Inventory` | 库位、库存（含批次、生产/过期日期、状态 normal/damaged/frozen） |
| `InboundOrder / InboundItem` | 入库单与明细（类型：replenish/return/purchase） |
| `OutboundOrder / OutboundItem` | 出库单与明细（类型：delivery/return/scrap） |
| `TransferOrder / TransferItem` | 调拨单与明细（状态：pending/approved/rejected） |
| `CheckInventory / CheckInventoryItem / CheckInventoryResult` | 盘点单、明细、结果（状态：pending/completed/canceled） |

### 主要视图蓝图（app/views/）

| 蓝图 | URL 前缀 | 说明 |
|------|---------|------|
| `auth` | `/auth` | 登录、登出、注册 |
| `user` | `/user` | 用户/角色/权限管理 |
| `product` | `/product` | 商品管理（含分类参数） |
| `category` | `/category` | 分类管理 |
| `inbound` | `/inbound` | 入库管理（列表/添加/审核/明细） |
| `outbound` | `/outbound` | 出库管理（列表/添加/审核/明细） |
| `inventory` | `/inventory` | 库存管理（详情/预警/状态管理） |
| `location` | `/location` | 库位管理 |
| `transfer` | `/transfer` | 调拨管理（列表/添加/审核/明细） |
| `check` | `/check` | 盘点管理（列表/添加/录入/取消/历史） |
| `report` | `/report` | 报表分析（仪表盘/入库报表/出库报表/库存商品） |
| `customer` | `/customer` | 客户管理 |
| `supplier` | `/supplier` | 供应商管理 |

## 项目结构

```
warehouse_management/
├── README.md                 # 项目说明（本文件）
├── LICENSE                   # LGPL-2.1 许可证
├── .gitignore                # 忽略 __pycache__、migrations、.idea
├── app/                      # Flask 应用主目录
│   ├── __init__.py           # 应用工厂 create_app()，注册蓝图与扩展
│   ├── run.py                # 应用入口，shell 上下文处理器
│   ├── config.py             # 配置文件（默认/开发/生产环境）
│   ├── requirements.txt      # Python 依赖清单
│   │
│   ├── models/               # 数据模型层（SQLAlchemy ORM）
│   │   ├── __init__.py       # 导出全部模型类
│   │   ├── user.py           # User / Role / Permission（RBAC）
│   │   ├── product.py        # Product / Category / Supplier / Customer / 参数模型
│   │   ├── inventory.py      # WarehouseLocation / Inventory
│   │   ├── inbound.py        # InboundOrder / InboundItem
│   │   ├── outbound.py       # OutboundOrder / OutboundItem
│   │   ├── transfer.py       # TransferOrder / TransferItem
│   │   └── check.py          # CheckInventory / CheckInventoryItem / CheckInventoryResult
│   │
│   ├── views/                # 控制层（Flask Blueprint 视图函数）
│   │   ├── __init__.py
│   │   ├── auth.py           # 登录/登出/注册
│   │   ├── user_manage.py    # 用户/角色/权限管理
│   │   ├── product_manage.py # 商品管理
│   │   ├── category_manage.py# 分类管理
│   │   ├── inbound_manage.py # 入库管理
│   │   ├── outbound_manage.py# 出库管理
│   │   ├── inventory_manage.py# 库存管理
│   │   ├── location_manage.py# 库位管理
│   │   ├── transfer_manage.py# 调拨管理
│   │   ├── check_manage.py   # 盘点管理
│   │   ├── report.py         # 报表分析
│   │   ├── customer_manage.py# 客户管理
│   │   └── supplier_manage.py# 供应商管理
│   │
│   ├── utils/                # 工具函数
│   │   ├── __init__.py
│   │   ├── auth.py           # 权限装饰器
│   │   └── helpers.py        # 单号生成、库存更新、调拨执行
│   │
│   ├── shells/               # 命令行数据初始化脚本
│   │   ├── information_shell.py  # 基础信息初始化（分类/参数/供应商/客户/库位/角色/管理员）
│   │   ├── product_shell.py      # 商品样例
│   │   ├── inventory_shell.py    # 出入库样例
│   │   ├── transfer_shell.py     # 调拨样例
│   │   └── check_shell.py        # 盘点样例
│   │
│   └── templates/            # Jinja2 模板（Bootstrap 5）
│       ├── base.html
│       ├── auth/             # 登录/注册
│       ├── user/             # 用户/角色/权限
│       ├── product/          # 商品
│       ├── category/         # 分类
│       ├── inbound/          # 入库
│       ├── outbound/         # 出库
│       ├── inventory/        # 库存
│       ├── location/         # 库位
│       ├── transfer/         # 调拨
│       ├── check/            # 盘点
│       ├── report/           # 报表
│       ├── customer/         # 客户
│       └── supplier/         # 供应商
```

## 数据初始化

系统首次使用需要按顺序运行初始化脚本，生成基础信息与样例数据：

```bash
# 确保已完成数据库迁移（flask db upgrade）

# 1. 基础信息：分类、参数、供应商、客户、库位、角色权限、管理员账号
python -m app.shells.information_shell

# 2. 商品样例
python -m app.shells.product_shell

# 3. 入库与出库单样例
python -m app.shells.inventory_shell

# 4. 调拨单样例
python -m app.shells.transfer_shell

# 5. 盘点单样例（已完成/待录入/已取消）
python -m app.shells.check_shell
```

初始化完成后，可使用以下账号登录：

| 账号 | 密码 | 角色 | 权限 |
|------|------|------|------|
| admin | 123456 | 管理员 | 全部权限 |
| tandingqi | 123456 | 仓库管理员 | 信息/库存/入库/出库/报表/审核 |
| wuwangxi | 123456 | 出入库操作员 | 信息/报表/入库/出库 |
| wuwangwang | 123456 | 普通用户 | 信息/报表 |

## 常见问题

**Q：启动时报错“找不到配置”或数据库连接失败？**  
A：请先确认 MySQL 服务已启动，并已创建 `warehouse_db` 数据库；检查 `app/config.py` 中的 `SQLALCHEMY_DATABASE_URI` 用户名与密码是否正确。

**Q：如何进行数据库迁移？**  
A：设置 `FLASK_APP=app/run.py` 后，依次执行 `flask db init`、`flask db migrate -m "message"`、`flask db upgrade`。若已有 migrations 目录，可直接 `flask db upgrade`。

**Q：一条库位只能存放一种商品，如何调整？**  
A：这是系统设计的业务规则，由 `Inventory.check_location_product_conflict()` 与 `execute_transfer()` 共同保证。如需允许混储，需修改相关校验逻辑并更新数据模型唯一约束。

**Q：出库时如何选择批次？**  
A：支持手动指定批次号，也可留空由系统按生产日期 FIFO 自动选取并扣减库存。

**Q：盘点期间库存会怎样？**  
A：盘点单创建后，相关库存自动冻结（状态变为 `frozen`）；录入盘点结果并完成后自动解冻并调整为实际数量；取消盘点也会自动解冻。

**Q：前端使用了什么框架？需要编译吗？**  
A：前端基于 Jinja2 模板 + Bootstrap 5 + ECharts，全部在服务端渲染，无需 Node.js 或前端构建工具，直接运行即可。

## 参与贡献

欢迎通过 Issues 报告问题或提交 Pull Request 贡献代码。在提交 PR 前，请确保：

1. 新增功能附带对应的测试或初始化脚本；
2. 现有数据初始化脚本仍能正常运行；
3. 代码风格与现有文件保持一致（缩进、命名、注释约定）；
4. 生产环境敏感信息（如 `SECRET_KEY`、数据库密码）通过环境变量注入，不要硬编码提交。

## 开源许可

本项目采用 [GNU Lesser General Public License v2.1](LICENSE) 开源。
