# 麦当劳 MCP 集成

服务端：麦当劳中国 MCP Server（`https://mcp.mcd.cn`）。客户端通过用户自己的 Token 连接；Token 仅存于客户端安全配置或环境变量。本文不包含真实 Token、账号或订单。

## 实际调用链

| 阶段 | MCP Tool | 使用结果 |
|---|---|---|
| 历史消费 | `order-list`、必要时 `query-order` | 收集近 90 天订单时间、状态、实付与餐品；过滤取消、未支付、退款订单 |
| 门店 | `query-nearby-stores` 或 `delivery-query-stores` | 确认本次可用门店和就餐方式 |
| 当前商品 | `query-meals`、必要时 `query-meal-detail` | 仅从当前门店可售餐品构造候选；读取可靠的新品标签 |
| 领券与查券 | `auto-bind-coupons`、`query-my-coupons`、`query-store-coupons` | 先领取、后确认适用券；领券需用户明确要求 |
| 实际计价 | `calculate-price` | 为每个套餐和适用券取得最终应付金额；超预算则换方案重新计算 |
| 可选活动新品 | `campaign-calendar` | 补充有日期依据的活动信息，不能代替菜单可售性 |
| 用户另行确认后 | `create-order`、`query-order` | 仅在明确要求购买时创建并追踪订单 |

Skill 在客户端真实调用以上 MCP 工具。离线 .NET 程序只复核统计和筛选；它不能伪造 MCP 响应，也不能代替真实连接。演示时应展示一次实时调用链，并在 README 中记录使用的工具和结果截图，注意遮盖手机号、地址、订单号及 Token。

## 规范化输入

MCP 返回的字段名称和分页结构以实际响应为准。Skill 从实际结果提取下列最小字段，再传给离线筛选程序：

```json
{
  "asOf": "2026-10-23T12:00:00+08:00",
  "orders": [
    { "id": "redacted-1", "createdAt": "2026-10-01T12:00:00+08:00", "status": "completed", "paidCents": 3200, "itemCodes": ["SKU_A"] }
  ],
  "candidates": [
    { "id": "combo-a", "name": "门店在售组合 A", "mainCode": "SKU_A", "payableCents": 3500, "couponName": "官方券", "fitScore": 80, "available": true }
  ]
}
```

`status` 统一为 `completed` 后才能参与统计。`paidCents` 和 `payableCents` 必须是 MCP 返回实付、计价结果换算的整数分。`fitScore`（0–100）是 Skill 按用户**明确偏好**和常点餐品给出的候选排序值，不应按性别推断。若历史有效订单少于 3 笔，先询问预算，再填 `userBudgetCents`。候选不足 3 个时继续从门店菜单取不同主餐并调用 `calculate-price`。

## 业务价值与限制

相较于仅看菜单标价的推荐，此 Skill 将用户历史消费、当前门店可售状态、可用券和官方计价形成闭环。`order-list` 被官方描述为查询近期订单，是否覆盖完整 90 天须以实际分页结果核实；不足时向用户说明覆盖范围。新品也仅能在官方菜单标签或活动信息可验证时标注。
