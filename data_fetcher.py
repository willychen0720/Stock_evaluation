# data_fetcher.py (動態12M ＋ 永擎特定數據校正完全體)
from FinMind.data import DataLoader
import pandas as pd
import numpy as np
import datetime
import streamlit as st

@st.cache_data(ttl=3600)
def fetch_stock_financials(ticker: str) -> dict:
    """
    【動態 12M 滾動模型優化版】
    自動感應最新公告季報與月營收進度差，並針對新股(如7711永擎)進行底層欄位清洗與落後還原。
    """
    api = DataLoader()
    today = datetime.date.today()
    today_str = today.strftime('%Y-%m-%d')
    
    try:
        # ---- 1. 抓取今日收盤價 ----
        start_price_date = (today - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
        price_df = api.taiwan_stock_daily(stock_id=ticker, start_date=start_price_date, end_date=today_str)
        if not price_df.empty:
            current_price = float(price_df['close'].iloc[-1])
        else:
            raise ValueError("無法取得即時股價")

        # ---- 2. 抓取綜合損益表 (自動感應最新單季) ----
        fin_start = f"{today.year - 1}-01-01"
        financial_df = api.taiwan_stock_financial_statement(stock_id=ticker, start_date=fin_start, end_date=today_str)
        if financial_df.empty:
            raise ValueError("財報資料庫回傳空值")
            
        financial_df['date'] = pd.to_datetime(financial_df['date'])
        
        eps_all = financial_df[financial_df['type'] == 'EPS'].sort_values('date', ascending=False)
        rev_all = financial_df[financial_df['type'] == 'Revenue'].sort_values('date', ascending=False)
        
        if eps_all.empty or rev_all.empty:
            raise ValueError("損益表關鍵會計科目不完整")
            
        latest_fin_date = eps_all['date'].iloc[0]
        latest_q_eps = float(eps_all['value'].iloc[0])
        
        target_rev_df = rev_all[rev_all['date'] == latest_fin_date]
        latest_q_rev = float(target_rev_df['value'].iloc[0]) / 100000000.0 if not target_rev_df.empty else 50.0
        
        q_end_month = latest_fin_date.month 
        q_label = f"{latest_fin_date.year} Q{q_end_month // 3}"

        # ---- 3. 跨年度月營收動態調配中心 ----
        rev_start = f"{today.year - 2}-01-01"
        rev_df = api.taiwan_stock_month_revenue(stock_id=ticker, start_date=rev_start, end_date=today_str)
        if rev_df.empty:
            raise ValueError("無法取得月營收數據")
            
        rev_df['date'] = pd.to_datetime(rev_df['date'])
        rev_df['year'] = rev_df['date'].dt.year
        rev_df['month'] = rev_df['date'].dt.month
        
        valid_max_month = today.month - 1 if today.year == latest_fin_date.year else 12
        this_year_rev = rev_df[(rev_df['year'] == latest_fin_date.year) & (rev_df['month'] <= valid_max_month)].copy()
        this_year_rev = this_year_rev.sort_values('month')
        
        # 🌟 核心硬核防禦：針對 7711 永擎在 FinMind 資料庫的特殊欄位錯位進行大清洗
        if ticker == "7711":
            # 永擎真實 4 月營收為 16.38 億 (由 1-4月累計 105.29億 減去 Q1 的 88.91億 完美還原)
            gap_months_rev = 16.38
            gap_months_list = [4]
            max_reported_month = 4
            latest_m_yoy = -44  # 真實 4 月 YoY 為 -44.22%
            gap_label_str = "4月 (已啟動經理人基本面精確洗滌校正)"
        else:
            # 常態股的滾動計量邏輯
            api_max_month = this_year_rev['month'].max() if not this_year_rev.empty else q_end_month
            if api_max_month > q_end_month:
                gap_months_df = this_year_rev[(this_year_rev['month'] > q_end_month) & (this_year_rev['month'] <= api_max_month)]
                gap_months_rev = float(gap_months_df['revenue'].sum()) / 100000000.0
                gap_months_list = list(gap_months_df['month'].values)
                max_reported_month = api_max_month
            else:
                gap_months_rev = 0.0
                gap_months_list = []
                max_reported_month = q_end_month
            gap_label_str = ", ".join([f"{m}月" for m in gap_months_list]) if gap_months_list else "無"

# 計算未來 12M 模型中，還剩下幾個月「未知」
        remain_months_count = 12 - 3 - len(gap_months_list)
        start_m = max_reported_month + 1
        
        remain_months_needed = []
        for i in range(remain_months_count):
            m = start_m + i
            y = latest_fin_date.year
            if m > 12:
                m = m - 12
                y = y + 1
            remain_months_needed.append((y, m)) # 儲存目標推算的【今年/明年】月份
            
        last_y_remain_rev = 0.0
        remain_labels = []
        
        # 🌟 法人級新股防禦：先算好當前單月平均營收，作為歷史缺漏時的「最嚴謹替代基期」
        q_avg_rev = latest_q_rev / 3.0 
        
        for y_target, m_target in remain_months_needed:
            y_base = y_target - 1 # 歷史對比基期為前一年
            
            # 前往營收資料庫撈取去年同期的數據
            match = rev_df[(rev_df['year'] == y_base) & (rev_df['month'] == m_target)]
            
            if not match.empty:
                # 情況 A：去年同期有資料，正常加總
                last_y_remain_rev += float(match['revenue'].iloc[0]) / 100000000.0
                remain_labels.append(f"{m_target}月")
            else:
                # 情況 B：新股在去年同期尚未掛牌、無資料（如永擎 5~9 月）
                # 自動啟動安全替代鎖：拿當前最新一季的單月平均營收頂替，確保推算不失真！
                last_y_remain_rev += q_avg_rev
                remain_labels.append(f"{m_target}月(新股遞補)")

        # ---- 4. 最新財報季度的真實營收 YoY ----
        past_q_rev_df = rev_all[rev_all['date'] == (latest_fin_date - pd.DateOffset(years=1))]
        suggested_yoy = 25
        if not past_q_rev_df.empty:
            past_q_rev = float(past_q_rev_df['value'].iloc[0]) / 100000000.0
            if past_q_rev > 0:
                suggested_yoy = int(round(((latest_q_rev - past_q_rev) / past_q_rev) * 100))

        # ---- 5. 最新單月營收 YoY 計算 (非 7711 股票才執行常態運算) ----
        if ticker != "7711":
            latest_m_yoy = 0
            if gap_months_list:
                target_month = gap_months_list[-1]
                m_data = this_year_rev[this_year_rev['month'] == target_month]
                if not m_data.empty:
                    m_rev_2026 = float(m_data['revenue'].iloc[0])
                    past_m_row = rev_df[(rev_df['year'] == (latest_fin_date.year - 1)) & (rev_df['month'] == target_month)]
                    if not past_m_row.empty:
                        m_rev_2025 = float(past_m_row['revenue'].iloc[0])
                        if m_rev_2025 > 0:
                            latest_m_yoy = int(round(((m_rev_2026 - m_rev_2025) / m_rev_2025) * 100))
            else:
                latest_m_yoy = suggested_yoy

        return {
            "current_price": current_price,
            "latest_q_rev": round(latest_q_rev, 2),
            "latest_q_eps": round(latest_q_eps, 2),
            "gap_months_rev": round(gap_months_rev, 2), 
            "last_y_remain_rev": round(last_y_remain_rev, 2),
            "suggested_yoy": max(-50, min(100, suggested_yoy)),
            "latest_m_yoy": latest_m_yoy,  
            "latest_m_label": f"{max_reported_month}月", 
            "q_label": q_label,
            "gap_label": gap_label_str,
            "remain_label": ", ".join(remain_labels),
            "status": f"📊 滾動 12M 數據咬合成功 (基準季: {q_label})"
        }
    
    except Exception as e:
        info = {"current_price": 100.0, "latest_q_rev": 50.0, "latest_q_eps": 1.0, "gap_months_rev": 0.0, "last_y_remain_rev": 150.0, "suggested_yoy": 25, "latest_m_yoy": 0, "latest_m_label": "未知月", "q_label": "未知季", "gap_label": "無", "remain_label": "無"}
        info["status"] = f"⚠️ 啟動防守預設值 (原因: {str(e)})"
        return info

@st.cache_data(ttl=86400)
def auto_compute_pe_intervals(ticker: str) -> tuple:
    api = DataLoader()
    three_years_ago = (datetime.date.today() - datetime.timedelta(days=3*365)).strftime('%Y-%m-%d')
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    try:
        price_df = api.taiwan_stock_daily(stock_id=ticker, start_date=three_years_ago, end_date=today_str)
        financial_df = api.taiwan_stock_financial_statement(stock_id=ticker, start_date=f"{datetime.date.today().year-2}-01-01", end_date=today_str)
        if price_df.empty or financial_df.empty: return 12.0, 18.0
        eps_df = financial_df[financial_df['type'] == 'EPS'].copy()
        if eps_df.empty: return 12.0, 18.0
        eps_df = eps_df.sort_values('date', ascending=False)
        latest_4_quarters_eps = eps_df['value'].head(4).sum()
        if latest_4_quarters_eps <= 0: return 8.0, 12.0
        historical_pes = price_df['close'] / latest_4_quarters_eps
        pe_mean = historical_pes.mean()
        pe_std = historical_pes.std()
        pe_low = max(8.0, pe_mean - (0.8 * pe_std))
        pe_high = pe_mean + (0.8 * pe_std)
        if pe_high > 50 and ticker != "4576": pe_high = 35.0
        return round(pe_low, 1), round(pe_high, 1)
    except Exception as e:
        return 12.0, 18.0