import pandas as pd

def run_valuation_core(latest_q_rev, latest_q_eps, latest_q_margin, gap_months_rev, remain_months_est_rev, pe_low, pe_high):
    """
    底層精確計算公式：滾動 12 個月 (Forward 12M) 估值運算 (結合毛利率敏感度微調)
    """
    if latest_q_rev == 0 or latest_q_margin == 0:
        return {"eps_est": 0.0, "fair_range": "0 ~ 0", "cheap": 0.0, "hot": 0.0, "fair_high_price": 0.0}
    
    # 1. 基準淨利轉換效率 (每億元營收貢獻多少 EPS) - 這是最穩定的護城河
    e_base = latest_q_eps / latest_q_rev
    
    # 2. 未來 12 個月預估總營收
    f12m_total_rev = latest_q_rev + gap_months_rev + remain_months_est_rev
    
    # 3. 未來 12 個月基準預估 EPS (在毛利率不變的前提下)
    base_f12m_eps = f12m_total_rev * e_base
    
    # (預留未來的微調空間)：
    # 如果未來您在前端 app.py 加了「毛利率預估滑桿 (est_margin)」，
    # 您可以在這裡加入： margin_adjustment_ratio = est_margin / latest_q_margin
    # 然後： f12m_eps_est = base_f12m_eps * margin_adjustment_ratio
    
    # 目前先以穩健的基準值為主，徹底消滅 5000 多倍的暴衝
    f12m_eps_est = base_f12m_eps
    
    # 4. 根據預估 Forward EPS 計算價值區間
    cheap_price = round(f12m_eps_est * pe_low, 1)
    fair_low = round(f12m_eps_est * pe_low, 1)
    fair_high = round(f12m_eps_est * pe_high, 1)
    hot_price = round(f12m_eps_est * pe_high * 1.25, 1)
    
    return {
        "eps_est": round(f12m_eps_est, 2),
        "fair_range": f"{fair_low} ~ {fair_high}",
        "cheap": cheap_price,
        "hot": hot_price,
        "fair_high_price": fair_high
    }
