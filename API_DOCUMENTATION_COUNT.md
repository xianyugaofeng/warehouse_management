# 库存盘点模块 API 文档

## 1. 盘点单管理 API

### 1.1 盘点单列表
**路由** `GET /count/list`  
**权限** `inventory_manage`  
**描述** 分页获取盘点单列表

**查询参数**
| 参数名 | 类型 | 必填 | 说明 |
|------|------|------|------|
| keyword | string | N | 盘点单号（模糊匹配） |
| count_type | string | N | 盘点方式：`open_count` (明盘) \| `blind_count` (暗盘) |
| status | string | N | 状态：`draft` \| `in_progress` \| `completed` \| `closed` |
| page | integer | N | 页码（默认1） |

**响应示例**
```html
盤點單列表頁面（HTML）
包含以下信息：
- count_no: 盘点单号
- count_type: 盘点方式
- status: 状态
- total_items: 商品总数
- counted_items: 已盘数量
- variance_items: 差异数量
- create_time: 创建时间
```

---

### 1.2 创建盘点单
**路由** `GET/POST /count/create`  
**权限** `inventory_manage`  
**描述** 创建新的盘点单并自动生成库存快照

**请求方法** `POST`  
**Content-Type** `application/x-www-form-urlencoded`

**请求参数**
| 参数名 | 类型 | 必填 | 说明 |
|------|------|------|------|
| count_type | string | Y | 盘点方式：`open_count` (明盘) \| `blind_count` (暗盘) |
| scope_type | string | Y | 范围类型：`all` (全部) \| `location` (库位) \| `category` (分类) \| `product` (商品) |
| location_ids / category_ids / product_ids | array | Y* | 范围条件（根据scope_type决定） |
| plan_date | date | Y | 计划盘点日期（YYYY-MM-DD） |
| remark | string | N | 备注 |

**响应** 重定向到盘点单详情页面（HTTP 302）

**异常处理**
```json
{
  "error": "创建盘点单失败: 错误信息"
}
```

---

### 1.3 盘点单详情
**路由** `GET /count/detail/<count_id>`  
**权限** `inventory_manage`  
**描述** 获取盘点单详情与明细列表，支持逐条录入实盘数量

**URL参数**
| 参数名 | 类型 | 说明 |
|------|------|------|
| count_id | integer | 盘点单ID |
| page | integer | 明细分页（默认1） |

**响应** HTML页面，包含：
- 盘点单基本信息（单号、方式、状态、进度条）
- 盘点明细表（分页展示，每页20条）
  - 若为明盘模式：显示快照数据（物理库存、锁定、冻结、可用）
  - 若为暗盘模式：隐藏快照数据
  - 实盘数量输入框（自动计算差异）
- 操作按钮：批量导入、导出模板、预览差异

---

### 1.4 更新单条盘点明细
**路由** `POST /count/detail/<count_id>/update_item/<detail_id>`  
**权限** `inventory_manage`  
**描述** 更新单条明细的实盘数量，自动计算差异

**请求体** `application/json`
```json
{
  "counted_qty": 105,           // 实盘数量（必填，非负整数）
  "reason": "损耗2件"             // 差异原因（可选）
}
```

**成功响应** (HTTP 200)
```json
{
  "success": true,
  "message": "实盘数量已更新",
  "variance_qty": 5,              // 差异数量
  "variance_type": "gain"         // 差异类型：gain|loss|none
}
```

**错误响应** (HTTP 400/500)
```json
{
  "success": false,
  "message": "错误信息"
}
```

---

### 1.5 差异预览
**路由** `GET /count/detail/<count_id>/variance_preview`  
**权限** `inventory_manage`  
**描述** 分类显示差异情况（盘盈、盘亏、无差异、未实盘）

**响应** HTML页面，包含：
- 摘要统计（盘盈数量、盘亏数量、无差异数、未实盘数）
- 盘盈明细表
- 盘亏明细表
- 无差异明细表
- 未实盘警告提示
- 生成差异单按钮

---

### 1.6 生成差异单
**路由** `POST /count/detail/<count_id>/generate_variances`  
**权限** `inventory_manage`  
**描述** 根据差异明细生成盘盈/盘亏单，并冻结差异数量

**请求方法** `POST`  
**请求体** 无

**响应** 重定向到盘点单详情页面

**副作用**
- 创建VarianceDocument记录（盘盈和/或盘亏）
- 创建VarianceDetail明细行
- 创建InventoryFreezeRecord冻结记录
- 更新库存frozen_quantity
- 盘点单状态更新为 'completed'

---

## 2. 差异单管理 API

### 2.1 差异单列表
**路由** `GET /count/variances/list`  
**权限** `inventory_manage`  
**描述** 分页获取差异单列表（默认显示待审核）

**查询参数**
| 参数名 | 类型 | 说明 |
|------|------|------|
| status | string | 状态：`pending` (待审) \| `approved` (已通过) \| `rejected` (已驳回)，默认 pending |
| variance_type | string | 类型：`gain` (盘盈) \| `loss` (盘亏) |
| page | integer | 页码（默认1） |

**响应** HTML页面，差异单列表含：
- variance_no: 差异单号
- variance_type: 类型
- status: 状态
- total_variance_qty: 总差异数量
- total_items: 明细项数

---

### 2.2 差异单详情
**路由** `GET /count/variances/<variance_id>/detail`  
**权限** `inventory_manage`  
**描述** 获取差异单详情与明细

**URL参数**
| 参数名 | 类型 | 说明 |
|------|------|------|
| variance_id | integer | 差异单ID |

**响应** HTML页面，包含：
- 差异单头部信息（单号、类型、状态、总数量）
- 差异明细表（每行包含商品编码、名称、库位、快照数、实盘数、差异数、锁定、冻结等）
- 审核操作区（若状态为pending）或审核结果（若已审核）

---

### 2.3 审核通过差异单
**路由** `POST /count/variances/<variance_id>/approve`  
**权限** `inventory_manage`  
**描述** 审核通过差异单，执行库存调整并解冻

**请求方法** `POST`  
**Content-Type** `application/x-www-form-urlencoded`

**请求参数**
| 参数名 | 类型 | 说明 |
|------|------|------|
| force | string | 可选，值为 '1' 表示强制通过（允许负可用） |

**响应** 重定向到差异单详情页面

**库存调整规则**
- **盘盈单**：physical_qty += variance_qty；frozen_qty 保持不变或减少（根据冻结记录）
- **盘亏单**：physical_qty -= abs(variance_qty)；frozen_qty -= abs(variance_qty)
- 调整后若 physical_qty < (locked_qty + frozen_qty) 且 force=false，返回错误
- 若 force=true 则忽略上述校验，记录 force_approved=true

**生成库存变更日志**
```
change_type: 'count_adjustment'
reason: '盘点单 #{count_no} - {盘盈|盘亏}'
reference_type: 'variance'
reference_id: variance_id
```

---

### 2.4 驳回差异单
**路由** `POST /count/variances/<variance_id>/reject`  
**权限** `inventory_manage`  
**描述** 驳回差异单，解冻库存并允许重新盘点

**请求方法** `POST`  
**Content-Type** `application/x-www-form-urlencoded`

**请求参数**
| 参数名 | 类型 | 说明 |
|------|------|------|
| reason | string | 驳回原因（可选） |

**响应** 重定向到差异单详情页面

**副作用**
- 差异单状态更新为 'rejected'
- 所有关联的冻结记录状态更新为 'released'
- 库存 frozen_qty 减少相应冻结数量

---

## 3. 数据导入/导出 API

### 3.1 批量导入实盘数量
**路由** `POST /count/detail/<count_id>/import`  
**权限** `inventory_manage`  
**描述** 通过Excel/CSV导入批量实盘数量

**请求方法** `POST`  
**Content-Type** `multipart/form-data`

**请求参数**
| 参数名 | 类型 | 说明 |
|------|------|------|
| file | file | Excel或CSV文件（必填） |

**文件格式要求**
- 必需列：`sku` (商品编码) 、`counted_qty` (实盘数量)
- 可选列：`product_name`、`spec`、`location`、`snapshot_qty`
- 数据类型：sku为字符串，counted_qty为非负整数

**成功响应** (HTTP 200)
```json
{
  "success": true,
  "message": "导入成功，更新 50 条记录",
  "error_count": 2,
  "errors": [
    [2, "SKU P001: 数量格式错误"],
    [5, "SKU P005: 不在当前盘点范围内"]
  ]
}
```

**错误响应** (HTTP 400)
```json
{
  "success": false,
  "message": "只支持 xlsx/xls/csv 格式"
}
```

**副作用**
- 更新成功行的 counted_quantity、counted_time、variance_quantity、variance_type

---

### 3.2 导出盘点模板
**路由** `GET /count/detail/<count_id>/export_template`  
**权限** `inventory_manage`  
**描述** 导出包含当前盘点明细的Excel模板

**响应** 
- Content-Type: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- Content-Disposition: `attachment; filename=count_{count_no}_template.xlsx`

**文件内容**
| sku | product_name | spec | location | snapshot_qty | counted_qty |
|-----|--------------|------|----------|--------------|-------------|
| P001 | 商品A | 10x10 | A-01-01 | 100 | (空) |
| ... | ... | ... | ... | ... | ... |

---

## 4. 数据模型与字段定义

### 4.1 InventoryCount（盘点单）
```json
{
  "id": 1,
  "count_no": "CT20250319001",
  "count_type": "open_count|blind_count",
  "scope_type": "all|location|category|product",
  "scope_filter": {"location_ids": [1, 2, 3]},
  "plan_date": "2025-03-19",
  "status": "draft|in_progress|completed|closed",
  "total_items": 100,
  "counted_items": 95,
  "variance_items": 5,
  "operator_id": 1,
  "operator": {"id": 1, "username": "user1", "real_name": "张三"},
  "approver_id": null,
  "approved_time": null,
  "remark": "定期盘点",
  "create_time": "2025-03-19T10:00:00",
  "update_time": "2025-03-19T10:30:00"
}
```

### 4.2 InventoryCountDetail（盘点明细）
```json
{
  "id": 1,
  "count_id": 1,
  "inventory_id": 5,
  "product_id": 1,
  "location_id": 1,
  "batch_no": "B001",
  "snapshot_quantity": 100,
  "snapshot_locked": 10,
  "snapshot_frozen": 5,
  "snapshot_available": 85,
  "snapshot_time": "2025-03-19T10:00:00",
  "counted_quantity": 105,
  "counted_time": "2025-03-19T10:15:00",
  "variance_quantity": 5,
  "variance_type": "gain|loss|none",
  "variance_reason": "发现漏点",
  "frozen_qty": 5,
  "freeze_record_id": 1,
  "variance_doc_id": 1,
  "create_time": "2025-03-19T10:00:00",
  "update_time": "2025-03-19T10:15:00"
}
```

### 4.3 VarianceDocument（盘盈/盘亏单）
```json
{
  "id": 1,
  "variance_no": "VD20250319001",
  "count_id": 1,
  "variance_type": "gain|loss",
  "status": "pending|approved|rejected",
  "total_variance_qty": 10,
  "total_items": 2,
  "approver_id": 2,
  "approved_time": "2025-03-19T11:00:00",
  "force_approved": false,
  "rejection_reason": null,
  "remark": "通常审核",
  "create_time": "2025-03-19T10:30:00",
  "update_time": "2025-03-19T11:00:00"
}
```

### 4.4 VarianceDetail（差异明细）
```json
{
  "id": 1,
  "variance_doc_id": 1,
  "count_detail_id": 1,
  "product_id": 1,
  "location_id": 1,
  "batch_no": "B001",
  "snapshot_quantity": 100,
  "counted_quantity": 105,
  "variance_quantity": 5,
  "snapshot_locked": 10,
  "snapshot_frozen": 5,
  "variance_reason": "发现漏点",
  "processed": true,
  "processed_time": "2025-03-19T11:00:00",
  "create_time": "2025-03-19T10:30:00"
}
```

### 4.5 InventoryFreezeRecord（冻结记录）
```json
{
  "id": 1,
  "product_id": 1,
  "location_id": 1,
  "inventory_id": 5,
  "freeze_qty": 5,
  "freeze_type": "count_gain|count_loss",
  "reason": "Count Order #CT20250319001 - loss variance",
  "variance_doc_id": 1,
  "count_id": 1,
  "status": "frozen|released",
  "frozen_time": "2025-03-19T10:30:00",
  "released_time": "2025-03-19T11:00:00",
  "released_reason": "Variance approved",
  "create_time": "2025-03-19T10:30:00",
  "update_time": "2025-03-19T11:00:00"
}
```

---

## 5. 业务流程图

```
┌─────────────────────────────────────────────────────────────┐
│                      盘点全流程                              │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│ 1. 创建盘点单 ──────────────→ 自动生成库存快照              │
│    (count_type, scope)        (snapshot_quantity,            │
│                               snapshot_locked,              │
│                               snapshot_frozen)              │
│                                  │                           │
│                                  ▼                           │
│ 2. 录入实盘数量 ─────────→ 自动计算差异                     │
│    (逐条/批量导入)        (variance_qty,                     │
│                           variance_type)                    │
│                                  │                           │
│                                  ▼                           │
│ 3. 预览差异 ────────────→ 分类显示                          │
│    (盘盈/盘亏/无差异)      (gain/loss/none)                │
│                                  │                           │
│                                  ▼                           │
│ 4. 生成差异单 ─────────→ 冻结库存                           │
│    (新建VD记录)           (frozen_quantity += variance)     │
│                                  │                           │
│                                  ▼                           │
│ 5. 审核差异单 ─────────→ 调整库存 / 驳回                    │
│    (approve/reject)       (若approve:                        │
│                           physical += variance;            │
│                           frozen -= variance;              │
│                           if force: 允许负可用)             │
│                                  │                           │
│                                  ▼                           │
│ 6. 生成变更日志 ────────→ 可追溯                            │
│    (InventoryChangeLog)                                     │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. 权限与访问控制

所有盘点相关API都需要用户具备 `inventory_manage` 权限。

```python
# 权限检查装饰器
@permission_required('inventory_manage')
@login_required
def api_endpoint():
    pass
```

---

## 7. 错误处理与异常码

| HTTP 状态码 | 错误信息 | 处理建议 |
|-----------|--------|--------|
| 400 | 范围筛选条件无效 | 检查请求参数 |
| 400 | 实盘数量不能为负 | 检查输入值 |
| 400 | 文件格式不支持 | 使用正确的Excel/CSV格式 |
| 401 | 未授权 | 重新登录 |
| 403 | 权限不足 | 联系管理员分配权限 |
| 404 | 盘点单不存在 | 检查盘点单ID |
| 500 | 调整后物理库存小于锁定与冻结之和，可用数量为负 | 使用强制通过选项或驳回 |

---

## 8. 性能优化建议

- **批量导入**：大文件分批处理，使用后台任务（Celery）
- **差异计算**：使用数据库触发器或ORM hook自动计算，避免重复查询
- **冻结操作**：使用数据库事务确保原子性
- **报表生成**：使用缓存或异步任务生成大型Excel文件
- **查询优化**：为 (count_id, inventory_id)、(count_id, status) 等字段加索引

---

## 9. 示例工作流

### 示例：创建盘点单并生成差异单

```bash
# 1. 创建盘点单
curl -X POST http://localhost:5000/count/create \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "count_type=open_count&scope_type=location&location_ids=1&location_ids=2&plan_date=2025-03-19&remark=定期盘点"

# 2. 录入实盘数量（逐条）
curl -X POST http://localhost:5000/count/detail/1/update_item/1 \
  -H "Content-Type: application/json" \
  -d '{"counted_qty":105,"reason":"发现漏点"}'

# 3. 预览差异
curl -X GET http://localhost:5000/count/detail/1/variance_preview

# 4. 生成差异单
curl -X POST http://localhost:5000/count/detail/1/generate_variances

# 5. 审核通过
curl -X POST http://localhost:5000/count/variances/1/approve \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "force=0"
```

---

## 10. FAQ

**Q: 盘点期间如何处理新的入出库？**  
A: 系统以初始快照为基准计算差异，期间的库存变动不影响差异计算。若期间库存变动较大，可手动刷新快照（提供覆盖确认）。

**Q: 暗盘模式如何实现隐藏库存数据？**  
A: 后端仍正常存储快照，前端在 `detail.html` 中通过 Jinja2 条件判断 `count.count_type` 来选择性隐藏显示。

**Q: 强制通过的意义是什么？**  
A: 允许调整后物理库存 < (锁定+冻结) 的情况（负可用）。需仓库管理员确认，记录在案以便审计。

**Q: 如何处理审核驳回后的重新盘点？**  
A: 驳回会解冻库存，用户需返回盘点单详情页面修改实盘数量后，重新生成差异单。

**Q: 支持多个盘点任务同时进行吗？**  
A: 支持。不同 count_id 的盘点单完全独立，可并行操作。

