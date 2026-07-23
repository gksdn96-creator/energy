import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import urllib.parse

# ---------------------------------------------------------
# 1. Page Config
# ---------------------------------------------------------
st.set_page_config(
    page_title="글로벌 에너지 정책 & 생태계 시뮬레이터",
    page_icon="🌍",
    layout="wide"
)

st.title("🌍 실시간 정부 정책 연동 미래 에너지 생태계 시뮬레이터")
st.markdown("""
각국 정부의 **신재생·원자력·온실가스 관련 실시간 정책 뉴스**를 수집하여 
정책 강화/후퇴 지수를 산출하고, 이를 미래 화석연료 고갈 시점 및 가격 예측에 자동 반영합니다.
""")

# ---------------------------------------------------------
# 2. Real-time Policy RSS Crawler & Sentiment Engine
# ---------------------------------------------------------
@st.cache_data(ttl=1800)  # 30분마다 뉴스 갱신
def fetch_policy_news(keyword):
    encoded_kw = urllib.parse.quote(keyword)
    url = f"https://news.google.com/rss/search?q={encoded_kw}&hl=ko&gl=KR&ceid=KR:ko"
    
    articles = []
    try:
        response = requests.get(url, timeout=5)
        soup = BeautifulSoup(response.content, "xml")
        items = soup.find_all("item")
        
        for item in items[:6]:  # 최근 6개 기사
            title = item.title.text
            link = item.link.text
            pub_date = item.pubDate.text[:16]
            articles.append({"title": title, "link": link, "date": pub_date})
    except Exception as e:
        articles.append({"title": "뉴스 수집 실패 (네트워크 확인 필요)", "link": "#", "date": ""})
        
    return articles

def calculate_policy_score(articles):
    """
    기사 제목 내 긍정/부정 정책 키워드를 스캔하여 정책 지수(-10 ~ +10) 산출
    """
    pos_words = ["확대", "상향", "지원", "의무화", "투자", "친환경", "달성", "규제 강화", "보조금"]
    neg_words = ["축소", "하향", "철회", "폐지", "완화", "중단", "연기", "반발"]
    
    score = 0
    for a in articles:
        title = a["title"]
        for pw in pos_words:
            if pw in title:
                score += 1.5
        for nw in neg_words:
            if nw in title:
                score -= 1.5
                
    return max(-10.0, min(10.0, score))

# ---------------------------------------------------------
# 3. Sidebar & Policy Auto-Integration
# ---------------------------------------------------------
st.sidebar.header("📡 실시간 정책 모니터링 설정")

country_keyword = st.sidebar.selectbox(
    "모니터링 대상 정책 주제",
    ["신재생 에너지 정책", "원자력 발전 비중", "온실가스 감축 목표 NDC", "탄소배출권 탄소세"]
)

raw_articles = fetch_policy_news(country_keyword)
policy_score = calculate_policy_score(raw_articles)

st.sidebar.markdown(f"**현재 정책 드라이브 지수:** `{policy_score:+.1f} / 10.0`")
if policy_score > 0:
    st.sidebar.success("🟢 친환경/전환 정책 강화 추세")
elif policy_score < 0:
    st.sidebar.warning("🔴 정책 규제 완화/속도조절 추세")
else:
    st.sidebar.info("⚪ 중립 또는 정책 변화 관망 중")

# 정책 지수를 기본 시뮬레이션 변수와 연동
auto_apply_policy = st.sidebar.checkbox("실시간 정책 지수를 시뮬레이션 변수에 자동 적용", value=True)

st.sidebar.subheader("⚙️ 시뮬레이션 수동 변수 조절")

base_re_rate = 1.5
if auto_apply_policy:
    # 정책 지수에 따라 신재생 대체 가속도 자동 보정 (-1.0%p ~ +2.0%p)
    policy_impact = (policy_score / 10.0) * 1.5
    calc_re_rate = max(0.1, base_re_rate + policy_impact)
else:
    calc_re_rate = base_re_rate

renewable_adoption_rate = st.sidebar.slider(
    "신재생 에너지 연간 대체 증가율 (%p/년)",
    min_value=0.0, max_value=6.0, 
    value=float(calc_re_rate), step=0.1
)

carbon_tax_base = 50
if auto_apply_policy and "탄소" in country_keyword:
    calc_carbon_tax = max(0, carbon_tax_base + int(policy_score * 5))
else:
    calc_carbon_tax = carbon_tax_base

carbon_tax = st.sidebar.slider(
    "탄소세/탄소배출권 가격 ($/톤 CO2)",
    min_value=0, max_value=200, 
    value=int(calc_carbon_tax), step=5
)

# ---------------------------------------------------------
# 4. Math Simulation Engine
# ---------------------------------------------------------
# 석유 기준 예시 시뮬레이션
reserves = 1730.0      # Gb
annual_demand = 36.5   # Gb/yr
current_price = 75.0   # $/배럴
carbon_intensity = 0.43 # 톤 CO2/배럴

years = np.arange(2026, 2026 + 80)
fossil_demands = []
renewable_shares = []
remaining_reserves = []
fossil_prices = []

curr_res = reserves
curr_fossil_demand = annual_demand
curr_price = current_price
re_share = 20.0

for i, y in enumerate(years):
    re_share = min(95.0, re_share + renewable_adoption_rate)
    net_fossil_growth = (2.0 - renewable_adoption_rate) / 100.0
    curr_fossil_demand = max(0.1, curr_fossil_demand * (1 + net_fossil_growth))
    
    if curr_res > 0:
        actual_cons = min(curr_res, curr_fossil_demand)
        curr_res -= actual_cons
    else:
        actual_cons = 0
        
    scarcity_factor = max(0.01, (curr_res / reserves))
    base_projected_price = curr_price * ((1 + 0.04) ** i) / (scarcity_factor ** 0.35)
    effective_price = base_projected_price + (carbon_tax * carbon_intensity)
    
    fossil_demands.append(actual_cons)
    remaining_reserves.append(curr_res)
    renewable_shares.append(re_share)
    fossil_prices.append(effective_price if curr_res > 0 else np.nan)

df_sim = pd.DataFrame({
    "연도": years,
    "잔존 매장량": remaining_reserves,
    "화석연료 소비량": fossil_demands,
    "신재생 점유율(%)": renewable_shares,
    "체감 가격($)": fossil_prices
})

depletion_year = df_sim[df_sim["잔존 매장량"] <= 0]["연도"].min()
depletion_text = f"{depletion_year}년" if pd.notna(depletion_year) else "80년 이상 유지"

# ---------------------------------------------------------
# 5. Main Dashboard View
# ---------------------------------------------------------
t1, t2 = st.tabs(["📡 실시간 정책 뉴스 & 영향도", "📊 예측 시뮬레이션"])

with t1:
    st.subheader(f"🔍 '{country_keyword}' 관련 최신 정부·기관 정책 소식")
    st.caption("구글 뉴스 RSS를 통해 실시간 트래킹된 뉴스 기사입니다.")
    
    col_news, col_metric = st.columns([2, 1])
    
    with col_news:
        for a in raw_articles:
            st.markdown(f"• [{a['title']}]({a['link']}) — *{a['date']}*")
            
    with col_metric:
        st.metric("수집 기반 정책 지수", f"{policy_score:+.1f}")
        st.metric("자동 보정된 신재생 증가율", f"{renewable_adoption_rate:.1f}%p/년")
        st.metric("자동 보정된 탄소세 설정", f"${carbon_tax}/톤")
        
    st.markdown("---")
    st.info("""
    **💡 정책 반영 알고리즘 설명**
    * 실시간 뉴스 텍스트에서 **'확대·지원·상향'** 등 정책 강화 키워드가 포착되면 정책 지수가 올라가며, 신재생 에너지 전환 속도 시뮬레이션 매개변수를 자동으로 높입니다.
    * 반대로 **'완화·철회·하향'** 키워드가 다수 발견되면 전환 속도가 지연되도록 모델 변수가 보정됩니다.
    """)

with t2:
    m1, m2, m3 = st.columns(3)
    m1.metric("예상 화석연료 고갈 시점", depletion_text)
    m2.metric("2050년 신재생 점유율", f"{df_sim[df_sim['연도']==2050]['신재생 점유율(%)'].values[0]:.1f}%")
    m3.metric("2035년 예상 자원 체감가", f"${df_sim[df_sim['연도']==2035]['체감 가격($)'].values[0]:,.1f}")
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_sim["연도"], y=df_sim["화석연료 소비량"], name="화석연료 소비량", line=dict(color="#E74C3C", width=3)))
    fig.add_trace(go.Scatter(x=df_sim["연도"], y=df_sim["신재생 점유율(%)"], name="신재생 비중(%)", yaxis="y2", line=dict(color="#2ECC71", width=3, dash="dash")))
    fig.update_layout(
        title="정책 반영 시나리오별 에너지 전환 추이",
        yaxis=dict(title="화석연료 소비량 (Gb)"),
        yaxis2=dict(title="신재생 비중 (%)", overlaying="y", side="right")
    )
    st.plotly_chart(fig, use_container_width=True)
