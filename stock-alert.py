import pandas as pd
import yfinance as yf
import requests
import os
from datetime import datetime

# --- 설정 (GitHub Secrets 연동) ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
CSV_FILE = 'code.csv'

# 분석 기준 설정
AVAILABLE_WINDOWS = [500, 300, 200, 100, 50]
SIGMA_MULT = 2

def send_telegram_msg(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    # HTML 모드를 사용하여 가독성을 높입니다.
    payload = {'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
    try:
        requests.post(url, json=payload, timeout=15)
    except Exception as e:
        print(f"전송 실패: {e}")

def analyze_stocks():
    try:
        df_targets = pd.read_csv(CSV_FILE, dtype={'code': str})
    except FileNotFoundError:
        return

    report_lines = [f"📊 <b>주식 상태 리포트 ({datetime.now().strftime('%m/%d %H:%M')})</b>\n"]

    for code in df_targets['code']:
        ticker = code if '.' in code else f"{code}.KS"
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="3y")
            data_len = len(df)
            
            current_window = next((w for w in AVAILABLE_WINDOWS if data_len >= w), None)
            if not current_window: continue

            # 계산: 이동평균, 표준편차
            df['MA'] = df['Close'].rolling(window=current_window).mean()
            df['Std'] = df['Close'].rolling(window=current_window).std()
            
            last = df.iloc[-1]
            curr_price = last['Close']
            ma = last['MA']
            std = last['Std']
            
            # 상/하한값 계산
            lower_bound = ma - (SIGMA_MULT * std)
            upper_bound = ma + (SIGMA_MULT * std)
            
            # 변동률 계산 (현재가와 이동평균의 괴리율)
            change_rate = ((curr_price - ma) / ma) * 100
            
            # 상태 및 이모지 판정
            if curr_price <= lower_bound:
                status = "🔴 구매 검토"  # 하한 돌파 (적색)
            elif curr_price >= upper_bound:
                status = "🔵 급등"      # 상한 돌파 (파란색)
            else:
                status = "⚫ 관망"      # 범위 내 (검은색)

            # 한 줄 리포트 작성
            line = (f"{status} | {ticker}\n"
                    f"└ 현재가: {int(curr_price):,}원 (변동: {change_rate:+.2f}%)\n"
                    f"└ 표준편차: {std:.2f} | 기준: {current_window}일\n")
            report_lines.append(line)
            
        except Exception as e:
            report_lines.append(f"⚠️ {ticker}: 분석 오류\n")

    # 전체 리포트 전송
    full_report = "\n".join(report_lines)
    send_telegram_msg(full_report)
    print("리포트 전송 완료")

if __name__ == "__main__":
    analyze_stocks()