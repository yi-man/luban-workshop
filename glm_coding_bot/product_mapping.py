"""
GLM Coding Plan 产品映射关系

基于 batch-preview API 实际返回数据
API: https://bigmodel.cn/api/biz/pay/batch-preview
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class SubscriptionPeriod(Enum):
    """订阅周期"""
    MONTHLY = "monthly"      # 连续包月
    QUARTERLY = "quarterly"  # 连续包季
    YEARLY = "yearly"        # 连续包年


@dataclass
class ProductInfo:
    """产品信息"""
    product_id: str
    name: str  # Lite/Pro/Max
    period: SubscriptionPeriod  # 订阅周期
    tokens: Optional[int] = None
    times: Optional[int] = None
    original_amount: float = 0.0  # 原价
    discount_amount: float = 0.0  # 折扣价
    pay_amount: float = 0.0  # 实付价
    monthly_original: float = 0.0  # 月均原价
    monthly_pay: float = 0.0  # 月均实付
    sold_out: bool = True  # 是否售罄
    campaign_name: str = ""  # 活动名称（如"连续包季 9 折"）
    renew_amount: float = 0.0  # 续费金额


# ============ 基于 batch-preview API 的真实产品数据 ============

# 产品ID映射（从API获取）
# 格式: (套餐类型, 订阅周期) -> 产品ID
PRODUCT_ID_MAP: Dict[Tuple[str, SubscriptionPeriod], str] = {
    # Lite 套餐
    ("Lite", SubscriptionPeriod.MONTHLY): "product-02434c",    # ¥49/月
    ("Lite", SubscriptionPeriod.QUARTERLY): "product-b8ea38",  # ¥44.1/月 (9折)
    ("Lite", SubscriptionPeriod.YEARLY): "product-70a804",     # ¥39.2/月 (8折)

    # Pro 套餐
    ("Pro", SubscriptionPeriod.MONTHLY): "product-1df3e1",      # ¥149/月
    ("Pro", SubscriptionPeriod.QUARTERLY): "product-fef82f",  # ¥134.1/月 (9折)
    ("Pro", SubscriptionPeriod.YEARLY): "product-5643e6",     # ¥119.2/月 (8折)

    # Max 套餐
    ("Max", SubscriptionPeriod.MONTHLY): "product-2fc421",      # ¥469/月
    ("Max", SubscriptionPeriod.QUARTERLY): "product-5d3a03",  # ¥422.1/月 (9折)
    ("Max", SubscriptionPeriod.YEARLY): "product-d46f8b",     # ¥375.2/月 (8折)
}

# 主力产品列表（用于抢购）
MAIN_PRODUCTS = ["product-02434c", "product-b8ea38", "product-70a804",  # Lite
                 "product-1df3e1", "product-fef82f", "product-5643e6",  # Pro
                 "product-2fc421", "product-5d3a03", "product-d46f8b"]  # Max


# ============ 辅助函数 ============

def get_product_id(package: str, period: SubscriptionPeriod) -> Optional[str]:
    """根据套餐类型和订阅周期获取产品ID"""
    return PRODUCT_ID_MAP.get((package, period))


def get_product_info_from_id(product_id: str) -> Optional[Tuple[str, SubscriptionPeriod]]:
    """根据产品ID获取套餐类型和订阅周期"""
    for (package, period), pid in PRODUCT_ID_MAP.items():
        if pid == product_id:
            return (package, period)
    return None


def list_products_by_package(package: str) -> List[str]:
    """获取指定套餐的所有产品ID"""
    return [pid for (pkg, _), pid in PRODUCT_ID_MAP.items() if pkg == package]


def get_main_product_for_package(package: str, period: SubscriptionPeriod = SubscriptionPeriod.QUARTERLY) -> str:
    """获取指定套餐的主力产品ID（默认连续包季）"""
    product_id = get_product_id(package, period)
    if not product_id:
        # 回退到任意可用产品
        products = list_products_by_package(package)
        return products[0] if products else ""
    return product_id


# 默认抢购目标
DEFAULT_TARGET = {
    "package": "Max",
    "period": SubscriptionPeriod.QUARTERLY,  # 连续包季（默认）
    "product_id": "product-5d3a03"
}


if __name__ == "__main__":
    # 测试
    print("产品映射关系：")
    for package in ["Lite", "Pro", "Max"]:
        print(f"\n{package}:")
        for period in [SubscriptionPeriod.MONTHLY, SubscriptionPeriod.QUARTERLY, SubscriptionPeriod.YEARLY]:
            pid = get_product_id(package, period)
            period_name = {
                SubscriptionPeriod.MONTHLY: "连续包月",
                SubscriptionPeriod.QUARTERLY: "连续包季",
                SubscriptionPeriod.YEARLY: "连续包年",
            }[period]
            print(f"  {period_name}: {pid}")

    print(f"\n默认抢购目标: {DEFAULT_TARGET}")


# 产品详细信息（从API调研获取）
PRODUCT_DETAILS = {
    "product-005": ProductInfo(
        product_id="product-005",
        name="Lite",
        tokens=5_000_000,
        times=None,
        api_name="acSuccess",
        description="轻量级套餐，500万tokens"
    ),
    "product-003": ProductInfo(
        product_id="product-003",
        name="Pro",
        tokens=10_000_000,
        times=None,
        api_name="newUserPurchase",
        description="专业版套餐，1000万tokens"
    ),
    "product-047": ProductInfo(
        product_id="product-047",
        name="Max",
        tokens=20_000_000,
        times=120,
        api_name="register",
        description="旗舰版套餐，2000万tokens+120次调用"
    ),
    "product-010": ProductInfo(
        product_id="product-010",
        name="HAI",
        tokens=5_000_000,
        times=None,
        api_name="HAI",
        description="HAI专用套餐"
    ),
    "product-008": ProductInfo(
        product_id="product-008",
        name="CCFold",
        tokens=1_000_000,
        times=None,
        api_name="CCFold",
        description="CCF旧版套餐"
    ),
    "product-009": ProductInfo(
        product_id="product-009",
        name="Geekbang",
        tokens=8_000_000,
        times=None,
        api_name="Geekbang",
        description="极客时间合作套餐"
    ),
    "product-006": ProductInfo(
        product_id="product-006",
        name="Dify",
        tokens=10_000_000,
        times=None,
        api_name="Dify",
        description="Dify合作套餐"
    ),
    "product-007": ProductInfo(
        product_id="product-007",
        name="CCFnew",
        tokens=1_000_000,
        times=None,
        api_name="CCFnew",
        description="CCF新版套餐"
    ),
}


def get_product_id(name: str) -> Optional[str]:
    """根据名称获取产品ID"""
    return PRODUCT_MAP.get(name)


def get_product_info(product_id: str) -> Optional[ProductInfo]:
    """根据产品ID获取详细信息"""
    return PRODUCT_DETAILS.get(product_id)


def list_products() -> List[ProductInfo]:
    """列出所有产品"""
    return list(PRODUCT_DETAILS.values())


def get_main_products() -> Dict[str, ProductInfo]:
    """获取主力产品（Lite/Pro/Max）"""
    return {
        "Lite": PRODUCT_DETAILS["product-005"],
        "Pro": PRODUCT_DETAILS["product-003"],
        "Max": PRODUCT_DETAILS["product-047"],
    }


# 订阅周期选项
SUBSCRIPTION_PERIODS = {
    "monthly": "连续包月",
    "quarterly": "连续包季",
    "yearly": "连续包年",
}

# 主力产品ID列表
MAIN_PRODUCT_IDS = ["product-005", "product-003", "product-047"]

if __name__ == "__main__":
    # 测试
    print("主力产品：")
    for name, info in get_main_products().items():
        print(f"  {name}: {info.product_id} - {info.tokens} tokens")
