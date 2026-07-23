import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as bg
import plotly.express as px
import yfinance as yf

# ---------------------------------------------------------
# 1. Page Config
# ---------------------------------------------------------
st.set_page_config(
    page_title="글로벌 화석연료 고갈 & 자원 가격 시뮬레이터",
    page_icon="⛽",
    layout="wide"
)

st.title("⛽ 글로벌 화석연료 잔존량 & 자원 가격 예측 대시보드")
st.markdown("""
누적 생산량 및 최신 매장량 데이터를 기반으로 **자원의 고갈 시점**과 **소비 속도에 따른 자원 가격 추이**를 추정합니다.
사이드바에서 변수를 조절하여 시나리오별 변화를 확인해보세요.
""")

# ---------------------------------------------------------
# 2. Baseline Data (EI Statistical Review & Energy Data 기준)
# ---------------------------------------------------------
# 매장량 기준: 석유(Gb, 십억 배럴), 석탄(Gt, 십억 톤), 가스(Tcm, 조 입방미터)
# 연간 소비량: 석유(Gb/yr), 석탄(Gt/yr), 가스(Tcm/yr)
BASE_DATA = {
    "석유 (Oil)": {
        "cumulative_past": 1400.0,  # 과거 누적 소비량 (Gb)
        "reserves": 1730.0,         # 현재 추정 매장량 (Gb)
        "annual_demand": 36.5,      # 연간 소비량 (Gb/yr)
        "unit": "Gb (십억 배럴)",
        "current_price": 75.0,      # 기준 가격 ($/배럴)
        "tickers": ["SHEL", "XOM", "CVX", "TTE"]
    },
    "석탄 (Coal)": {
        "cumulative_past": 400.0,   # 과거 누적 소비량 (Gt)
        "reserves": 1070.0,         # 현재 추정 매장량 (Gt)
        "annual_demand": 8.5,       # 연간 소비량 (Gt/yr)
        "unit": "Gt (십억 톤)",
        "current_price": 130.0,     # 기준 가격 ($/톤)
        "tickers": ["BTU", "ARLP", "ARCH"]
    },
    "천연가스 (Gas)": {
        "cumulative_past": 110.0,   # 과거 누적 소비량 (Tcm)
        "reserves": 188.0,          # 현재 추정 매장량 (Tcm)
        "annual_demand": 4.0,       # 연간 소비량 (Tcm/yr)
        "unit": "Tcm (조 m³)",
        "current_price": 2.8,       # 기준 가격 ($/MMBtu)
        "tickers": ["EQT", "AR", "LNG"]
    }
}

# ---------------------------------------------------------
# 3. Sidebar - Parameters Setup
# ---------------------------------------------------------
st.sidebar.header("⚙️ 시뮬레이션 변수 설정")

fuel_type = st.sidebar.selectbox("자원 선택", list(BASE_DATA.keys()))
fuel_info = BASE_DATA[fuel_type]

st.sidebar.subheader("1. 수요 및 매장량 변수")
reserves_adj = st.sidebar.slider(
    f"추정 매장량 조정 ({fuel_info['unit']})",
    min_value=float(fuel_info["reserves"] * 0.5),
    max_value=float(fuel_info["reserves"] * 2.0),
    value=float(fuel_info["reserves"]),
    step=10.0
)

demand_growth = st.sidebar.slider(
    "연간 소비량 증가율 (%)",
    min_value=-3.0,
    max_value=5.0,
    value=1.0,
    step=0.1
)

st.sidebar.subheader("2. 가격 예측 변수 (Hotelling's Rule)")
discount_rate = st.sidebar.slider(
    "자원 희소성 할인율/이자율 (%)",
    min_value=1.0,
    max_value=10.0,
    value=4.0,
    step=0.5
) / 100.0

extraction_cost_growth = st.sidebar.slider(
    "채굴 난이도 상승에 따른 비용 증가율 (%)",
    min_value=0.0,
    max_value=5.0,
    value=1.5,
    step=0.1
) / 100.0

# ---------------------------------------------------------
# 4. Math Model Calculation
# ---------------------------------------------------------
years = np.arange(2026, 2026 + 100)
annual_demands = []
remaining_reserves = []
prices = []

curr_res = reserves_adj
curr_demand = fuel_info["annual_demand"]
curr_price = fuel_info["current_price"]

for i, y in enumerate(years):
    # 당해 소비량 적용
    if curr_res > 0:
        actual_consumption = min(curr_res, curr_demand)
        curr_res -= actual_consumption
    else:
        actual_consumption = 0
    
    # 가격 추정 모델: 기본 가격 * (1 + 할인율 + 채굴비용상승)^t / (남은 잔존율 비율)
    scarcity_factor = max(0.01, (curr_res / reserves_adj))
    projected_price = curr_price * ((1 + discount_rate + extraction_cost_growth) ** i) / (scarcity_factor ** 0.3)
    
    annual_demands.append(actual_consumption)
    remaining_reserves.append(curr_res)
    prices.append(projected_price if curr_res > 0 else np.nan)
    
    # 다음 해 소비량 증가율 적용
    curr_demand *= (1 + demand_growth / 100.0)

df_sim = pd.DataFrame({
    "연도": years,
    "잔존 매장량": remaining_reserves,
    "연간 소비량": annual_demands,
    "예측 가격": prices
})

# 고갈 연도 계산
depletion_year = df_sim[df_sim["잔존 매장량"] <= 0]["연도"].min()
depletion_text = f"{depletion_year}년" if pd.notna(depletion_year) else "100년 이상 남음"

# ---------------------------------------------------------
# 5. Main Dashboard View
# ---------------------------------------------------------
col1, col2, col3 = st.columns(3)
col1.metric("현재 설정 매장량", f"{reserves_adj:,.1f} {fuel_info['unit']}")
col2.metric("현재 연간 소비량", f"{fuel_info['annual_demand']} {fuel_info['unit']}/년")
col3.metric("예상 고갈 시점", depletion_text)

st.markdown("---")

# 차트 레이아웃
c_chart1, c_chart2 = st.columns(2)

with c_chart1:
    st.subheader("📉 자원 잔존량 추이")
    fig_res = px.line(df_sim, x="연도", y="잔존 매장량", 
                      title=f"{fuel_type} 잔존량 예측",
                      labels={"잔존 매장량": fuel_info['unit']})
    fig_res.update_traces(line_color="#E74C3C", line_width=3)
    st.plotly_chart(fig_res, use_container_width=True)

with c_chart2:
    st.subheader("📈 시나리오별 자원 가격 예측")
    fig_price = px.line(df_sim, x="연도", y="예측 가격", 
                        title=f"{fuel_type} 추정 가격 그래프 ($)",
                        labels={"예측 가격": "가격 ($)"})
    fig_price.update_traces(line_color="#2ECC71", line_width=3)
    st.plotly_chart(fig_price, use_container_width=True)

# ---------------------------------------------------------
# 6. Real-time Enterprise Data (yfinance)
# ---------------------------------------------------------
st.markdown("---")
st.subheader(f"🌐 실시간 {fuel_type} 생산 기업 시장 정보")
st.caption("Yahoo Finance API를 통해 주요 자원 기업들의 실시간 주가 및 연간 성과 데이터를 연동합니다.")

@st.cache_data(ttl=3600)
def fetch_corporate_data(tickers):
    data = []
    for t in tickers:
        try:
            ticker_obj = yf.Ticker(t)
            info = ticker_obj.info
            data.append({
                "티커": t,
                "기업명": info.get("shortName", t),
                "현재 주가 ($)": info.get("currentPrice", info.get("regularMarketPrice", "N/A")),
                "시가총액 ($)": f"{info.get('marketCap', 0) / 1e9:,.2f} B",
                "PER": info.get("trailingPE", "N/A"),
                "배당수익률 (%)": f"{info.get('dividendYield', 0) * 100:.2f}%" if info.get('dividendYield') else "N/A"
            })
        except Exception:
            continue
    return pd.DataFrame(data)

df_corp = fetch_corporate_data(fuel_info["tickers"])
st.dataframe(df_corp, hide_index=True, use_container_width=True)

# ---------------------------------------------------------
# 7. Raw Data Table View
# ---------------------------------------------------------
with st.expander("📄 시뮬레이션 원본 데이터 표 보기"):
    st.dataframe(df_sim)
