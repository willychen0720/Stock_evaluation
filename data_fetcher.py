# data_fetcher.py (動態12M ＋ 數據請求減肥 ＋ 歷史 3 年 TTM 本益比統計引擎完全體)
from FinMind.data import DataLoader
import pandas as pd
import numpy as np
import datetime
import streamlit as st

# 🌟 綁定經理人的官方高頻放寬 Token
MY_FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiV2lsbHljd3k3MjAiLCJlbWFpbCI6IndpbGx5ODc4Nzg3QGhvdG1haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.j0VsZ1DNVFlvOXfFkpAGMDPEs_kLh1tezrNBv3FNfrU"

@st.cache_data(ttl=3600)
def fetch_stock_financials(ticker: str) -> dict:
    api = DataLoader(token=MY_FINMIND_TOKEN)
    today = datetime.date.today()
    today_str = today.strftime('%Y-%m-%d')
    
    try:
        # --- [1] 原始股價抓取邏輯 ---
        start_price_date = (today - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
        price_df = api.taiwan_stock_daily(stock_id=ticker, start_date=start_price_date, end_date=today_str)
        current_price = float(price_df['close'].iloc[-1]) if not price_df.empty else 100.0
        
        # --- [2] 原始財務數據抓取 ---
        fin_start = f"{today.year - 2}-01-01" # 🌟 為了算季 YoY，這裡提早一年抓損益表
        financial_df = api.taiwan_stock_financial_statement(stock_id=ticker, start_date=fin_start, end_date=today_str)
        
        if financial_df.empty: raise ValueError("No Fin Data")
            
        eps_all = financial_df[financial_df['type'] == 'EPS'].sort_values('date')
        if eps_all.empty: raise ValueError("No EPS Data")
        latest_fin = eps_all.iloc[-1]
        
        latest_fin_date = pd.to_datetime(latest_fin['date'])
        
        # 提取最新毛利率 (雙重防禦機制)
        margin_all = financial_df[financial_df['type'] == 'GrossProfitMargin'].sort_values('date')
        if not margin_all.empty:
            latest_margin = float(margin_all.iloc[-1]['value'])
        else:
            gp_all = financial_df[financial_df['type'] == 'GrossProfit'].sort_values('date')
            rev_fin_all_temp = financial_df[financial_df['type'] == 'Revenue'].sort_values('date')
            if not gp_all.empty and not rev_fin_all_temp.empty:
                latest_gp = float(gp_all.iloc[-1]['value'])
                latest_rev_q = float(rev_fin_all_temp.iloc[-1]['value'])
                latest_margin = (latest_gp / latest_rev_q) * 100 if latest_rev_q != 0 else 25.0
            else:
                latest_margin = 25.0

        # --- [3] 營業收入數據抓取與計算 ---
        # 抓取季報的營收
        rev_fin_all = financial_df[financial_df['type'] == 'Revenue'].sort_values('date')
        latest_q_rev_calculated = float(rev_fin_all.iloc[-1]['value']) / 100000000.0 if not rev_fin_all.empty else 0.0

        # 🌟 修復核心：計算真正的「季營收 YoY (suggested_yoy)」
        suggested_yoy_calculated = 25 # 預設值
        if not rev_fin_all.empty and len(rev_fin_all) >= 5:
            # 找到去年同期的財報日期 (往前回推一年)
            last_year_date = latest_fin_date - pd.DateOffset(years=1)
            # 在資料庫中尋找是否有這天的紀錄
            past_q_rev_df = rev_fin_all[pd.to_datetime(rev_fin_all['date']) == last_year_date]
            if not past_q_rev_df.empty:
                past_q_rev = float(past_q_rev_df.iloc[0]['value']) / 100000000.0
                if past_q_rev > 0:
                    suggested_yoy_calculated = int(round(((latest_q_rev_calculated - past_q_rev) / past_q_rev) * 100))

        # 月營收抓取與跨年度對齊
        rev_start = f"{today.year - 2}-01-01"
        rev_df = api.taiwan_stock_month_revenue(stock_id=ticker, start_date=rev_start, end_date=today_str)
        
        gap_months_rev_calculated = 0.0
        last_y_remain_rev_calculated = 0.0
        gap_label_str = "無"
        remain_label_str = "未來月份"
        latest_m_label_str = "最新月"
        latest_m_yoy_calculated = 0

        if not rev_df.empty:
            rev_df['date'] = pd.to_datetime(rev_df['date'])
            rev_df['correct_date'] = rev_df['date'] - pd.DateOffset(months=1)
            rev_df['year'] = rev_df['correct_date'].dt.year
            rev_df['month'] = rev_df['correct_date'].dt.month
            
            q_end_month = latest_fin_date.month
            valid_max_month = today.month - 1 if today.year == latest_fin_date.year else 12
            
            this_year_rev = rev_df[(rev_df['year'] == latest_fin_date.year) & (rev_df['month'] <= valid_max_month)].sort_values('month')
            max_reported_month = this_year_rev['month'].max() if not this_year_rev.empty else q_end_month
            
            if max_reported_month > q_end_month:
                gap_months_df = this_year_rev[(this_year_rev['month'] > q_end_month) & (this_year_rev['month'] <= max_reported_month)]
                gap_months_rev_calculated = float(gap_months_df['revenue'].sum()) / 100000000.0
                gap_label_str = ", ".join([f"{m}月" for m in gap_months_df['month'].values])
            else:
                max_reported_month = q_end_month
                
            remain_months_count = 12 - 3 - (max_reported_month - q_end_month)
            start_m = max_reported_month + 1
            
            remain_labels = []
            for i in range(remain_months_count):
                m_target = start_m + i
                y_target = latest_fin_date.year
                if m_target > 12:
                    m_target -= 12
                    y_target += 1
                
                y_base = y_target - 1
                match = rev_df[(rev_df['year'] == y_base) & (rev_df['month'] == m_target)]
                if not match.empty:
                    last_y_remain_rev_calculated += float(match['revenue'].iloc[0]) / 100000000.0
                    remain_labels.append(f"{m_target}月")
            
            remain_label_str = ", ".join(remain_labels) if remain_labels else "無"
            
            # 計算最新的單月 YoY
            if max_reported_month > q_end_month:
                m_data = this_year_rev[this_year_rev['month'] == max_reported_month]
                past_m_row = rev_df[(rev_df['year'] == (latest_fin_date.year - 1)) & (rev_df['month'] == max_reported_month)]
                if not m_data.empty and not past_m_row.empty:
                    m_rev_2026 = float(m_data['revenue'].iloc[0]) / 100000000.0
                    m_rev_2025 = float(past_m_row['revenue'].iloc[0]) / 100000000.0
                    if m_rev_2025 > 0:
                        latest_m_yoy_calculated = int(round(((m_rev_2026 - m_rev_2025) / m_rev_2025) * 100))
            latest_m_label_str = f"{max_reported_month}月"

        return {
            "current_price": current_price,
            "latest_q_eps": float(latest_fin['value']),
            "latest_q_margin": latest_margin,
            "latest_q_rev": round(latest_q_rev_calculated, 2),
            "gap_months_rev": round(gap_months_rev_calculated, 2),
            "last_y_remain_rev": round(last_y_remain_rev_calculated, 2),
            "suggested_yoy": max(-50, min(100, suggested_yoy_calculated)), # 🌟 季營收 YoY
            "q_label": f"{latest_fin_date.year} Q{(latest_fin_date.month-1)//3 + 1}",
            "gap_label": gap_label_str,
            "remain_label": remain_label_str,
            "latest_m_label": latest_m_label_str,
            "latest_m_yoy": latest_m_yoy_calculated # 🌟 月營收 YoY (已拆分)
        }
    except Exception as e:
        print(f"⚠️ fetch_stock_financials 內部報錯 ({ticker}): {e}")
        return {"current_price": 100.0, "latest_q_eps": 1.0, "latest_q_margin": 25.0, "latest_q_rev": 50.0, "gap_months_rev": 0.0, "last_y_remain_rev": 150.0, "suggested_yoy": 25, "q_label": "讀取失敗", "gap_label": "無", "remain_label": "無", "latest_m_label": "未知月", "latest_m_yoy": 0}

@st.cache_data(ttl=86400)
def auto_compute_pe_intervals(ticker: str) -> tuple:
    api = DataLoader(token=MY_FINMIND_TOKEN)
    three_years_ago = (datetime.date.today() - datetime.timedelta(days=3*365)).strftime('%Y-%m-%d')
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    
    try:
        price_df = api.taiwan_stock_daily(stock_id=ticker, start_date=three_years_ago, end_date=today_str)
        financial_df = api.taiwan_stock_financial_statement(stock_id=ticker, start_date=f"{datetime.date.today().year-4}-01-01", end_date=today_str)
        
        if price_df.empty or financial_df.empty: return 12.0, 18.0
        
        eps_df = financial_df[financial_df['type'] == 'EPS'].copy()
        if eps_df.empty: return 12.0, 18.0
        
        eps_df['date'] = pd.to_datetime(eps_df['date'])
        eps_df = eps_df.sort_values('date')
        
        eps_df['ttm_eps'] = eps_df['value'].rolling(window=4, min_periods=4).sum()
        eps_df = eps_df.dropna(subset=['ttm_eps'])
        
        eps_df['date'] = pd.to_datetime(eps_df['date'])
        eps_df = eps_df.sort_values('date')
        
        price_df['date'] = pd.to_datetime(price_df['date'])
        price_df = price_df.sort_values('date')
        
        merged_df = pd.merge_asof(price_df, eps_df, on='date', direction='backward')
        
        merged_df['PE'] = merged_df['close'] / merged_df['ttm_eps']
        
        merged_df = merged_df[(merged_df['PE'] > 3) & (merged_df['PE'] < 60)].dropna()
        
        if merged_df.empty: return 12.0, 18.0
        
        pe_mean = merged_df['PE'].mean()
        pe_std = merged_df['PE'].std()
        
        pe_low = round(max(5.0, pe_mean - 1.0 * pe_std), 1)
        pe_high = round(min(50.0, pe_mean + 1.0 * pe_std), 1)
        
        if pe_low >= pe_high:
            pe_low = round(max(5.0, pe_mean * 0.8), 1)
            pe_high = round(min(50.0, pe_mean * 1.2), 1)
            
        return pe_low, pe_high
    except:
        return 12.0, 18.0
