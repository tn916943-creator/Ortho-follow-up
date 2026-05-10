
import streamlit as st
import google.generativeai as genai
import qrcode
from io import BytesIO

# 系統介面設定
st.set_page_config(page_title="骨科復健與關懷系統", page_icon="🦴", layout="wide")

st.title("🦴 骨科專屬復健與關懷系統 (診間單向推播版)")
st.markdown("輸入病患狀況，自動生成**復健指引**與**專屬關懷信**，並直接產生 **QR Code** 讓病患掃描帶走。")

# 左側邊欄 - 設定與輸入
with st.sidebar:
    st.header("⚙️ 系統設定")
    api_key = st.text_input("輸入 Gemini API Key", type="password")

    st.header("📋 基本資訊")
    age = st.number_input("病患年齡", min_value=1, max_value=120, value=65)
    gender = st.selectbox("性別", ["女性", "男性"])

    st.header("🦴 手術與傷口狀況")
    surgery_part = st.selectbox("手術/受傷部位", [
        "橈骨遠端骨折 (手腕)", 
        "大拇指腕掌關節", 
        "髖關節骨折", 
        "膝關節置換/鏡檢", 
        "脊椎手術", 
        "腳踝/足部骨折",
        "其他"
    ])
    trauma_type = st.selectbox("受傷原因", ["低能量跌倒", "高能量車禍/創傷", "退化性疾病", "運動傷害"])
    post_op_weeks = st.number_input("術後/受傷週數", min_value=0, max_value=52, value=2)
    sutures_removed = st.radio("傷口拆線狀況", ["未拆線 (需保持乾燥)", "已拆線 (可碰水)"])

    st.header("🩺 共病與生活習慣 (影響癒合)")
    has_osteo = st.checkbox("有骨質疏鬆 (T-score < -2.5)")
    has_dm = st.checkbox("有糖尿病 (DM)")
    has_ckd = st.checkbox("有慢性腎臟病 (CKD)")
    smoke_habit = st.checkbox("有抽菸習慣")

    notes = st.text_area("其他特別叮嚀 (選填)", placeholder="例如：可拿筷子、不能提大於1公斤重物...")

    generate_btn = st.button("🚀 生成指引與 QR Code", use_container_width=True)

# 核心邏輯
if generate_btn:
    if not api_key:
        st.error("請先在左側輸入您的 Gemini API Key！")
    else:
        with st.spinner("AI 醫師助理正在綜合評估共病風險並撰寫專屬內容..."):
            genai.configure(api_key=api_key)

# 使用穩定的 Gemini 1.5 Flash 免費版
model = genai.GenerativeModel("gemini-1.5-flash")

            # 將勾選的共病轉換為文字敘述
            comorbidities = []
            if has_osteo: comorbidities.append("骨質疏鬆")
            if has_dm: comorbidities.append("糖尿病")
            if has_ckd: comorbidities.append("慢性腎臟病")
            if smoke_habit: comorbidities.append("抽菸習慣")

            comorb_text = "無明顯影響癒合之共病" if not comorbidities else "、".join(comorbidities)

            # 設計 System Prompt (更精密的臨床人設與判斷)
            prompt = f'''
            你是一位台灣醫學中心專業且溫暖的骨科醫師。請根據以下病患資料，生成一份高度個人化的復健指引與關懷信。

            【病患臨床資料】
            基本資料：{age}歲 {gender}
            部位：{surgery_part}
            原因：{trauma_type}
            術後進度：第 {post_op_weeks} 週
            傷口狀況：{sutures_removed}
            影響癒合之共病/習慣：{comorb_text}
            醫師特別叮嚀：{notes}

            【臨床推理要求】
            1. 必須考慮「共病」對癒合的影響。若有糖尿病，必須提醒控制血糖對傷口/骨頭癒合的重要性；若有抽菸，必須提醒尼古丁會延緩骨頭癒合；若有骨鬆，必須提醒防跌。
            2. 必須考慮「拆線狀況」。若未拆線，必須強調傷口不可碰水與觀察紅腫熱痛。
            3. 若為高能量創傷，需適度安撫病患創傷後的心理壓力。

            【輸出格式要求】
            請嚴格輸出兩個段落，並用「---」分隔：

            第一部分：復健與照護指引 (標題：📋 專屬復健與照護指引)
            - 本週允許的日常活動與禁忌。
            - 居家復健動作 (請具體描述動作與建議次數)。
            - 傷口照護與共病管理提醒 (融合前述的 DM/CKD/抽菸/拆線等狀態)。
            - 需立即回診的警示徵象。

            ---
            第二部分：專屬關懷信件 (標題：💌 醫師關懷信)
            - 語氣必須溫暖、親切，稱呼長輩為伯伯/阿姨，年輕人為先生/小姐。
            - 使用台灣醫療用語 (回診、復健、主治醫師、血糖控制)。
            - 將冷冰冰的醫囑轉化為關心的話語。例如「因為您有糖尿病，我們更要注意傷口...」。
            - 結尾署名：「您的骨科醫師 關心您」
            '''

            try:
                response = model.generate_content(prompt)
                output_text = response.text

                parts = output_text.split("---")
                rehab_text = parts[0].strip() if len(parts) > 0 else output_text
                letter_text = parts[1].strip() if len(parts) > 1 else "生成格式錯誤，請再試一次。"

                tab1, tab2, tab3 = st.tabs(["📋 復健指引", "💌 關懷信件", "📱 給病人掃描的 QR Code"])

                with tab1:
                    st.markdown(rehab_text)
                with tab2:
                    st.markdown(letter_text)
                with tab3:
                    st.warning("💡 請病人掃描下方 QR Code 即可將文字存入手機中。")
                    combined_text = f"{rehab_text}\n\n{letter_text}"

                    qr = qrcode.QRCode(version=1, box_size=10, border=4)
                    qr.add_data(combined_text[:800])
                    qr.make(fit=True)

                    img = qr.make_image(fill_color="black", back_color="white")
                    buf = BytesIO()
                    img.save(buf, format="PNG")
                    st.image(buf.getvalue(), width=350)

            except Exception as e:
                # 備用方案
                st.error(f"發生錯誤：{e}\n正在嘗試切換備用模型...")
                try:
fallback_model = genai.GenerativeModel("gemini-1.5-flash")
                    response = fallback_model.generate_content(prompt)
                    output_text = response.text
                    parts = output_text.split("---")
                    rehab_text = parts[0].strip() if len(parts) > 0 else output_text
                    letter_text = parts[1].strip() if len(parts) > 1 else "生成錯誤。"

                    tab1, tab2, tab3 = st.tabs(["📋 復健指引", "💌 關懷信件", "📱 QR Code"])
                    with tab1: st.markdown(rehab_text)
                    with tab2: st.markdown(letter_text)
                    with tab3:
                        combined_text = f"{rehab_text}\n\n{letter_text}"
                        qr = qrcode.QRCode(version=1, box_size=10, border=4)
                        qr.add_data(combined_text[:800])
                        qr.make(fit=True)
                        img = qr.make_image(fill_color="black", back_color="white")
                        buf = BytesIO()
                        img.save(buf, format="PNG")
                        st.image(buf.getvalue(), width=350)
                except Exception as fallback_e:
                    st.error("模型連線失敗，請檢查 API Key 是否正確。")
