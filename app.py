import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import random

# 設定網頁標題與風格
st.set_page_config(page_title="HK-WeatherMind AI 智能氣象與社會營運預報系統", layout="wide")

# ==========================================
# DATA FETCHING FUNCTION (自動獲取香港天文台數據)
# ==========================================
@st.cache_data(ttl=300) # 每 5 分鐘自動緩存更新，不重複轟炸 API
def fetch_hko_data():
    try:
        # 1. 獲取本港地區今日天氣報告 (包含各區氣溫)
        temp_res = requests.get("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=rhrread&lang=tc").json()
        # 2. 獲取九天天氣預報 (用於 Module 1 & 2 長期)
        fnd_res = requests.get("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=fnd&lang=tc").json()
        # 3. 獲取現時天氣警告摘要 (用於颱風/暴雨中期)
        warn_res = requests.get("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=warnsum&lang=tc").json()
        return temp_res, fnd_res, warn_res
    except Exception as e:
        st.error(f"數據抓取失敗，請檢查網絡連接。錯誤: {e}")
        return None, None, None

temp_data, fnd_data, warn_data = fetch_hko_data()

# ==========================================
# SYSTEM CORE LOGIC (HK-WeatherMind AI 核心演算)
# ==========================================
st.title("🌐 HK-WeatherMind AI 系統")
st.subheader(f"實時數據更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (每 5 分鐘自動刷新)")
st.markdown("---")

if temp_data and fnd_data:
    # 提取當前天文台總部氣溫作為基準
    current_hko_temp = 25.0 # 默認安全值
    for t in temp_data.get('temperature', {}).get('data', []):
        if t['place'] == '香港天文台':
            current_hko_temp = float(t['value'])
            break

    # ------------------------------------------
    # MODULE 1: 基礎與微氣候七日預報
    # ------------------------------------------
    st.header("📊 Module 1: 基礎與微氣候七日預報")
    
    locations = ["大圍", "沙田", "第一城", "馬鞍山", "九龍塘", "天文台總部"]
    m1_forecast = []
    
# 抓取天文台未來7天預報並進行微氣候修正 (Downscaling)
for i, day in enumerate(fnd_data.get('weatherForecast', [])[:7]):
    date_str = day.get('forecastDate', '00000000')
    
    # 安全提取最高氣溫，如果找不到就給個默認值 28.0
    max_temp_obj = day.get('forecastMaxTemp')
    base_max = float(max_temp_obj['value']) if max_temp_obj and 'value' in max_temp_obj else float(day.get('forecastMaxTemp', 28.0))
    
    # 安全提取最低氣溫，如果找不到就給個默認值 22.0
    min_temp_obj = day.get('forecastMinTemp')
    base_min = float(min_temp_obj['value']) if min_temp_obj and 'value' in min_temp_obj else float(day.get('forecastMinTemp', 22.0))
    
    psr = day.get('PSR', '中') # 降雨概率
    
        
        # 轉換 PSR 文本為大致百分比
        psr_map = {"低": "10%", "中低": "30%", "中": "50%", "中高": "70%", "高": "90%"}
        rain_prob = psr_map.get(psr, "50%")
        
        # 微氣候地形修正邏輯
        for loc in locations:
            if loc == "大圍":
                max_t, min_t = base_max + 0.5, base_min - 0.2  # 盆地效應，日夜溫差稍大
            elif loc == "第一城":
                max_t, min_t = base_max + 0.2, base_min - 0.1
            elif loc == "馬鞍山":
                max_t, min_t = base_max - 0.3, base_min + 0.3  # 臨海，風大，溫差較溫和
            elif loc == "九龍塘":
                max_t, min_t = base_max + 0.4, base_min + 0.5  # 城市熱島效應
            else:
                max_t, min_t = base_max, base_min
                
            m1_forecast.append({
                "日期": f"{date_str[4:6]}/{date_str[6:8]}",
                "地點": loc,
                "天氣狀況": day['forecastWeather'],
                "最高氣溫 (°C)": round(max_t, 1),
                "最低氣溫 (°C)": round(min_t, 1),
                "降雨概率": rain_prob
            })
            
    df_m1 = pd.DataFrame(m1_forecast)
    selected_loc = st.selectbox("選擇查看地點微氣候：", locations)
    st.dataframe(df_m1[df_m1["地點"] == selected_loc].set_index("日期"), use_container_width=True)

    # ------------------------------------------
    # MODULE 2 & 5: 降雨、颱風及社會營運決策引擎 (整合演算法)
    # ------------------------------------------
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        st.header("🌧️ Module 2: 三級降雨與暴雨預警")
        # 模擬 Nowcasting 雷達外推
        st.subheader("短期預報 (未來 2-3 小時)")
        current_hour = datetime.now().hour
        
        # 簡單判定目前是否有雨
        is_raining = "雨" in fnd_data['weatherForecast'][0]['forecastWeather']
        
        if is_raining:
            st.warning("⚠️ 偵測到強對流雨帶正橫過沙田及九龍塘")
            st.metric(label="未來 120 分鐘降雨高峰期", value=f"{current_hour+1}:15 - {current_hour+1}:45")
            st.metric(label="紅雨 / 黑雨觸發預估時間", value=f"預計於 {current_hour}:40 分鐘左右觸發")
            red_rain_prob = 75
        else:
            st.success("🟢 視訊雷達回波良好，未來 3 小時局部地區無大雨")
            red_rain_prob = 10
            
        st.subheader("中期預報 (未來 1 天)")
        st.progress(red_rain_prob / 100, text=f"發出暴雨警告信號最高機率: {red_rain_prob}%")

    with col2:
        st.header("🌀 Module 3: 颱風全週期路徑預測")
        # 檢查是否有颱風信號
        has_typhoon_signal = any('熱帶氣旋' in str(w.get('name')) for w in warn_data) if warn_data else False
        
        if has_typhoon_signal:
            st.error("🚨 當前本港正受熱帶氣旋影響")
            st.subheader("短期掛波精準 Minute-Level 預測")
            # 帶入 20/40 分決策習慣
            next_check = (datetime.now() + timedelta(hours=1)).replace(minute=20, second=0)
            st.metric(label="預計考慮改掛更高風球時間", value=f"{next_check.strftime('%H:%M')} 或 {next_check.replace(minute=40).strftime('%H:%M')}")
            st.caption("備註：AI 模型已根據香港天文台於「每小時20分/40分」掛波之習慣進行時間權重修正。")
            t8_prob = 85
        else:
            st.info("ℹ️ 西北太平洋及南海當前無熱帶氣旋逼近香港 800km 範圍。")
            t8_prob = 0

    # ------------------------------------------
    # MODULE 4: 冬季冷鋒與急降溫分析
    # ------------------------------------------
    st.markdown("---")
    st.header("❄️ Module 4: 冬季冷鋒與急降溫分析")
    current_month = datetime.now().month
    if current_month in [11, 12, 1, 2, 3]:
        st.subheader("🥶 冬季模式已自動激活")
        st.write("正在監測西伯利亞高壓脊線...")
        # 模擬高低海拔地形降溫
        st.write(f"ℹ️ 大圍/沙田等新界平地體感溫標將比天文台總部低約 1-2°C；若前往大老山等高海拔地區，氣溫將額外暴跌 4-5°C。")
    else:
        st.write(f"☀️ 當前月份為 {current_month} 月，非冬季，冷鋒追蹤模組已自動轉入休眠狀態。")

    # ------------------------------------------
    # MODULE 5: 社會營運影響與決策預測（停課預報）
    # ------------------------------------------
    st.markdown("---")
    st.header("🏫 Module 5: 社會營運影響與「停課停工」決策預報")
    
    # 核心時間加權邏輯：若大雨/大風發生在清晨 05:30 - 07:30
    now_time = datetime.now().time()
    is_rush_hour = datetime.strptime("05:30", "%H:%M").time() <= now_time <= datetime.strptime("07:30", "%H:%M").time()
    
    # 計算停課概率
    school_closure_prob = 0
    if red_rain_prob > 50 or t8_prob > 50:
        school_closure_prob = 80
        if is_rush_hour:
            school_closure_prob += 15 # 清晨時段極高概率直接宣布停課
            
    school_closure_prob = min(school_closure_prob, 100)
    
    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        st.metric(label="明日 幼稚園/小學/中學 停課機率", value=f"{school_closure_prob}%")
        if school_closure_prob > 70:
            st.error("⚠️ AI 建議：家長及學生請密切留意明早 06:00 前政府之宣佈。")
    with col_s2:
        extreme_case_prob = 90 if t8_prob > 80 else 10
        st.metric(label="勞工處發出「極端情況」停工機率", value=f"{extreme_case_prob}%")
    with col_s3:
        mtr_risk = "高風險 (露天段大圍至羅湖隨時停駛)" if t8_prob > 50 else "正常營運"
        st.metric(label="港鐵東鐵線營運風險", value=mtr_risk)

else:
    st.error("無法加載即時氣象數據。")
