"""
Management Accounting & CVP (Cost-Volume-Profit) Analysis Tools.
"""

from typing import Dict, Any


def calculate_cvp_break_even(
    unit_price: float,
    unit_variable_cost: float,
    total_fixed_costs: float,
    current_sales_volume: float
) -> Dict[str, Any]:
    """
    Calculate Break-even sales volume, contribution margin, safety margin, and operating leverage.
    """
    unit_cm = unit_price - unit_variable_cost  # 单位边际贡献
    cm_ratio = unit_cm / max(unit_price, 1e-6)  # 边际贡献率
    
    # 盈亏平衡点 (Break-even point)
    be_volume = total_fixed_costs / max(unit_cm, 1e-6)
    be_revenue = be_volume * unit_price
    
    # 当前经营状态
    total_revenue = current_sales_volume * unit_price
    total_var_cost = current_sales_volume * unit_variable_cost
    total_cm = current_sales_volume * unit_cm
    ebit = total_cm - total_fixed_costs  # 息税前利润
    
    # 安全边际 (Margin of Safety)
    safety_margin_volume = current_sales_volume - be_volume
    safety_margin_ratio = safety_margin_volume / max(current_sales_volume, 1e-6)
    
    # 经营杠杆系数 (Degree of Operating Leverage, DOL)
    dol = total_cm / max(ebit, 1e-6)

    return {
        "unit_cm": round(unit_cm, 2),
        "cm_ratio": round(cm_ratio * 100, 2),
        "break_even_volume": round(be_volume, 2),
        "break_even_revenue": round(be_revenue, 2),
        "current_ebit": round(ebit, 2),
        "safety_margin_ratio": round(safety_margin_ratio * 100, 2),
        "operating_leverage_dol": round(dol, 2),
        "is_profitable": ebit > 0,
        "risk_status": "低风险(安全边际充足)" if safety_margin_ratio > 0.3 else ("中风险(需关注固定成本)" if safety_margin_ratio > 0.1 else "高风险(临近或处于亏损区)")
    }
