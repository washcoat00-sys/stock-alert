import pandas as pd
import yfinance as yf
import requests
import os
from datetime import datetime

# 1. 보안 설정: 깃허브 Secrets에 저장된 값을 안전하게 불러옵니다.
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
CSV_FILE = 'code.csv'

# 2. 분석 기준 설정
AVAILABLE_WINDOWS = [500, 300, 200, 100, 50] # 가용한 가장 긴 데이터 기준 선택
SIGMA_MULT = 1.0  # 사용자 요청 사항: 1시그마 판정 기준

def send_telegram_msg(message):
    """최종 리포트를 텔레그램으로 전송합니다."""
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("에러: 텔레그램 토큰 또는 채팅 ID 설정이 필요합니다.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
    try:
        requests.post(url, json=payload, timeout=20)
    except Exception as e:
        print(f"텔레그램 전송 실패: {e}")

def analyze_stocks():
    """모든 종목을 분석하여 한 줄 요약 리포트를 생성합니다."""
    try:
        df_targets = pd.read_csv(CSV_FILE, dtype={'code': str})
    except FileNotFoundError:
        print(f"에러: {CSV_FILE} 파일을 찾을 수 없습니다.")
        return

    # 리포트 헤더 생성
    now_str = datetime.now().strftime('%m/%d %H:%M')
    report_lines = [f"📊 <b>주식 상태 리포트 ({now_str})</b>"]
    report_lines.append(f"<i>기준: {SIGMA_MULT}시그마 (1.0배 표준편차)</i>\n")

    for code in df_targets['code']:
        ticker = code if '.' in code else f"{code}.KS"
        try:
            # 주가 데이터 로드
            stock = yf.Ticker(ticker)
            df = stock.history(period="3y")
            
            if df.empty or len(df) < 50:
                continue

            data_len = len(df)
            # 사용 가능한 가장 긴 분석 기간(Window) 선택
            current_window = next((w for w in AVAILABLE_WINDOWS if data_len >= w), 50)

            # 이동평균(MA) 및 표준편차(Std) 계산
            df['MA'] = df['Close'].rolling(window=current_window).mean()
            df['Std'] = df['Close'].rolling(window=current_window).std()
            
            last = df.iloc[-1]
            curr_price = last['Close']
            ma = last['MA']
            std = last['Std']
            
            # 상/하한선 계산 (1시그마 기준)
            lower_bound = ma - (SIGMA_MULT * std)
            upper_bound = ma + (SIGMA_MULT * std)
            
            # 평균가 대비 현재 변동량(%) 계산
            change_rate = ((curr_price - ma) / ma) * 100
            
            # 상태 판정 및 이모지 설정
            if curr_price <= lower_bound:
                status = "🔴 구매검토"
            elif curr_price >= upper_bound:
                status = "🔵 급등알림"
            else:
                status = "⚫ 관망중"

            # 한 줄 출력 포맷 적용
            # [상태] | [종목] | [현재가] | [평균대비변동%] | [일일표준편차]
            line = f"{status} | {ticker} | {int(curr_price):,}원 | 변동: {change_rate:+.1f}% | 표편: {std:.1f}"
            report_lines.append(line)
            
        except Exception as e:
            report_lines.append(f"⚠️ {ticker}: 분석 오류 ({e})")

    # 전체 리포트 전송
    full_report = "\n".join(report_lines)
    send_telegram_msg(full_report)
    print("텔레그램 리포트 전송 완료!")

if __name__ == "__main__":
    analyze_stocks()
