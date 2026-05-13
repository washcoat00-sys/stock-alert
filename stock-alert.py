import pandas as pd
import yfinance as yf
import requests
import os
from datetime import datetime

# --- 설정 (GitHub Secrets 연동) ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
CSV_FILE = 'code.csv'

AVAILABLE_WINDOWS = [500, 300, 200, 100, 50]
SIGMA_MULT = 1.0  # 1시그마 기준

def send_telegram_msg(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("에러: 텔레그램 토큰 또는 채팅 ID 설정이 필요합니다.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
    try:
        requests.post(url, json=payload, timeout=20)
    except Exception as e:
        print(f"전송 실패: {e}")

def analyze_stocks():
    try:
        df_targets = pd.read_csv(CSV_FILE, dtype={'code': str})
    except FileNotFoundError:
        print(f"에러: {CSV_FILE} 파일을 찾을 수 없습니다.")
        return

    now_str = datetime.now().strftime('%m/%d %H:%M')
    report_lines = [f"📊 <b>주식 상태 리포트 ({now_str})</b>"]
    report_lines.append(f"<i>기준: 일일 변동률 {SIGMA_MULT}시그마</i>\n")

    for index, row in df_targets.iterrows():
        code = str(row['code'])
        # CSV에 'name' 열이 있으면 종목명을 가져옵니다.
        stock_name = row['name'] if 'name' in df_targets.columns else code
        
        ticker = code if '.' in code else f"{code}.KS"
        display_name = f"<b>{stock_name}</b>({code})" if stock_name != code else f"<b>{ticker}</b>"

        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="3y")
            
            df['Daily_Return'] = df['Close'].pct_change() * 100
            df = df.dropna(subset=['Daily_Return'])
            
            if df.empty or len(df) < 50:
                continue

            data_len = len(df)
            current_window = next((w for w in AVAILABLE_WINDOWS if data_len >= w), 50)

            df['Return_MA'] = df['Daily_Return'].rolling(window=current_window).mean()
            df['Return_Std'] = df['Daily_Return'].rolling(window=current_window).std()
            
            last = df.iloc[-1]
            curr_price = last['Close']
            
            curr_return = last['Daily_Return']
            mean_return = last['Return_MA']
            std_return = last['Return_Std']
            
            lower_bound = mean_return - (SIGMA_MULT * std_return)
            upper_bound = mean_return + (SIGMA_MULT * std_return)
            
            if curr_return <= lower_bound:
                status = "🔴 구매검토"
            elif curr_return >= upper_bound:
                status = "🔵 급등알림"
            else:
                status = "⚫ 관망중"

            # 텔레그램 출력 포맷 (2줄 출력)
            line = f"{status} | {display_name} | {int(curr_price):,}원\n└ 1σ범위: {lower_bound:+.2f}% ~ {upper_bound:+.2f}% / 오늘: {curr_return:+.2f}%"
            report_lines.append(line)
            
        except Exception as e:
            report_lines.append(f"⚠️ {display_name}: 분석 오류")

    full_report = "\n".join(report_lines)
    send_telegram_msg(full_report)
    print("텔레그램 리포트 전송 완료!")

if __name__ == "__main__":
    analyze_stocks()
