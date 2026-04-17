# Agent Trade Kit - Skills

本目录包含所有交易相关的AI Skills。

## 目录结构

```
skills/
├── gold-grid-arbitrage.md    # 黄金网格套利策略
└── README.md                 # 本文件
```

## Skills 列表

### 1. 黄金网格套利 (gold-grid-arbitrage)

**功能**：针对XAU-USDT-SWAP(黄金合约)的自动化网格交易和套利策略

**核心特性**：
- 5维度AI综合判断(价格位置/趋势/波动率/情绪/成交量)
- 6档网格委托
- 完整风控(仓位/资金/熔断)
- 止盈止损自动设置

**使用场景**：
- 黄金合约交易
- 网格套利
- 震荡行情交易

**详细文档**：[gold-grid-arbitrage.md](./gold-grid-arbitrage.md)

---

## 如何添加新Skill

1. 在 `skills/` 目录下创建 `.md` 文件
2. 参考现有Skill格式
3. 提交PR到仓库

## 依赖

- OKX CLI (`okx`)
- OpenClaw Framework

## 许可证

MIT License
