from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class CustomsDeclaration:
    # ── 买卖双方信息 ──
    seller_name_address: str = ""
    """发货人/出口商名称与地址 (Seller/Exporter)"""
    buyer_name_address: str = ""
    """收货人/进口商名称与地址 (Buyer/Consignee)"""

    # ── 商品信息 ──
    goods_description: str = ""
    """商品名称及规格型号"""
    hs_code: str = ""
    """HS编码 (至少前6位)"""
    quantity: float = 0.0
    """数量"""
    unit: str = ""
    """计量单位 (件、千克、升等)"""
    unit_price: float = 0.0
    """单价"""
    total_amount: float = 0.0
    """总价 (单价 × 数量)"""
    currency: str = "USD"
    """币种 (USD、EUR、CNY等)"""
    incoterms: str = ""
    """贸易术语 (FOB、CIF、CFR、EXW等)"""
    gross_weight: float = 0.0
    """毛重 (千克)"""
    net_weight: float = 0.0
    """净重 (千克)"""
    packaging: str = ""
    """包装件数及包装方式 (如20 pallets、100 cartons)"""

    # ── 价格与费用信息 ──
    total_contract_value: float = 0.0
    """成交总价"""
    freight: float = 0.0
    """运费 (CIF/CFR等条款下)"""
    insurance: float = 0.0
    """保险费 (CIF条款下)"""
    other_fees: float = 0.0
    """其他费用 (佣金、折扣、装卸费等)"""

    # ── 运输与装运信息 ──
    port_of_loading: str = ""
    """起运港"""
    port_of_discharge: str = ""
    """目的港"""
    transport_mode: str = ""
    """运输方式 (海运、空运、陆运、铁路)"""
    vessel_name: str = ""
    """运输工具名称/船名航次"""
    shipping_date: Optional[str] = None
    """装运日期或预计到港日期"""
    bl_awb_no: str = ""
    """提单/运单号 (B/L or AWB No.)"""

    # ── 其他重要信息 ──
    contract_po_no: str = ""
    """合同/订单号"""
    country_of_origin: str = ""
    """原产地国"""
    country_of_export: str = ""
    """出口国"""
    payment_terms: str = ""
    """支付条款 (T/T、L/C、D/P等)"""
    marks_numbers: str = ""
    """唛头 (Marks & Nos.)"""
    remarks: str = ""
    """声明/备注"""

    def to_dict(self) -> dict:
        """转为字典，便于序列化 (如存入区块链交易)"""
        return asdict(self)

    def to_str(self) -> str:
        """格式化为可读的报关单字符串"""
        lines = [
            "═" * 60,
            "              CUSTOMS DECLARATION / 报关单",
            "═" * 60,
            "",
            "── 买卖双方信息 ──",
            f"  Seller/Exporter : {self.seller_name_address}",
            f"  Buyer/Consignee : {self.buyer_name_address}",
            "",
            "── 商品信息 ──",
            f"  Description     : {self.goods_description}",
            f"  HS Code         : {self.hs_code}",
            f"  Quantity        : {self.quantity} {self.unit}",
            f"  Unit Price      : {self.currency} {self.unit_price}",
            f"  Total Amount    : {self.currency} {self.total_amount}",
            f"  Incoterms       : {self.incoterms}",
            f"  Gross Weight    : {self.gross_weight} kg",
            f"  Net Weight      : {self.net_weight} kg",
            f"  Packaging       : {self.packaging}",
            "",
            "── 价格与费用 ──",
            f"  Contract Value  : {self.currency} {self.total_contract_value}",
            f"  Freight         : {self.currency} {self.freight}",
            f"  Insurance       : {self.currency} {self.insurance}",
            f"  Other Fees      : {self.currency} {self.other_fees}",
            "",
            "── 运输信息 ──",
            f"  Port of Loading  : {self.port_of_loading}",
            f"  Port of Discharge: {self.port_of_discharge}",
            f"  Transport Mode   : {self.transport_mode}",
            f"  Vessel/Voyage    : {self.vessel_name}",
            f"  Shipping Date    : {self.shipping_date or 'N/A'}",
            f"  B/L or AWB No.   : {self.bl_awb_no}",
            "",
            "── 其他 ──",
            f"  Contract/PO No.  : {self.contract_po_no}",
            f"  Country of Origin: {self.country_of_origin}",
            f"  Country of Export: {self.country_of_export}",
            f"  Payment Terms    : {self.payment_terms}",
            f"  Marks & Nos.     : {self.marks_numbers}",
            f"  Remarks          : {self.remarks}",
            "",
            "═" * 60,
        ]
        return "\n".join(lines)

    def __str__(self):
        return self.to_str()
