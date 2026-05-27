# app.py (靜態快取秒開 ＋ 降維紅字顯影選單 ＋ 7大看板與公式透明化完全體)
import streamlit as st
import pandas as pd
import os
import re # 引入正則表達式，用於動態拆解 Re-rating default 值
from model_engine import run_valuation_core
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
    stocks_df = pd.DataFrame(columns=['ticker', 'name', 'pe_low', 'pe_high', '稼動率調整值評估', '今年法人預估EPS均值'])
    stocks_df.to_csv(csv_filename, index=False, encoding="utf-8-sig")

# 📊 確保 DataFrame 欄位安全平滑機制
if '稼動率調整值評估' not in stocks_df.columns:
    stocks_df['稼動率調整值評估'] = "1.00x (維持現狀：傳統個股)"
if '今年法人預估EPS均值' not in stocks_df.columns:
    stocks_df['今年法人預估EPS均值'] = 0.0

# ---- 🌟 核心優化：利用 CSV 靜態快取全自動計算安全邊際，免網路請求，網頁 0 延遲開起 🌟 ----
selectbox_options = []
ticker_to_display_map = {} # 用於反查原始代號

if not stocks_df.empty:
    for index, row in stocks_df.iterrows():
        t_id = str(int(row['ticker'])).strip()
        s_name = row['name']
        p_low = float(row.get('pe_low', 12.0))
        p_high = float(row.get('pe_high', 18.0))
        
        # 直接由資料庫調取每晚 6 點更新好的快取數據
        q_rev = float(row.get('latest_q_rev', 0.0))
        q_eps = float(row.get('latest_q_eps', 0.0))
        gap_rev = float(row.get('gap_months_rev', 0.0))
        rem_base = float(row.get('last_y_remain_rev', 0.0))
        m_price = float(row.get('current_price', 0.0))
        s_yoy = float(row.get('suggested_yoy', 25.0)) / 100
        
        # 拆解該股預設 alpha 級距
        raw_rating = str(row.get('稼動率調整值評估', '1.00x'))
        m_alpha = re.search(r"([0-9\.]+)", raw_rating)
        alpha_def = float(m_alpha.group(1)) if m_alpha else 1.00
        
        # 計算預估未來 12M EPS
        r_est = rem_base * (1 + s_yoy) * alpha_def
        
        # 🌟 🛠️ 修正點 1：精確校正引數名稱為 remain_months_est_rev，讓下拉選單紅字功能正常運作 🌟
        pre_res = run_valuation_core(
        latest_q_rev=q_rev, 
        latest_q_eps=q_eps,
        latest_q_margin=float(row.get('latest_q_margin', 25.0)), # 🌟 新增此行
        gap_months_rev=gap_rev, 
        remain_months_est_rev=r_est,
        pe_low=p_low, 
        pe_high=p_high
        )
        
        # 進行「折價紅字顯影」渲染標籤
        display_label = f"{t_id} {s_name}"
        if pre_res and m_price > 0:
            f_high_p = pre_res['eps_est'] * p_high * alpha_def
            if m_price < f_high_p: # 進入安全折價區
                discount_pct = int(round(((f_high_p - m_price) / f_high_p) * 100))
                display_label = f"🔴 {t_id} {s_name} [折價 {discount_pct}%]"
                
        selectbox_options.append(display_label)
        ticker_to_display_map[display_label] = t_id

# ---- 步驟 4-2：側邊欄控制（Sidebar）----
st.sidebar.header("⚙️ 模型參數風控鎖")

db_alpha_default = 1.00
db_consensus_eps = 0.0

if not stocks_df.empty and selectbox_options:
    selected_display = st.sidebar.selectbox("選擇分析標的", selectbox_options)
    ticker_id = ticker_to_display_map[selected_display] # 反查出純代碼
    stock_info = stocks_df[stocks_df['ticker'] == int(ticker_id)].iloc[0]
    
    # 動態解構資料庫中的 Re-rating 預設值
    raw_rating_str = str(stock_info.get('稼動率調整值評估', '1.00x'))
    match_alpha = re.search(r"([0-9\.]+)", raw_rating_str)
    if match_alpha:
        try:
            db_alpha_default = float(match_alpha.group(1))
            db_alpha_default = max(1.00, min(1.50, db_alpha_default))
        except ValueError:
            db_alpha_default = 1.00
            
    # 提取資料庫中該股的法人預估 EPS 均值 (Consensus)
    db_consensus_eps = float(stock_info.get('今年法人預估EPS均值', 0.0))
    
    # 完全重組原有的 data 字典，直接調用讀入的靜態快取欄位，解耦網路延遲
    data = {
        "latest_q_eps": float(stock_info.get('latest_q_eps', 0.0)),
        "latest_q_rev": float(stock_info.get('latest_q_rev', 0.0)),
        "gap_months_rev": float(stock_info.get('gap_months_rev', 0.0)),
        "last_y_remain_rev": float(stock_info.get('last_y_remain_rev', 0.0)),
        "current_price": float(stock_info.get('current_price', 0.0)),
        "suggested_yoy": int(stock_info.get('suggested_yoy', 25)),
        "q_label": str(stock_info.get('q_label', 'Q1')),
        "gap_label": str(stock_info.get('gap_label', '無')),
        "remain_label": str(stock_info.get('remain_label', '未來月份')),
        "latest_m_label": str(stock_info.get('latest_m_label', '最新月')),
        "latest_m_yoy": int(stock_info.get('latest_m_yoy', 0))
    }
    st.sidebar.caption("📊 數據狀態：已對齊冷儲存靜態資料庫 (100% 效能優化)")
else:
    st.sidebar.warning("目前資料庫無自選股，請先於下方新增股票。")
    data = {"latest_q_eps": 0.0, "latest_q_rev": 0.0, "gap_months_rev": 0.0, "last_y_remain_rev": 0.0, "current_price": 0.0, "suggested_yoy": 25, "q_label": "Q1", "gap_label": "無", "remain_label": "無", "latest_m_label": "最新月", "latest_m_yoy": 0}
    stock_info = {"pe_low": 12.0, "pe_high": 18.0}

st.markdown("---")

# 一字不漏保留您完整的滑桿標籤排版與參數
default_yoy = int(data.get("suggested_yoy", 25))
q_label = data.get("q_label", "最新季")
gap_label = data.get("gap_label", "無")
remain_label = data.get("remain_label", "未來月份")

yoy_slider = st.sidebar.slider(
    f"🔮 未來未知月份營收 YoY (%) [{q_label}實績: {default_yoy}%]", 
    min_value=-50, max_value=100, value=default_yoy, step=5
) / 100

# 核心安全機制：Re-rating 切換開關
auto_toggle_on = True if db_alpha_default > 1.00 else False
enable_rerating = st.sidebar.toggle("⚠️ 啟動高階 AI / 產能爆發 Re-rating 修正", value=auto_toggle_on, key=f"toggle_{ticker_id}")

# 將滑桿的預設帶入值定錨在從 csv 洗出來的 db_alpha_default 數字上
alpha_value = st.sidebar.slider(
    "Re-rating 修正係數 (α)", 
    min_value=1.00, max_value=1.50, value=db_alpha_default, step=0.05, key=f"sl_{ticker_id}"
) if enable_rerating else 1.00

# 一字不漏保留完整的 Re-rating 級距指引 Markdown 表格
with st.sidebar.expander("📘 Re-rating 級距風控定錨指引", expanded=enable_rerating):
    st.markdown("""
    | 修正係數 $\\alpha$ | 適用產業 / 財務質變指標 |
    | :--- | :--- |
    | **1.00x** | **維持現狀**：傳統硬體代工、成熟製程個股。 |
    | **1.05x ~ 1.10x** | **客戶拓展**：切入新供應鏈、毛利率連官方小拉。 |
    | **1.15x ~ 1.25x** | **結構性紅利 (如南電、日月光)**：高階 AI 載板、先進封裝、Starlink 核心鏈、財報雙重跳升。 |
    | **1.30x ~ 1.50x** | **市場壟斷 (如德律、大銀微)**：先進製程設備大週期、技術極高專利壁壘。 |
    """)

if not stocks_df.empty:
    st.sidebar.info(f"""📊 當前資料庫核心投研定錨：
- 防守低標 PE: {stock_info['pe_low']}x
- 合理高標 PE: {stock_info['pe_high']}x
- 稼動率評估: {stock_info.get('稼動率調整值評估', '1.00x')}
- 法人預估均值: {db_consensus_eps} 元""")

# ---- 步驟 4-3：主畫面數據核實與手動微調（一字不漏完整對齊原有排版） ----
st.markdown(f"### 📑 滾動 12M 核實基底資料 ── 分析標的：`{ticker_id} {stock_info['name']} ({q_label})`")

latest_m_label = data.get("latest_m_label", "最新月")
latest_m_yoy = data.get("latest_m_yoy", 0)

m1, m2 = st.columns(2)
with m1:
    st.metric(label=f"📈 最新季度實績營收 YoY ({q_label})", value=f"{default_yoy} %", delta=f"{default_yoy}%")
with m2:
    st.metric(label=f"📅 最新單月實績營收 YoY ({latest_m_label})", value=f"{data['latest_m_yoy']} %", delta=f"{data['latest_m_yoy']}%")

st.markdown(" ") 

col1, col2, col3 = st.columns(3)
with col1:
    q1_eps_input = st.number_input(f"當季 ({q_label}) 實際單季 EPS", value=float(data['latest_q_eps']), format="%.2f", key=f"eps_{ticker_id}")
    q1_rev_input = st.number_input(f"當季 ({q_label}) 單季營收 (億)", value=float(data['latest_q_rev']), format="%.2f", key=f"q_rev_{ticker_id}")
with col2:
    m4_rev_input = float(stock_info.get('gap_months_rev', 0.0))  
    st.number_input(f"季報後已公告月營收 (億) ── 已納入: {gap_label}", value=m4_rev_input, format="%.2f", disabled=True, key=f"gap_{ticker_id}")
    remain_base_rev = float(data['last_y_remain_rev'])
    remain_est_rev = remain_base_rev * (1 + yoy_slider)
    st.number_input(f"未知月份歷史基期總營收 (億) ── 對應: {remain_label}", value=remain_base_rev, format="%.2f", disabled=True, key=f"rem_{ticker_id}")
with col3:
    market_price = st.number_input("今日市場收盤價", value=float(data['current_price']), format="%.2f", key=f"price_{ticker_id}")

# ---- 步驟 4-4：執行核心模型計算 ----
# 🌟 🛠️ 修正點 2：將主功能引數名同樣精確校正為 remain_months_est_rev，達成全面數據咬合 🌟
res = run_valuation_core(
    latest_q_rev=q1_rev_input, 
    latest_q_eps=q1_eps_input, 
    latest_q_margin=float(stock_info.get('latest_q_margin', 25.0)), # 從 CSV 或資料庫撈取毛利率
    gap_months_rev=m4_rev_input, 
    remain_months_est_rev=remain_est_rev,
    pe_low=stock_info['pe_low'], 
    pe_high=stock_info['pe_high']
)

# ---- 步驟 4-5：UI 狀態燈號顯示與極端估值警示 ----
if res:
    st.markdown("---")
    st.markdown("### 📈 Forward 12M 模型推算與滾動價值區間")
    
    # 橫向擴展為 7 個核心指標主面板 (兩大價格天花板欄位完美歸位)
    col_m1, col_m2, col_m_consensus, col_f_high, col_irr_p, col_m3, col_m4 = st.columns(7)
    
    col_m1.metric("今日最新收盤價", f"{market_price} 元")
    calculated_eps = round(res['eps_est'], 2)
    col_m2.metric("Forward 12M 預估總 EPS", f"{calculated_eps} 元")
    col_m_consensus.metric("今年法人預估 EPS 均值", f"{db_consensus_eps} 元")
    
    # 常態合理高標價格
    pe_high_base = float(stock_info['pe_high'])
    # 🏛️ 欄位一：常態合理高標價格（理性 EPS x 理性歷史 PE x 唯一的評價 Re-rating α）
    fair_high_price = round(calculated_eps * pe_high_base * alpha_value, 1)
    col_f_high.metric("🏛️ 常態合理高標價", f"{fair_high_price} 元", help="公式：預估總 EPS x 歷史高標 PE x α")
    
    # 🔥 欄位二：情緒溢價天花板價格（在 Re-rating 基礎上，外加 25% 右尾極端追價情緒）
    irrational_pe_ceiling = round(pe_high_base * 1.25 * alpha_value, 2)
    hot_ceiling_price = round(calculated_eps * irrational_pe_ceiling, 1)
    col_irr_p.metric("🔥 情緒溢價天花板價", f"{hot_ceiling_price} 元", help="公式：預估總 EPS x (歷史高標 PE x 1.25 x α)")
    
    col_m3.metric("領先半年合理價值區間", res['fair_range'])
    pe_dynamic = round(market_price / res['eps_est'], 2) if res['eps_est'] != 0 else 0.0
    col_m4.metric("動態 Forward 12M PE", f"{pe_dynamic} 倍")

    # 建立一個專門的情緒溢價監控儀表板 (UI 回歸)
    st.markdown("#### 🧠 經理人風控監控：非理性繁榮情緒溢價指標")
    v1, v2, v3 = st.columns(3)
    v1.metric(label="📊 歷史常態合理高標 PE", value=f"{pe_high_base} 倍", help="過去 3 年大數據去雜訊後評價天花板。")
    v2.metric(label="🔥 非理性繁榮情緒溢價 PE 天花板", value=f"{irrational_pe_ceiling} 倍", delta=f"+25% 情緒溢價", delta_color="inverse")
    
    overpriced_pct = int(round(((market_price - fair_high_price) / fair_high_price) * 100)) if fair_high_price > 0 else 0
    if overpriced_pct > 0:
        v3.metric(label="⚠️ 當前市價超額交易（溢價）", value=f"{overpriced_pct} %", delta="超越歷史合理高標", delta_color="inverse")
    else:
        v3.metric(label="🛡️ 當前市價安全邊際（折價）", value=f"{abs(overpriced_pct)} %", delta="低於歷史合理高標", delta_color="normal")

    # 原始字串加註 LaTeX 算式白皮書 (UI 回歸)
    with st.expander("📘 查看學術與法人級底層估值算式與推導邏輯", expanded=False):
        st.markdown(r"""
        ### 📐 核心風控指標公式白皮書
        本系統底層之關鍵指標均對齊法人級計量標準，其精確推導算式如下：

        #### 1️⃣ 常態合理高標價格 (Fair High Price)
        代表在歷史常態估值極限下，結合未來 12M 基本面與產業結構性修正的理性價值上限：
        $$
        \text{常態合理高標價} = \text{Forward 12M 預估總 EPS} \times \text{歷史合理高標 PE} \times \alpha
        $$

        #### 2️⃣ 非理性繁榮情緒溢價價格 (Ceiling Hot Price)
        考慮市場極端追價、非理性過熱情緒（歷史高標再溢價 25%）下的終極右尾安全防線：
        $$
        \text{情緒溢價天花板價} = \text{Forward 12M 預估總 EPS} \times (\text{歷史合理高標 PE} \times 1.25 \times \alpha)
        $$
        """)

    st.markdown(" ") 

    # 預期對撞警告燈
    if db_consensus_eps > 0 and calculated_eps > db_consensus_eps:
        deviation_pct = round(((calculated_eps - db_consensus_eps) / db_consensus_eps) * 100, 1)
        st.info(f"🔵 **營運動能超越市場預期 (強烈 Re-rating 訊號)**：目前模型推算之滾動 EPS ({calculated_eps}元) 高出法人圈預期均值 ({db_consensus_eps}元) **+{deviation_pct}%**！潛在的估值重估動能正在發酵。")

    # 原本的過熱/安全燈號警告
    if market_price > res['hot']:
        st.error(f"🔴 嚴重過熱：目前市價突破未來 12M 過熱防線 ({res['hot']}元)！當前動態本益比 {pe_dynamic} 倍，已超前交易過多未來預期。")
    elif market_price < res['cheap']:
        st.success(f"🟢 價值顯現：目前股價低於 Forward 12M 保守安全防線 ({res['cheap']}元)，具備極高安全邊際。")
    else:
        st.info("🟡 股價正於未來 12M 基本面合理區間內震盪。")

# ---- ⚙️ 資料庫維護區 ----
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
                new_row = pd.DataFrame([{
                    "ticker": int(new_ticker), "name": new_name, "pe_low": 0.0, "pe_high": 0.0,
                    "稼動率調整值評估": "1.00x (維持現狀：傳統個股)", "今年法人預估EPS均值": 0.0
                }])
                new_row.to_csv(csv_filename, mode='a', header=False, index=False, encoding="utf-8-sig")
                st.success(f"✅ {new_ticker} {new_name} 已臨時寫入雲端暫存！")
                st.rerun()

if st.sidebar.button("🎯 僅更新全新標的 PE (行動推薦)"):
    with st.sidebar.status("正在精準定錨新股票大數據...", expanded=True) as status:
        ret_msg = run_targeted_update()
        status.update(label=ret_msg, state="complete")
    st.rerun()

if st.sidebar.button("🔄 一鍵滾動更新歷史 PE (全清單)"):
    with st.sidebar.status("正在動態計算全資料庫 3 年大數據...", expanded=True) as status:
        ret_msg = run_batch_update()
        status.update(label=ret_msg, state="complete")
    st.rerun()
