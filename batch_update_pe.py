# batch_update_pe.py (內建函數無縫調度 ＋ 轉型亂碼修正完全體)
import pandas as pd
import os
import time
import warnings
# 強制讓 Python 忽略來自 Streamlit 的執行緒警告，保持終端機與背景乾淨
warnings.filterwarnings("ignore", category=UserWarning, module="streamlit")

from data_fetcher import auto_compute_pe_intervals

def run_batch_update():
    """
    🌟 整合版歷史 PE 計算核心：兼顧本地終端機執行與雲端網頁（app.py）無縫直接呼叫
    """
    csv_filename = "stock_list.csv"
    
    if not os.path.exists(csv_filename):
        msg = f"❌ 錯誤：找不到 {csv_filename}"
        print(msg)
        return msg
    
    try:
        # 🌟 讀取時強制指定 pe_low 與 pe_high 為 float 型態，允許小數點寫入
        df = pd.read_csv(
            csv_filename, 
            encoding="utf-8-sig", 
            dtype={'ticker': int, 'name': str, 'pe_low': float, 'pe_high': float}
        )
    except Exception as e:
        msg = f"❌ 讀取自選股清單失敗: {str(e)}"
        print(msg)
        return msg
    
    if df.empty:
        msg = "⚠️ 目前自選股清單中沒有任何股票"
        print(msg)
        return msg
    
    print("🔄 [真實數據解鎖] 開始自動量化計算全自選股之歷史防守 PE 區間...")
    print("==================================================================")
    
    success_count = 0
    for index, row in df.iterrows():
        ticker_str = str(int(row['ticker'])).strip()
        stock_name = row['name']
        
        try:
            # 呼叫真正對齊時間軸與全域月份洗滌的統計引擎
            low, high = auto_compute_pe_intervals(ticker_str)
            
            # 成功解鎖後寫入有小數點的科學數據
            df.at[index, 'pe_low'] = float(low)
            df.at[index, 'pe_high'] = float(high)
            print(f"✅ 更新成功 ── {ticker_str} {stock_name:<6} | 防守低標: {low}x | 合理高標: {high}x")
            success_count += 1
            
            # 🌟 防禦型定時器：避免在外雲端大量更新時，因頻率過高被 API 伺服器斷線
            time.sleep(0.5)
            
        except Exception as e:
            print(f"⚠️ 標的 {ticker_str} {stock_name} 計算失敗: {str(e)}")
            
    # 存檔時加入 encoding="utf-8-sig"，確保 Excel 開啟中文絕對不亂碼
    df.to_csv(csv_filename, index=False, encoding="utf-8-sig")
    print("==================================================================")
    
    success_msg = f"💾 [雲端同步完成] 成功校正 {success_count} 檔自選股 PE 區間並回寫資料庫！"
    print(success_msg)
    return success_msg

# 保留原本在本機電腦終端機直接執行的備援獨立觸發機制
if __name__ == "__main__":
    run_batch_update()
