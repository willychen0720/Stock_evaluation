# app.py (內建無縫調度 ＋ 雲端風控刷新完全體)
import streamlit as st
import pandas as pd
import os
from model_engine import run_valuation_core
from data_fetcher import fetch_stock_financials
# 🌟 核心優化：直接引入重構後的內建歷史 PE 大數據計算核心
from batch_update_pe import run_batch_update, run_targeted_update

# 頁面初始化配置
st.set_page_config(layout="wide", page_title="經理人價值管理系統", page_icon="📊")
st.title("📊 專業經理人價值管理系統 (Forward 12M 滾動預測版)")

csv_filename = "stock_list.csv"

# ---- 步驟 4-1：讀取自選股清單 ----
if os.path.exists(csv_filename):
    stocks_df = pd.read_csv(csv_filename, encoding="utf-8-sig")
else:
    stocks_df = pd.DataFrame(columns=['ticker', 'name', 'pe_low', 'pe_high'])
    stocks_df.to_csv(csv_filename, index=False, encoding="utf-8-sig")

# ---- 步驟 4-2：側邊欄控制（Sidebar）----
st.sidebar.header("⚙️ 模型參數風控鎖")

if not stocks_df.empty:
    selected_ticker = st.sidebar.selectbox("選擇分析標的", stocks_df['ticker'].astype(str) + " " + stocks_df['name'])
    ticker_id = selected_ticker.split()[0]
    stock_info = stocks_df[stocks_df['ticker'] == int(ticker_id)].iloc[0]
    
    # 動態抓取該股即時數據
    data = fetch_stock_financials(ticker_id)
    st.sidebar.caption(f"📅 數據狀態：{data.get('status', '未知')}")
else:
    st.sidebar.warning("目前資料庫無自選股，請先於下方新增股票。")
    data = {"latest_q_eps": 0.0, "latest_q_rev": 0.0, "gap_months_rev": 0.0, "last_y_remain_rev": 0.0, "current_price": 0.0, "suggested_yoy": 25, "q_label": "Q1", "gap_label": "無", "remain_label": "無"}
    stock_info = {"pe_low": 12.0, "pe_high": 18.0}

st.markdown("---")

# 讀取後台動態算出來的最新財報季度 YoY 實績
default_yoy = int(data.get("suggested_yoy", 25))
q_label = data.get("q_label", "最新季")
gap_label = data.get("gap_label", "無")
remain_label = data.get("remain_label", "未來月份")

yoy_slider = st.sidebar.slider(
    f"🔮 未來未知月份營收 YoY (%) [{q_label}實績: {default_yoy}%]", 
    min_value=-50, 
    max_value=100, 
    value=default_yoy,  
    step=5
) / 100

# 核心安全機制：Re-rating 切換開關
enable_rerating = st.sidebar.toggle("⚠️ 啟動高階 AI / 產能爆發 Re-rating 修正", value=False)
alpha_value = st.sidebar.slider("Re-rating 修正係數 (α)", min_value=1.00, max_value=1.50, value=1.15, step=0.05) if enable_rerating else 1.00

# Re-rating 級距指引
with st.sidebar.expander("📘 Re-rating 級距風控定錨指引", expanded=enable_rerating):
    st.markdown("""
    | 修正係數 $\\alpha$ | 適用產業 / 財務質變指標 |
    | :--- | :--- |
    | **1.00x** | **維持現狀**：傳統硬體代工、成熟製程個股。 |
    | **1.05x ~ 1.10x** | **客戶拓展**：切入新供應鏈、毛利率連兩季小拉。 |
    | **1.15x ~ 1.25x** | **結構性紅利 (如南電、日月光)**：高階 AI 載板、先進封裝、Starlink 核心鏈、財報雙重跳升。 |
    | **1.30x ~ 1.50x** | **市場壟斷 (如德律、大銀微)**：先進製程設備大週期、技術極高專利壁壘。 |
    """)

if not stocks_df.empty:
    st.sidebar.info(f"📊 當前資料庫歷史 PE 參考：\n- 防守低標: {stock_info['pe_low']}x\n- 合理高標: {stock_info['pe_high']}x")

# ---- 步驟 4-3：主畫面數據核實與手動微調（加入動態 key 強制刷新暫存） ----
st.markdown(f"### 📑 滾動 12M 核實基底資料 ── 分析標的歷史季度：`{q_label}`")

# 最頂層動態趨勢看板
latest_m_label = data.get("latest_m_label", "最新月")
latest_m_yoy = data.get("latest_m_yoy", 0)

m1, m2 = st.columns(2)
with m1:
    st.metric(
        label=f"📈 最新季度實績營收 YoY ({q_label})", 
        value=f"{default_yoy} %", 
        delta=f"{default_yoy}%"
    )
with m2:
    st.metric(
        label=f"📅 最新單月實績營收 YoY ({latest_m_label})", 
        value=f"{latest_m_yoy} %", 
        delta=f"{latest_m_yoy}%"
    )

st.markdown(" ") 

col1, col2, col3 = st.columns(3)
with col1:
    # 🌟 關鍵優化：加上 key=f"eps_{ticker_id}"，當換股票時強制刷新，絕不殘留舊數據
    q1_eps_input = st.number_input(f"當季 ({q_label}) 實際單季 EPS", value=float(data['latest_q_eps']), format="%.2f", key=f"eps_{ticker_id}")
    q1_rev_input = st.number_input(f"當季 ({q_label}) 單季營收 (億)", value=float(data['latest_q_rev']), format="%.2f", key=f"q_rev_{ticker_id}")
with col2:
    # 🌟 關鍵優化：加上 key=f"gap_{ticker_id}"，當永擎算出來是 0.0 時，欄位會立刻被強制清空歸零！
    m4_rev_input = st.number_input(f"季報後已公告月營收 (億) ── 已納入: {gap_label}", value=float(data['gap_months_rev']), format="%.2f", key=f"gap_{ticker_id}")
    
    remain_base_rev = float(data['last_y_remain_rev'])
    remain_est_rev = remain_base_rev * (1 + yoy_slider) * alpha_value
    st.number_input(f"未知月份歷史基期總營收 (億) ── 對應: {remain_label}", value=remain_base_rev, format="%.2f", disabled=True, key=f"rem_{ticker_id}")
with col3:
    market_price = st.number_input("今日市場收盤價", value=float(data['current_price']), format="%.2f", key=f"price_{ticker_id}")

# ---- 步驟 4-4：執行核心模型計算 ----
res = run_valuation_core(
    latest_q_rev=q1_rev_input, latest_q_eps=q1_eps_input, 
    gap_months_rev=m4_rev_input, remain_months_est_rev=remain_est_rev,
    pe_low=stock_info['pe_low'], pe_high=stock_info['pe_high']
)

# ---- 步驟 4-5：UI 狀態燈號顯示與極端估值警示 (加入非理性繁榮情緒溢價面板) ----
if res:
    st.markdown("---")
    st.markdown("### 📈 Forward 12M 模型推算與滾動價值區間")
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    col_m1.metric("今日最新收盤價", f"{market_price} 元")
    col_m2.metric("Forward 12M 預估總 EPS", f"{round(res['eps_est'], 2)} 元")
    col_m3.metric("領先半年合理價值區間", res['fair_range'])
    
    pe_dynamic = round(market_price / res['eps_est'], 2) if res['eps_est'] != 0 else 0.0
    col_m4.metric("動態 Forward 12M PE", f"{pe_dynamic} 倍")

    # 🌟 核心增強：計算與列出「非理性繁榮情緒溢價」風控指標
    pe_high_base = float(stock_info['pe_high'])
    irrational_pe_ceiling = round(pe_high_base * 1.25 * alpha_value, 2) # 歷史高標 x 1.25 x Re-rating
    
    # 計算目前市價高出「常態合理高標價值」的超額交易溢價比例
    fair_high_price = res.get('fair_high_price', res['eps_est'] * pe_high_base * alpha_value) # 抓取合理區間頂部
    overpriced_pct = int(round(((market_price - fair_high_price) / fair_high_price) * 100)) if fair_high_price > 0 else 0

    # 建立一個專門的情緒溢價監控儀表板
    st.markdown("#### 🧠 經理人風控監控：非理性繁榮情緒溢價指標")
    v1, v2, v3 = st.columns(3)
    with v1:
        st.metric(
            label="📊 歷史常態合理高標 PE", 
            value=f"{pe_high_base} 倍",
            help="過去 3 年大數據去雜訊後，法人認同的常態交易評價天花板。"
        )
    with v2:
        st.metric(
            label="🔥 非理性繁榮情緒溢價 PE 天花板", 
            value=f"{irrational_pe_ceiling} 倍",
            delta=f"+25% 情緒溢價",
            delta_color="inverse", # 讓紅色代表本益比墊高的高風險
            help="考慮到歷史最高評價再加價 25% 的極端追價情緒天花板（若開啟 Re-rating 則已包含 α 修正效應）。"
        )
    with v3:
        if overpriced_pct > 0:
            st.metric(
                label="⚠️ 當前市價超額交易（溢價）", 
                value=f"{overpriced_pct} %",
                delta="超越歷史合理高標",
                delta_color="inverse"
            )
        else:
            st.metric(
                label="🛡️ 當前市價安全邊際（折價）", 
                value=f"{abs(overpriced_pct)} %",
                delta="低於歷史合理高標",
                delta_color="normal"
            )

    st.markdown(" ") # 留白保持 Scannable

    # 原本的過熱/安全燈號警告
    if market_price > res['hot']:
        st.error(f"🔴 嚴重過熱：目前市價突破未來 12M 過熱防線 ({res['hot']}元)！當前動態本益比 {pe_dynamic} 倍，已超前交易過多未來預期。")
    elif market_price < res['cheap']:
        st.success(f"🟢 價值顯現：目前股價低於 Forward 12M 保守安全防線 ({res['cheap']}元)，具備極高安全邊際。")
    else:
        st.info("🟡 股價正於未來 12M 基本面合理區間內震盪。")

# ---- ⚙️ 資料庫維護區 ───-
st.sidebar.markdown("---")
st.sidebar.subheader("🗄️ 資料庫維護")

with st.sidebar.expander("➕ 在外臨時新增股票", expanded=False):
    new_ticker = st.text_input("輸入股票代號 (如 2330)", key="new_ticker_input").strip()
    new_name = st.text_input("輸入股票名稱 (如 台積電)", key="new_name_input").strip()
    
    if st.button("確認新增至清單"):
        if new_ticker and new_name:
            if int(new_ticker) in stocks_df['ticker'].values:
                st.warning(f"⚠️ 代號 {new_ticker} 已存在於清單中！")
            else:
                new_row = pd.DataFrame([{"ticker": int(new_ticker), "name": new_name, "pe_low": 0.0, "pe_high": 0.0}])
                new_row.to_csv(csv_filename, mode='a', header=False, index=False, encoding="utf-8-sig")
                st.success(f"✅ {new_ticker} {new_name} 已臨時寫入雲端暫存！")
                st.rerun()

# 📱 按鈕 A：在外行動專用 ── 輕量化精準局部更新（省流量、速度極快）
if st.sidebar.button("🎯 僅更新全新標的 PE (行動推薦)"):
    with st.sidebar.status("正在精準定錨新股票大數據...", expanded=True) as status:
        ret_msg = run_targeted_update()
        status.update(label=ret_msg, state="complete")
    st.rerun()

# 💻 按鈕 B：全域大洗牌 ── 適合在家、在公司用固網維護
if st.sidebar.button("🔄 一鍵滾動更新歷史 PE (全清單)"):
    with st.sidebar.status("正在動態計算全資料庫 3 年大數據...", expanded=True) as status:
        ret_msg = run_batch_update()
        status.update(label=ret_msg, state="complete")
    st.rerun()

# 🌟 核心優化：徹底揮別 subprocess，改用原生內建函數執行大數據調度
if st.sidebar.button("🔄 一鍵滾動更新歷史 PE 區間"):
    with st.sidebar.status("正在動態計算歷史 3 年大數據...", expanded=True) as status:
        # 直接調用同一個 Python 沙盒環境下的核心邏輯，100% 免疫雲端作業系統環境衝突
        ret_msg = run_batch_update()
        status.update(label=ret_msg, state="complete")
    
    # 🌟 關鍵絕殺：強制網頁徹底重整，重新讀取 CSV，讓 0.0 的估值防線瞬間在畫面上被精確數字取代！
    st.rerun()
