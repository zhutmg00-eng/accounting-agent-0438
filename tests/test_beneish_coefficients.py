"""Beneish (1999) 八变量模型系数回归测试：M = -4.84 + 0.920 DSRI + 0.528 GMI + 0.404 AQI
+ 0.892 SGI + 0.115 DEPI - 0.172 SGAI + 4.679 TATA - 0.327 LVGI。"""
import inspect
import re

from src.plugins.audit_fraud_plugin import tools


def test_beneish_coefficients_match_published_model():
    src = inspect.getsource(tools)
    assert re.search(r"\+\s*4\.679\s*\*\s*tata", src)
    assert re.search(r"-\s*0\.327\s*\*\s*lvgi", src)
    assert "4.037" not in src and "0.0327" not in src
