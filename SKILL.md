---
name: mcd-order-persona
description: Use McDonald's China MCP to recommend three currently purchasable meal combinations from the user's last 90 days of paid orders, stated diner preferences, live menu, and claimed coupons.
---

# 麦麦常点新搭子

当用户希望根据自己的麦当劳历史消费得到套餐和新品推荐时使用。只通过麦当劳中国 MCP 获取订单、门店、菜单、优惠券和实时计价；`src/` 中的工具只处理脱敏后的规范化数据，不访问账号。

## 流程

1. 询问用餐门店或地址、就餐方式、人数、每位用餐者是成人还是儿童，以及口味、忌口或不想吃的食材。性别仅作为用户自选标签，不根据订单推断，也不假设女性或儿童必然偏好某种口味或热量。
2. 调用 `order-list` 获取过去 90 天的订单；按工具提供的分页继续获取。若订单缺实付金额或餐品，调用 `query-order` 补齐。只统计已支付且已完成的点餐订单，排除取消、未支付、全额退款和商城订单。若工具无法覆盖完整 90 天，应说明实际覆盖范围。不要保存原始订单或个人资料到项目目录、日志和公开仓库。
3. 根据地址调用 `query-nearby-stores` 或 `delivery-query-stores`，选定门店后调用 `query-meals`、必要时 `query-meal-detail`。优惠券领取属于账号变更；仅在用户明确要求领券时调用 `auto-bind-coupons`。本 Skill 的推荐请求已明确要求先领取。随后调用 `query-my-coupons` 和 `query-store-coupons` 获取实际可用券。
4. 依据历史常点餐品和用户明确偏好提出至少 6 个不同主餐的候选组合。只从当前门店在售餐品中选。对每个候选组合及适用优惠券调用 `calculate-price`，使用**最终应付金额**判断预算，不用菜单标价或臆测折扣。
5. 将规范化的已完成订单、候选组合的实付报价输入 `src/McdOrderPersona`。预算上限为最近 90 天平均每单实付金额的 125%。若少于 3 个合格方案，换更小组合、其他适用券或门店在售选项重新调用 `calculate-price`，直到得到 3 个不同主餐的合格方案，或已合理尝试仍不足 3 个。不要用超预算方案补足名额。
6. 新品仅在 `query-meals` 的官方新品标签或 `campaign-calendar` 的活动信息可核实时推荐。没有可靠上新信息，就明确说暂无法确认“最新上架”；不要把普通在售餐品冒充新品。新品若作为套餐加购，必须重新计算合计实付并满足预算上限。
7. 输出 90 天有效订单数、实际覆盖时段、平均实付、125% 上限、三套套餐的组成与优惠后实付、使用的券、推荐理由，以及经官方信息确认的新品。金额均显示人民币元。只有在用户另外明确要求下单，并核对门店、餐品、价格与配送信息后，才调用 `create-order`。

## 异常边界

- 少于 3 笔有效历史订单时不把样本均价当作稳定预算，询问用户预算；规范化输入可填写 `userBudgetCents`。
- 订单可能是一家多人合单。历史均价是**每单**金额，不是每人消费。根据本次用餐人数解释这一点，必要时询问用户是否改用自定预算。
- `calculate-price` 的报价、券适用性和库存可能变化。展示时注明核价时间；准备下单前重新计价。
- 若 `auto-bind-coupons`、订单查询或实时报价失败，明确标注缺失信息，不编造优惠或订单历史。

参赛集成和规范化输入格式见 [MCP_INTEGRATION.md](MCP_INTEGRATION.md) 与 [README.md](README.md)。
