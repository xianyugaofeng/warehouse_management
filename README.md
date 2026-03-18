# 基于flask的仓库管理系统


# 仓库管理系统

基于Flask的仓库管理系统，实现了商品管理、采购管理、入库管理、出库管理、库存管理、退货管理等功能。

## 退货管理模块

### 功能特点
- 退货单创建：支持创建退货单，包含退货单号、退货日期、退货原因等信息
- 退货单查询：支持按单号、日期等条件筛选退货单
- 退货明细管理：支持添加多条退货明细，记录商品编码、商品名称、退货数量、单价、退货金额等信息
- 业务规则：仅允许对不合格商品进行退货操作，退货操作仅限于暂存区库存
- 库存更新：退货操作完成后自动更新暂存区库存数量

### 技术实现
- 数据模型：使用SQLAlchemy ORM，定义了ReturnOrder和ReturnItem两个模型
- 视图功能：实现了退货单的创建、查询和查看功能
- 模板页面：提供了直观的退货单创建表单、清晰的退货单列表页面和完整的退货单详情页面
- 测试用例：包含了退货单的创建、查询和关系测试

### 数据库迁移

1. 初始化数据库迁移（如果尚未初始化）：
   ```
   flask db init
   ```

2. 生成迁移文件：
   ```
   flask db migrate -m "添加退货管理模块"
   ```

3. 执行迁移：
   ```
   flask db upgrade
   ```

### 访问路径
- 退货单列表：`/return/list`
- 创建退货单：`/return/add`
- 退货单详情：`/return/detail/<order_id>`

#### 软件架构
软件架构说明


#### 安装教程

1.  xxxx
2.  xxxx
3.  xxxx

#### 使用说明

1.  xxxx
2.  xxxx
3.  xxxx

#### 参与贡献

1.  Fork 本仓库
2.  新建 Feat_xxx 分支
3.  提交代码
4.  新建 Pull Request


#### 特技

1.  使用 Readme\_XXX.md 来支持不同的语言，例如 Readme\_en.md, Readme\_zh.md
2.  Gitee 官方博客 [blog.gitee.com](https://blog.gitee.com)
3.  你可以 [https://gitee.com/explore](https://gitee.com/explore) 这个地址来了解 Gitee 上的优秀开源项目
4.  [GVP](https://gitee.com/gvp) 全称是 Gitee 最有价值开源项目，是综合评定出的优秀开源项目
5.  Gitee 官方提供的使用手册 [https://gitee.com/help](https://gitee.com/help)
6.  Gitee 封面人物是一档用来展示 Gitee 会员风采的栏目 [https://gitee.com/gitee-stars/](https://gitee.com/gitee-stars/)
