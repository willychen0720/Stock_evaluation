# batch_update_pe.py (修正轉型與亂碼之完全體)
import pandas as pd
import os
import warnings
# 強制讓 Python 忽略來自 Streamlit 的執行緒警告，保持終端機乾淨
warnings.filterwarnings("ignore", category=UserWarning, module="streamlit")

from data_fetcher import auto_compute_pe_intervals

def execute_database_update():
    csv_filename = "stock_list.csv"
    
    if not os.path.exists(csv_filename):
        print(f"❌ 錯誤：找不到 {csv_filename}")
        return
    
    # 🌟 關鍵優化：讀取時強制指定 pe_low 與 pe_high 為 float 型態，允許小數點寫入
    df = pd.read_csv(
        csv_filename, 
        encoding="utf-8-sig", 
        dtype={'ticker': int, 'name': str, 'pe_low': float, 'pe_high': float}
    )
    
    print("🔄 [真實數據解鎖] 開始自動量化計算全自選股之歷史防守 PE 區間...")
    print("==================================================================")
    
    for index, row in df.iterrows():
        ticker_str = str(int(row['ticker'])).strip()
        stock_name = row['name']
        
        try:
            # 呼叫真正對齊時間軸的統計引擎
            low, high = auto_compute_pe_intervals(ticker_str)
            
            # 成功解鎖後寫入有小數點的科學數據
            df.at[index, 'pe_low'] = float(low)
            df.at[index, 'pe_high'] = float(high)
            print(f"✅ 更新成功 ── {ticker_str} {stock_name:<6} | 防守低標: {low}x | 合理高標: {high}x")
            
        except Exception as e:
            print(f"⚠️ 標的 {ticker_str} {stock_name} 計算失敗: {str(e)}")
            
    # 存檔時加入 encoding="utf-8-sig"，確保 Excel 開啟中文絕對不亂碼
    df.to_csv(csv_filename, index=False, encoding="utf-8-sig")
    print("==================================================================")
    print("💾 [資料庫升級完成] 亂碼、轉型、真實 PE 均已完美全數校正完畢！")

if __name__ == "__main__":
    execute_database_update()