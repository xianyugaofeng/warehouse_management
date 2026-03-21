# 出库管理系统 - 完整API文档与实现指南

## 目录
1. [系统概述](#系统概述)
2. [核心流程](#核心流程)
3. [数据模型](#数据模型)
4. [API 端点详解](#api-端点详解)
5. [业务规则](#业务规则)
6. [错误处理](#错误处理)
7. [权限控制](#权限控制)
8. [集成示例](#集成示例)
9. [常见问题](#常见问题)

---

## 系统概述

出库管理系统是完整的商品出库流程管理解决方案，支持从销售订单到最终出库的全过程追踪和控制。

### 核心特性

| 特性 | 说明 |
|-----|------|
| **完整流程** | 销售单 → 分配 → 拣货 → 复核 → 出库 |
| **库存策略** | 支持FIFO和临近过期优先两种分配策略 |
| **部分出库** | 支持灵活的部分出库，自动更新剩余数量 |
| **自动锁定** | 分配时自动锁定库存，防止重复分配 |
| **库位转移** | 自动处理库存从正常区到拣货区的转移 |
| **库位清理** | 库存为0时自动删除记录并清理库位 |
| **完整审计** | 所有操作自动记录于库存变更日志 |
| **权限管理** | 支持细粒度权限控制 |

---

## 核心流程

### 流程图

```
┌─────────────────────────────────────────────────────────────┐
│                     销售单创建 (SalesOrder)                  │
│  order_no, customer_id, warehouse_id, outbound_type, items  │
│                     Status: pending_allocation                │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ↓
┌─────────────────────────────────────────────────────────────┐
│              分配单创建 (AllocationOrder)                    │
│   验证库存 → 选择分配策略(FIFO/近期过期) → 锁定库存          │
│         Status: pending → completed                          │
│         销售单更新: allocated                                │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ↓
┌─────────────────────────────────────────────────────────────┐
│              拣货单创建 (PickingOrder)                       │
│   库存转移: normal库位 → picking库位                         │
│   解除库存锁定 → 生成库存变更日志                           │
│         Status: pending → in_progress → completed            │
│         销售单更新: picked                                   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ↓
┌─────────────────────────────────────────────────────────────┐
│              复核单管理 (InspectionOrder)                    │
│   复核商品数量与质量 → 通过或失败                           │
│   新增: inspection_type=outbound支持出库复核                │
│         Status: pending → passed/failed                      │
│         销售单更新: inspected                                │
└──────────────────────────┬──────────────────────────────────┘
                           │ (通过)
                           ↓
┌─────────────────────────────────────────────────────────────┐
│              出库单创建 (ShippingOrder)                      │
│   扣减拣货区库存 → 生成库存变更日志 → 清理库位              │
│   支持部分出库，自动更新剩余数量                            │
│         Status: pending → partialShipped → completed          │
│         销售单更新: shipped                                  │
└─────────────────────────────────────────────────────────────┘
```

### 状态转换总览

| 模块 | 状态流转 | 说明 |
|-----|---------|-----|
| **销售单** | pending_allocation → allocated → picked → inspected → shipped | 完整的状态转换路径 |
| **分配单** | pending → completed (或 failed) | 库存验证失败时为failed |
| **拣货单** | pending → in_progress → completed | 库位转移过程 |
| **复核单** | pending → passed/failed/repicking | 质量检验结果 |
| **出库单** | pending → partialShipped → completed | 支持部分出库 |

---

## 数据模型

### 1. SalesOrder（销售单）

**表名**: `sales_orders`

| 字段 | 类型 | 约束 | 说明 |
|-----|------|------|------|
| id | Integer | PK | 主键 |
| order_no | String(32) | UNIQUE | 销售单号，自动生成(SO+日期+随机数) |
| related_order | String(32) | - | 来源采购单号 |
| customer_id | Integer | FK | 关联客户ID |
| warehouse_id | Integer | FK | 发货仓库ID |
| outbound_type | String(16) | - | 出库类型: normal/express/special |
| expected_outbound_date | Date | - | 期望出库日期 |
| status | String(16) | - | 状态: pending_allocation/allocated/picked/inspected/shipped |
| total_quantity | Integer | - | 销售单总数量 |
| allocated_quantity | Integer | - | 已分配数量 |
| picked_quantity | Integer | - | 已拣货数量 |
| shipped_quantity | Integer | - | 已出库数量 |
| operator_id | Integer | FK | 创建人ID |
| allocation_manager_id | Integer | FK | 分配负责人ID |
| remark | String(256) | - | 备注 |
| create_time | DateTime | - | 创建时间 |
| update_time | DateTime | - | 更新时间 |

**关联关系**:
- `customer`: 关联Customer表，1:N关系
- `warehouse`: 关联WarehouseLocation表，N:1关系
- `items`: SalesOrderItem 1:N (cascade删除)
- `allocation_order`: 1:1关系
- `picking_order`: 1:1关系
- `inspection_order`: 1:1关系
- `shipping_order`: 1:1关系

### 2. SalesOrderItem（销售单明细）

**表名**: `sales_order_items`

| 字段 | 类型 | 说明 |
|-----|------|------|
| id | Integer | 主键 |
| order_id | Integer | FK，关联销售单 |
| product_id | Integer | FK，关联商品 |
| quantity | Integer | 需求数量 |
| unit_price | Float | 单价（可选） |
| subtotal | Float | 小计（可选） |
| preferred_batch_no | String(32) | 指定批次号（优先使用） |

**约束**: (order_id, product_id) UNIQUE

### 3. AllocationOrder（分配单）

**表名**: `allocation_orders`

| 字段 | 类型 | 说明 |
|-----|------|------|
| id | Integer | 主键 |
| allocation_no | String(32) | 分配单号，自动生成(AL+日期+随机数) |
| sales_order_id | Integer | FK，关联销售单 |
| warehouse_id | Integer | FK，发货仓库 |
| allocation_strategy | String(16) | 分配策略: fifo/near_expiry |
| status | String(16) | pending/completed/failed |
| total_allocated_qty | Integer | 已分配总数量 |
| operator_id | Integer | FK，分配员 |
| manager_id | Integer | FK，审批人 |
| approved_time | DateTime | 审批时间 |
| remark | String(256) | 备注 |
| create_time | DateTime | 创建时间 |
| update_time | DateTime | 更新时间 |

### 4. AllocationItem（分配单明细）

**表名**: `allocation_items`

| 字段 | 类型 | 说明 |
|-----|------|------|
| id | Integer | 主键 |
| allocation_id | Integer | FK，关联分配单 |
| sales_order_item_id | Integer | FK，关联销售单明细 |
| inventory_id | Integer | FK，关联库存 |
| allocated_qty | Integer | 分配数量 |
| snapshot_quantity | Integer | 分配时的库存数量快照 |
| snapshot_batch_no | String(32) | 分配时的批次号快照 |
| snapshot_expire_date | Date | 分配时的过期日期快照 |
| status | String(16) | allocated/picked/shipped |

**约束**: (allocation_id, inventory_id) UNIQUE

### 5. PickingOrder（拣货单）

**表名**: `picking_orders`

| 字段 | 类型 | 说明 |
|-----|------|------|
| id | Integer | 主键 |
| picking_no | String(32) | 拣货单号，自动生成(PI+日期+随机数) |
| allocation_order_id | Integer | FK，关联分配单 |
| sales_order_id | Integer | FK，关联销售单 |
| warehouse_id | Integer | FK，发货仓库 |
| picking_location_id | Integer | FK，拣货区库位 |
| status | String(16) | pending/in_progress/completed/failed |
| total_picked_qty | Integer | 已拣货总数量 |
| warehouse_staff_id | Integer | FK，拣货员 |
| manager_id | Integer | FK，拣货主管 |
| completed_time | DateTime | 完成时间 |
| remark | String(256) | 备注 |
| create_time | DateTime | 创建时间 |
| update_time | DateTime | 更新时间 |

### 6. PickingItem（拣货单明细）

**表名**: `picking_items`

| 字段 | 类型 | 说明 |
|-----|------|------|
| id | Integer | 主键 |
| picking_id | Integer | FK，关联拣货单 |
| allocation_item_id | Integer | FK，关联分配单明细 |
| inventory_id | Integer | FK，源库存 |
| picked_qty | Integer | 拣货数量 |
| source_location_id | Integer | FK，源库位 |
| target_location_id | Integer | FK，目标库位（拣货区） |
| snapshot_quantity | Integer | 拣货时的库存快照 |
| snapshot_locked | Integer | 拣货时的锁定数量快照 |
| status | String(16) | pending/in_progress/completed |
| change_log_id | Integer | FK，库存变更日志 |
| create_time | DateTime | 创建时间 |
| completed_time | DateTime | 完成时间 |

### 7. ShippingOrder（出库单）

**表名**: `shipping_orders` (原 `outbound_orders`)

| 字段 | 类型 | 说明 |
|-----|------|------|
| id | Integer | 主键 |
| shipping_no | String(32) | 出库单号，自动生成(SH+日期+随机数) |
| inspection_order_id | Integer | FK，关联复核单 |
| sales_order_id | Integer | FK，关联销售单 |
| picking_order_id | Integer | FK，关联拣货单 |
| receiver | String(32) | 收货人名称 |
| receiver_phone | String(16) | 收货人电话 |
| receiver_address | String(256) | 收货地址 |
| outbound_date | Date | 实际出库日期 |
| total_quantity | Integer | 计划出库数量 |
| shipped_quantity | Integer | 已出库数量 |
| remaining_quantity | Integer | 剩余可出库数量 |
| status | String(16) | pending/partialShipped/completed/canceled |
| operator_id | Integer | FK，操作员 |
| approver_id | Integer | FK，审批人 |
| approved_time | DateTime | 审批时间 |
| purpose | String(64) | 出库用途 |
| remark | String(256) | 备注 |
| related_order | String(32) | 关联采购单号 |
| create_time | DateTime | 创建时间 |
| completed_time | DateTime | 出库完成时间 |

### 8. ShippingItem（出库单明细）

**表名**: `shipping_items` (原 `outbound_items`)

| 字段 | 类型 | 说明 |
|-----|------|------|
| id | Integer | 主键 |
| shipping_id | Integer | FK，关联出库单 |
| picking_item_id | Integer | FK，关联拣货单明细 |
| inventory_id | Integer | FK，拣货区库存 |
| location_id | Integer | FK，出库库位 |
| product_id | Integer | FK，商品 |
| unit_price | Float | 单价 |
| planned_quantity | Integer | 计划出库数量 |
| shipped_quantity | Integer | 已出库数量 |
| remaining_quantity | Integer | 剩余可出库数量 |
| snapshot_quantity | Integer | 出库前库存快照 |
| change_log_id | Integer | FK，库存变更日志 |
| create_time | DateTime | 创建时间 |

---

## API 端点详解

### A. 销售单管理 (`/sales`)

#### 1. 列表 GET /sales/list

**查询参数**:
```
keyword: 销售单号或采购单号搜索
customer_id: 客户ID过滤
status: 状态过滤(pending_allocation/allocated/picked/inspected/shipped)
date_from: 创建日期范围起点
date_to: 创建日期范围终点
page: 分页（默认1，10条/页）
```

**响应示例**:
```json
{
  "orders": [
    {
      "id": 1,
      "order_no": "SO20250319001",
      "customer": {"id": 1, "name": "ABC公司"},
      "status": "allocated",
      "total_qty": 100,
      "allocated_qty": 100,
      "create_time": "2025-03-19 10:00:00"
    }
  ],
  "pagination": {...}
}
```

#### 2. 创建 GET/POST /sales/create

**GET**: 展示创建表单，返回:
- customers: 启用的客户列表
- warehouses: 启用的仓库库位列表
- products: 全部商品列表

**POST**: 创建销售单

**请求体** (multipart/form-data):
```
customer_id: 客户ID (必填)
warehouse_id: 仓库库位ID (必填)
outbound_type: 出库类型 normal/express/special (必填)
expected_outbound_date: 期望出库日期 YYYY-MM-DD (必填)
related_order: 来源采购单号 (可选)
remark: 备注 (可选)

// 销售单明细（数组）
product_id[]: 商品ID数组
quantity[]: 数量数组
unit_price[]: 单价数组 (可选)
```

**请求示例**:
```bash
curl -X POST http://localhost:5000/sales/create \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "customer_id=1&warehouse_id=5&outbound_type=normal&expected_outbound_date=2025-03-25&product_id[]=1&product_id[]=2&quantity[]=100&quantity[]=50"
```

**成功响应** (302 重定向):
- Redirect to `/sales/detail/<id>`
- Flash: "销售单 SO20250319001 创建成功"

**失败响应**:
```
Flash: "只能修改待分配状态的销售单" / "创建失败: ..." (400)
```

#### 3. 详情 GET /sales/detail/<int:id>

**响应信息**:
- 销售单基本信息
- 销售单明细列表 (items)
- 关联的分配单、拣货单、复核单、出库单

#### 4. 更新 POST /sales/detail/<int:id>/update

**限制**: 仅限待分配状态 (pending_allocation)

**请求体**:
```
expected_outbound_date: 新的期望出库日期
remark: 备注
```

#### 5. 删除 POST /sales/detail/<int:id>/delete

**限制**: 仅限待分配状态

**成功**: Flash "销售单 SO20250319001 已删除"

#### 6. API: 获取客户信息 GET /sales/api/customer/<int:customer_id>

**响应**:
```json
{
  "id": 1,
  "name": "ABC公司",
  "code": "C001",
  "phone": "0571-xxxx",
  "email": "abc@example.com",
  "address": "杭州市..."
}
```

#### 7. API: 获取商品信息 GET /sales/api/product/<int:product_id>

**响应**:
```json
{
  "id": 1,
  "code": "SKU001",
  "name": "商品名称",
  "spec": "规格型号",
  "unit": "个",
  "warning_stock": 10
}
```

---

### B. 分配单管理 (`/allocation`)

#### 1. 列表 GET /allocation/list

**查询参数**:
```
status: 状态(pending/completed/failed)
strategy: 分配策略(fifo/near_expiry)
keyword: 分配单号或销售单号搜索
page: 分页
```

#### 2. 创建 GET/POST /allocation/create/<int:sales_order_id>

**前置条件**:
- 销售单状态为 `pending_allocation`
- 销售单无关联的分配单

**GET**: 展示分配页面，包括:
- 库存验证结果（库存是否充足）
- 缺货商品明细（如有）
- 分配策略选项

**POST**: 创建分配单并执行分配逻辑

**请求体**:
```
allocation_strategy: fifo 或 near_expiry (必填)
remark: 备注 (可选)
```

**业务逻辑**:
1. 验证库存: 对每个销售单明细，检查仓库可用库存
2. 选择分配策略:
   - **FIFO**: 按生产日期升序排列（oldest first）
   - **near_expiry**: 按过期日期升序排列（expires soon first）
3. 分配库存: 逐行匹配销售单需求，创建AllocationItem记录
4. 锁定库存: 对每条Inventory调用 `lock_quantity(allocated_qty)`
5. 记录日志: 为每次锁定生成InventoryChangeLog
6. 更新状态: 销售单 → allocated, 分配单 → completed

**成功响应**:
```
Flash: "分配单 AL20250319001 创建成功"
Redirect: /allocation/detail/<id>
```

**失败响应示例**:
```
Flash: "库存不足，无法完成分配。商品A缺少50件；商品B缺少20件"
HTTP: 400
```

#### 3. 详情 GET /allocation/detail/<int:id>

**展示信息**:
- 分配单头部信息（分配单号、销售单关联、策略、状态）
- 分配明细列表：
  - 商品信息（编码、名称、规格）
  - 分配来源库位
  - 分配数量、批次号、过期日期等快照信息

#### 4. 审批 POST /allocation/detail/<int:id>/approve

**限制**: 仅限待审批状态 (pending)

**操作**:
- 更新分配单状态 → completed
- 设置 manager_id, approved_time

#### 5. 拒绝 POST /allocation/detail/<int:id>/reject

**操作**:
1. 对每个AllocationItem，解锁对应库存: `unlock_quantity(allocated_qty)`
2. 记录解锁日志: InventoryChangeLog, change_type='unlock'
3. 更新分配单状态 → failed
4. 恢复销售单状态 → pending_allocation, allocated_qty = 0

---

### C. 拣货单管理 (`/picking`)

#### 1. 列表 GET /picking/list

**查询参数**:
```
status: 拣货状态(pending/in_progress/completed)
keyword: 拣货单号或销售单号搜索
page: 分页
```

#### 2. 创建 GET/POST /picking/create/<int:allocation_order_id>

**前置条件**:
- 分配单状态为 `completed`

**GET**: 展示创建页面
- 拣货区库位列表（location_type='picking'）

**POST**: 创建拣货单，为分配单中的每一项创建PickingItem

**请求体**:
```
picking_location_id: 拣货区库位ID (必填)
```

**业务逻辑**:
1. 创建PickingOrder记录
2. 为AllocationOrder中的每一条AllocationItem创建PickingItem:
   - source_location: 原库位
   - target_location: 拣货区库位
   - 拍摄库存快照 (snapshot_quantity, snapshot_locked)

#### 3. 详情 GET /picking/detail/<int:id>

**展示**:
- 拣货单头部信息
- 拣货项列表，包括：
  - 商品信息
  - 源库位 → 目标库位（拣货区）
  - 拣货数量
  - 拣货项状态（pending/in_progress/completed）

#### 4. 完成拣货项 POST /picking/detail/<int:id>/item/<int:item_id>/complete

**验证**:
1. 库存未改变（数量与位置一致）
2. 拣货项未完成

**操作**:
1. 创建目标库位库存记录（如不存在）
2. 库位转移:
   - source_location.quantity -= picked_qty
   - target_location.quantity += picked_qty
3. 解锁库存: `unlock_quantity(picked_qty)`
4. 更新拣货项状态 → completed
5. 记录库存变更日志: change_type='location_transfer'

**成功响应**:
```
Flash: "拣货项已完成，已转移 50 件"
```

#### 5. 完成拣货单 POST /picking/detail/<int:id>/complete

**验证**: 所有拣货项都已完成

**操作**:
1. 更新拣货单状态 → completed
2. 更新销售单状态 → picked, picked_quantity = total_picked
3. 更新分配单状态 → completed

#### 6. API: 获取拣货单状态 GET /picking/api/picking/<int:id>/status

**响应**:
```json
{
  "picking_no": "PI20250319001",
  "status": "completed",
  "total_picked": 100,
  "items": [
    {
      "id": 1,
      "product_name": "商品A",
      "picked_qty": 100,
      "status": "completed",
      "source_location": "A-01-01",
      "target_location": "P-01-01"
    }
  ],
  "can_complete": true
}
```

---

### D. 出库单管理 (`/shipping`)

#### 1. 列表 GET /shipping/list

**查询参数**:
```
status: 出库状态(pending/partialShipped/completed)
keyword: 出库单号或销售单号搜索
page: 分页
```

#### 2. 创建 GET/POST /shipping/create/<int:inspection_order_id>

**前置条件**:
- 检验单类型为 outbound
- 检验单状态为 passed

**GET**: 展示创建表单
- 默认收货人：销售单关联的客户名称

**POST**: 创建出库单及出库明细

**请求体**:
```
receiver: 收货人名称 (必填)
receiver_phone: 收货人电话 (可选)
receiver_address: 收货地址 (可选)
purpose: 出库用途 (可选)
remark: 备注 (可选)
```

**业务逻辑**:
1. 创建ShippingOrder记录
2. 为PickingOrder中的每个已完成的PickingItem创建ShippingItem:
   - inventory_id: 拣货区库存ID
   - planned_quantity: picking_item.picked_qty
   - remaining_quantity: 初始等于planned_quantity
3. 设置状态: pending, shipped_qty=0

#### 3. 详情 GET /shipping/detail/<int:id>

**展示**:
- 出库单头部信息（出库单号、收货人、状态、已出库数/计划数）
- 出库明细表：
  - 商品信息（编码、名称、规格）
  - 计划出库数 | 已出库数 | 剩余数
  - 操作按钮："出库"

#### 4. 出库单个商品 POST /shipping/detail/<int:id>/item/<int:item_id>/ship

**参数**:
```
ship_qty: 本次出库数量 (必填，≤ remaining_quantity)
```

**验证**:
1. ship_qty > 0 且 ≤ remaining_qty
2. Inventory.quantity ≥ ship_qty

**操作**:
1. 扣减库存: inventory.quantity -= ship_qty
2. 更新出库项: shipped_qty += ship_qty, remaining_qty -= ship_qty
3. 更新出库单: shipped_qty += ship_qty, remaining_qty -= ship_qty
4. 更新出库单状态:
   - 如 remaining_qty > 0: status = partialShipped
   - 如 remaining_qty == 0: status = completed, completed_time = now()
5. 记录日志: InventoryChangeLog, change_type='outbound'
6. 库存清理: 如 inventory.quantity == 0，删除库存记录，清理库位

**成功响应**:
```
Flash: "已出库 50 件"
(如果整单完成) Flash: "出库单已完成，销售单已标记为已出库"
```

#### 5. 完成出库单 POST /shipping/detail/<int:id>/complete

**验证**: remaining_qty == 0（全部出库）

**操作**:
1. 更新出库单状态 → completed
2. 更新销售单 → shipped

#### 6. API: 获取出库单状态 GET /shipping/api/shipping/<int:id>/status

**响应**:
```json
{
  "shipping_no": "SH20250319001",
  "status": "partialShipped",
  "total_qty": 100,
  "shipped_qty": 60,
  "remaining_qty": 40,
  "receiver": "某某公司",
  "items": [
    {
      "id": 1,
      "product_name": "商品A",
      "product_code": "SKU001",
      "planned_qty": 100,
      "shipped_qty": 60,
      "remaining_qty": 40,
      "location": "P-01-01"
    }
  ]
}
```

---

## 业务规则

### 库存分配规则

#### FIFO 策略 (First-In-First-Out)

```python
# 按生产日期升序排列，优先分配最早生产的商品
SELECT inventory 
FROM inventories 
WHERE product_id = ? AND location_id = ? AND available_qty > 0
ORDER BY production_date ASC NULLS LAST, create_time ASC
```

**适用场景**: 
- 商品无明显过期风险
- 需要保证库存周转秩序

#### Near Expiry 策略（临近过期优先）

```python
#按过期日期升序排列，优先分配快要过期的商品
SELECT inventory 
FROM inventories 
WHERE product_id = ? AND location_id = ? AND available_qty > 0
ORDER BY expire_date ASC NULLS LAST, production_date ASC NULLS LAST
```

**适用场景**:
- 商品有明确过期日期（食品、药品等）
- 防止过期损失

#### 指定批次优先

如果销售单明细中指定了 `preferred_batch_no`，系统将优先尝试从该批次分配。只有该批次库存不足时，才会扩大搜索范围到其他批次。

### 库存锁定机制

**目的**: 防止已分配的库存被其他出库单重复分配

**流程**:
1. 分配单创建时，对每条AllocationItem对应的Inventory调用 `lock_quantity(qty)`
2. Inventory 的 locked_qty 增加，available_qty 相应减少
3. 拣货完成时，通过 `unlock_quantity(qty)` 解锁
4. 若分配失败（拒绝），通过拒绝端点批量解锁所有分配的库存

**库存计算**:
```
可用数量 = 物理库存 - 锁定数量 - 冻结数量
```

### 库位转移规则

**正常流程**（拣货）:
```
normal库位 (source)  →  picking库位 (target)
inventory.quantity 从source减少，到target增加
locked_qty 在source解锁
库存记录最终转移到target库位
```

**库位清理规则**:
- 当库位内某个库存记录quantity=0时，删除该记录
- 若库位内所有库存都被删除，该库位自动标记为"空闲"
- 不删除库位本身，可继续使用

### 部分出库规则

**支持场景**: 拣货区库存可部分出库

**流程**:
1. 创建出库单时，将计划出库数设为拣货数量
2. 在详情页可逐次出库，每次可出库任意数量 ≤ remaining_qty
3. 系统自动更新:
   - shipping_item.remaining_qty -= ship_qty
   - shipping_order.remaining_qty -= ship_qty
4. 根据remaining_qty更新out_order状态:
   - 0 < remaining < total: status = partialShipped
   - 0 = remaining: status = completed

### 复核单（质量检验）

**出库前复核 (新增)**:

InspectionOrder 扩展支持 `inspection_type='outbound'`:

| 字段 | 说明 |
|-----|------|
| inspection_type | inbound(入库检) / outbound(出库检) |
| sales_order_id | 关联销售单（仅outbound） |
| picking_order_id | 关联拣货单（仅outbound） |
| status | pending → passed / failed / repicking |
| recheck_items | 复核总项数 |
| recheck_passed_items | 复核通过项数 |
| recheck_failed_items | 复核失败项数 |

**复核流程**:
1. 拣货完成后创建复核单
2. 逐项检验商品数量和质量
3. 通过 (passed): 触发出库单创建， sales_order → inspected
4. 失败 (failed): 标记为repicking，允许重新拣货

---

## 错误处理

### HTTP 状态码

| 状态码 | 含义 | 示例 |
|--------|------|------|
| 200 | 成功 | GET 列表 |
| 302 | 重定向 | POST 创建后重定向详情页 |
| 400 | 业务验证失败 | 库存不足、数据缺失 |
| 404 | 资源不存在 | 销售单ID无效 |
| 500 | 服务器错误 | 数据库操作异常 |

### 常见错误信息

| 错误 | 原因 | 处理 |
|-----|------|------|
| "库存不足，无法完成分配。商品A缺少50件" | 仓库库存不足 | 扩大库存来源或调整需求量 |
| "只能为已完成的分配单创建拣货单" | 分配单状态不对 | 确保分配单已完成审批 |
| "库存已改变，无法完成拣货" | 拣货期间库存被其他操作改变 | 重新创建拣货单，重新拣货 |
| "拣货区库存缺失，无法创建出库单" | 拣货单数据不一致 | 检查并修复库存数据 |
| "库存不足。库存量: 40, 出库数: 50" | 拣货区库存不足 | 减少出库数量或重新拣货 |

### 事务处理

关键操作都在数据库事务中执行：

```python
try:
    # 执行业务操作
    db.session.add(...)
    db.session.commit()
    flash('成功', 'success')
except Exception as e:
    db.session.rollback()  # 回滚所有修改
    flash(f'失败: {str(e)}', 'danger')
```

---

## 权限控制

### 权限方案

所有端点均需要 `inventory_manage` 权限：

```python
@permission_required('inventory_manage')
@login_required
def endpoint():
    ...
```

### 建议的权限分配

| 角色 | 权限 | 职责 |
|-----|------|------|
| 销售员 | sales_create | 创建销售单 |
| 仓库员 | inventory_manage | 分配、拣货、出库 |
| 仓库主管 | inventory_manage | 审批分配单，复核拣货 |
| 系统管理员 | 所有权限 | 全量访问 |

---

## 集成示例

### Python/Flask 集成

```python
from app.models import SalesOrder, AllocationOrder
from app.models import db

# 创建销售单（编程方式）
sales = SalesOrder(
    order_no='SO20250319001',
    customer_id=1,
    warehouse_id=5,
    outbound_type='normal',
    expected_outbound_date='2025-03-25',
    operator_id=current_user.id,
    total_quantity=100,
    status='pending_allocation'
)

# 添加明细
from app.models import SalesOrderItem
item = SalesOrderItem(
    order=sales,
    product_id=1,
    quantity=100,
    unit_price=10.0
)

db.session.add_all([sales, item])
db.session.commit()

# 创建分配单（自动执行分配逻辑）
from app.views.allocation_manage import allocate_by_fifo, validate_allocation

can_allocate, missing, msg = validate_allocation(sales)
if can_allocate:
    allocation = AllocationOrder(
        allocation_no='AL20250319001',
        sales_order_id=sales.id,
        warehouse_id=sales.warehouse_id,
        allocation_strategy='fifo',
        operator_id=current_user.id
    )
    db.session.add(allocation)
    db.session.flush()
    
    # 执行FIFO分配...
```

### API 调用示例（cURL）

```bash
# 1. 创建销售单
curl -X POST http://localhost:5000/sales/create \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "Cookie: session=..." \
  -d "customer_id=1&warehouse_id=5&outbound_type=normal&expected_outbound_date=2025-03-25&product_id[]=1&quantity[]=100"

# 2. 创建分配单
curl -X POST http://localhost:5000/allocation/create/1 \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "Cookie: session=..." \
  -d "allocation_strategy=fifo"

# 3. 创建拣货单
curl -X POST http://localhost:5000/picking/create/1 \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "Cookie: session=..." \
  -d "picking_location_id=10"

# 4. 完成拣货项
curl -X POST http://localhost:5000/picking/detail/1/item/1/complete \
  -H "Cookie: session=..."

# 5. 创建出库单
curl -X POST http://localhost:5000/shipping/create/1 \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "Cookie: session=..." \
  -d "receiver=某某公司&receiver_phone=0571-xxxx&receiver_address=杭州..."

# 6. 出库
curl -X POST http://localhost:5000/shipping/detail/1/item/1/ship \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "Cookie: session=..." \
  -d "ship_qty=50"

# 7. 完成出库单
curl -X POST http://localhost:5000/shipping/detail/1/complete \
  -H "Cookie: session=..."
```

---

## 常见问题

### Q1: 库存不足时如何处理？

**A**: 系统会在分配验证阶段检查库存。如果库存不足，系统会显示缺货明细。

两种处理方式：
1. **扩大来源**: 从其他仓库调货
2. **调整需求**: 减少销售单数量或取消订单

### Q2: 支持跨仓库分配吗？

**A**: 当前设计中，一个销售单绑定一个仓库。跨仓库分配需要：
1. 创建多个销售单（每个销售单一个仓库）
2. 或修改销售单与库位的关联模式

如需跨仓库支持，需修改 SalesOrder.warehouse_id 为一对多关系。

### Q3: 拣货期间库存被修改（如入库）怎么办？

**A**: 系统通过库存快照机制检测修改：

```python
# 在 PickingItem.can_complete() 中
if inventory.quantity != picking_item.snapshot_quantity:
    return False  # 库存已改变，无法拣货
```

此时需要重新创建拣货单。

### Q4: 已出库的单据能否撤销？

**A**: 当前系统不支持已出库单据的撤销。  
原因：库存已扣减，库位已清理，难以完全回到出库前状态。

建议处理方式：
1. 以退货单 (ReturnOrder) 进行反向操作
2. 或创建新的入库单恢复库存

### Q5: 支持出库单的合并或拆分吗？

**A**: 不支持。每个销售单对应一个独立的出库流程。

如需组合：在销售订单层面处理（多商品一张销售单）

### Q6: 如何导给第三方物流？

**A**: 系统对出库单信息已支持导出：

```python
# 可通过 ShippingOrder.get_summary() 获取信息
{
    'shipping_no': 'SH20250319001',
    'receiver': '...',
    'items': [...]
}
```

可集成到第三方平台或生成面单。

### Q7: 部分出库后能否再次出库？

**A**: 可以。系统支持灵活的部分出库：

```
remaining_qty = 100
第一次出库: 60件，remaining = 40
第二次出库: 30件，remaining = 10
第三次出库: 10件，remaining = 0 (完成)
```

---

## 更新日志

### v1.0 (2025-03-19)

**新增模块**:
- ✅ 销售单管理 (SalesOrder, SalesOrderItem)
- ✅ 分配单管理 (AllocationOrder, AllocationItem)
  - FIFO 分配策略
  - 近期过期优先策略
  - 库存验证与锁定
- ✅ 拣货单管理 (PickingOrder, PickingItem)
  - 库位转移 (normal → picking)
  - 库存解锁
- ✅ 复核单扩展 (InspectionOrder)
  - 支持outbound类型
  - 出库前质检
- ✅ 出库单管理 (ShippingOrder, ShippingItem)
  - 部分出库支持
  - 库存自动清理
  - 库位管理

**完整的API端点**: 30+ 个端点覆盖整个流程

**库存管理**:
- 自动库存锁定/解锁
- 库位转移跟踪
- 完整的库存变更审计

---

**文档版本**: 1.0  
**最后更新**: 2025-03-19  
**维护者**: 系统管理员
