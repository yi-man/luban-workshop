"""GLM Coding Plan 产品映射关系

基于 batch-preview API 实际返回数据
API: https://bigmodel.cn/api/biz/pay/batch-preview
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple


class SubscriptionPeriod(Enum):
    """订阅周期"""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


@dataclass
class ProductInfo:
    """产品信息"""
    product_id: str
    name: str
    period: SubscriptionPeriod
    original_amount: float = 0.0
    discount_amount: float = 0.0
    pay_amount: float = 0.0
    monthly_original: float = 0.0
    monthly_pay: float = 0.0
    sold_out: bool = True
    campaign_name: str = ""
    renew_amount: float = 0.0


# 产品ID映射（从API获取）
PRODUCT_ID_MAP: Dict[Tuple[str, SubscriptionPeriod], str] = {
    ("Lite", SubscriptionPeriod.MONTHLY): "product-02434c",
    ("Lite", SubscriptionPeriod.QUARTERLY): "product-b8ea38",
    ("Lite", SubscriptionPeriod.YEARLY): "product-70a804",

    ("Pro", SubscriptionPeriod.MONTHLY): "product-1df3e1",
    ("Pro", SubscriptionPeriod.QUARTERLY): "product-fef82f",
    ("Pro", SubscriptionPeriod.YEARLY): "product-5643e6",

    ("Max", SubscriptionPeriod.MONTHLY): "product-2fc421",
    ("Max", SubscriptionPeriod.QUARTERLY): "product-5d3a03",
    ("Max", SubscriptionPeriod.YEARLY): "product-d46f8b",
}


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


def get_main_product_for_package(
    package: str,
    period: SubscriptionPeriod = SubscriptionPeriod.QUARTERLY,
) -> str:
    """获取指定套餐的主力产品ID（默认连续包季）"""
    product_id = get_product_id(package, period)
    if not product_id:
        products = list_products_by_package(package)
        return products[0] if products else ""
    return product_id


DEFAULT_TARGET = {
    "package": "Max",
    "period": SubscriptionPeriod.QUARTERLY,
    "product_id": "product-5d3a03",
}
