# batch_update_pe.py (輕量化精準打擊版)
import pandas as pd
import os
import time
import warnings
# 強制讓 Python 忽略來自 Streamlit 的執行緒警告，保持背景乾淨
warnings.filterwarnings("ignore", category=UserWarning, module="streamlit")

from data_fetcher import auto_compute_pe_intervals

def load_stock_df(csv_filename):
    """公用讀取函數，保持轉型與亂碼修正"""
    if not os.path.exists(csv_filename):
        return None, f"❌ 錯誤：找不到 {csv_filename}"
    try:
        df = pd.read_csv(
            csv_filename, 
            encoding="utf-8-sig", 
            dtype={'ticker': int, 'name': str, 'pe_low': float, 'pe_high': float}
        )
        return df, "OK"
    except Exception as e:
        return None, f"❌ 讀取自選股清單失敗: {str(e)}"

def run_batch_update():
    """全域更新：全自選股大洗牌（適合本地端定期維護）"""
    csv_filename = "stock_list.csv"
    df, msg = load_stock_df(csv_filename)
    if df is None: return msg
    if df.empty: return "⚠️ 目前自選股清單中沒有任何股票"
    
    print("🔄 [全域量化計算] 開始自動計算全自選股之歷史防守 PE 區間...")
    success_count = 0
    for index, row in df.iterrows():
        ticker_str = str(int(row['ticker'])).strip()
        stock_name = row['name']
        try:
            low, high = auto_compute_pe_intervals(ticker_str)
            df.at[index, 'pe_low'] = float(low)
            df.at[index, 'pe_high'] = float(high)
            print(f"✅ 全域更新 ── {ticker_str} {stock_name:<6} | {low}x ~ {high}x")
            success_count += 1
            time.sleep(0.5)
        except Exception as e:
            print(f"⚠️ 標的 {ticker_str} {stock_name} 計算失敗: {str(e)}")
            
    df.to_csv(csv_filename, index=False, encoding="utf-8-sig")
    return f"💾 [全域同步完成] 成功校正 {success_count} 檔自選股 PE 區間！"


def run_targeted_update():
    """
    🎯 輕量化精準打擊：【專門針對在外行動看盤設計】
    只去撈取 pe_low == 0.0 或 pe_high == 0.0 的全新股票進行快速精算。
    """
    csv_filename = "stock_list.csv"
    df, msg = load_stock_df(csv_filename)
    if df is None: return msg
    if df.empty: return "⚠️ 目前自選股清單中沒有任何股票"
    
    # 篩選出需要補齊數據的「全新未計算股票」
    target_df = df[(df['pe_low'] == 0.0) | (df['pe_high'] == 0.0)]
    
    if target_df.empty:
        return "ℹ️ 雲端提示：目前所有股票的歷史 PE 皆已定錨完畢，無需重複計算！"
        
    print(f"🎯 [精準局部打擊] 偵測到 {len(target_df)} 檔新股票需要定錨...")
    success_count = 0
    
    for index, row in target_df.iterrows():
        ticker_str = str(int(row['ticker'])).strip()
        stock_name = row['name']
        try:
            # 只針對這幾檔新股票穿透大數據統計引擎
            low, high = auto_compute_pe_intervals(ticker_str)
            df.at[index, 'pe_low'] = float(low)
            df.at[index, 'pe_high'] = float(high)
            print(f"🎯 精準更新 ── {ticker_str} {stock_name:<6} | {low}x ~ {high}x")
            success_count += 1
            time.sleep(0.5)
        except Exception as e:
            print(f"⚠️ 標的 {ticker_str} {stock_name} 精準計算失敗: {str(e)}")
            
    # 將計算好的局部數據完美回寫 CSV
    df.to_csv(csv_filename, index=False, encoding="utf-8-sig")
    return f"⚡ [精準更新完成] 已成功定錨 {success_count} 檔全新標的之 PE 區間！"


if __name__ == "__main__":
    run_batch_update()
