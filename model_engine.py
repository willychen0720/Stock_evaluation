# model_engine.py
import pandas as pd

def run_valuation_core(latest_q_rev, latest_q_eps, gap_months_rev, remain_months_est_rev, pe_low, pe_high):
    """
    底層精確計算公式：滾動 12 個月 (Forward 12M) 估值運算
    """
    if latest_q_rev == 0: return {}
    
    # 1. 最新單季獲利效率 (每億元營收貢獻多少 EPS)
    e_base = latest_q_eps / latest_q_rev
    
    # 2. 未來 12 個月預估總營收 = 最新單季實績 + 季報後已公告月營收 + 剩餘月份預估營收
    f12m_total_rev = latest_q_rev + gap_months_rev + remain_months_est_rev
    
    # 3. 滾動 12 個月 Forward EPS 運算 (Re-rating 已直接反映在預估營收或外部係數中，此處回歸基本面交乘)
    f12m_eps_est = f12m_total_rev * e_base
    
    # 4. 根據全新預估 Forward EPS 計算價值區間
    cheap_price = f12m_eps_est * pe_low
    fair_low = f12m_eps_est * pe_low
    fair_high = f12m_eps_est * pe_high
    hot_price = f12m_eps_est * (pe_high * 1.25) # 過熱給予 25% 溢價
    
    return {
        "e_base": e_base,
        "f12m_total_rev": f12m_total_rev,
        "eps_est": f12m_eps_est,
        "cheap": cheap_price,
        "fair_range": f"{round(fair_low, 1)} ~ {round(fair_high, 1)}",
        "fair_low": fair_low,
        "fair_high": fair_high,
        "hot": hot_price
    }