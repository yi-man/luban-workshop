# GLM Coding Plan 产品映射关系

## API调研结果

### 产品ID列表（从API获取）

| API名称 | 产品ID | Tokens | Times | 推测套餐 |
|---------|--------|--------|-------|----------|
| acSuccess | product-005 | 5,000,000 | - | Lite |
| HAI | product-010 | 5,000,000 | - | HAI专用 |
| newUserPurchase | product-003 | 10,000,000 | - | Pro/新用户 |
| CCFold | product-008 | 1,000,000 | - | CCF旧版 |
| Geekbang | product-009 | 8,000,000 | - | 极客时间合作 |
| Dify | product-006 | 10,000,000 | - | Dify合作 |
| CCFnew | product-007 | 1,000,000 | - | CCF新版 |
| register | product-047 | 20,000,000 | 120 | **Max（主要目标）** |

### 关键发现

1. **Max套餐确认**: `product-047` (register) 拥有最高的 2000万 tokens 和 120次调用，对应页面上的