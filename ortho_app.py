import streamlit as st
import google.generativeai as genai
import qrcode
import re
from io import BytesIO

# 系統介面設定
st.set_page_config(page_title="骨科復健與關懷系統", page_icon="🦴", layout="wide")

st.title("🦴 骨科專屬復健與關懷系統 (診間推播版)")
st.markdown("輸入病患狀況，自動生成**復健指引**與**專屬關懷長信**，並直接產生 **QR Code** 讓病患掃描帶走。")

# 左側邊欄 - 設定與輸入
with st.sidebar:
    st.header("⚙️ 系統設定")
    api_key = st.text_input("輸入 Gemini API Key", type="password")

    st.header("📋 基本資訊")
    patient_name = st.text_input("病患姓氏或姓名 (選填)", placeholder="例如：陳, 王大明")
    age = st.number_input("病患年齡", min_value=1, max_value=120, value=65)
    gender = st.selectbox("性別", ["女性", "男性"])

    st.header("🦴 手術與傷口狀況")
    surgery_part = st.selectbox("手術/受傷部位", [
        # 上肢
        "鎖骨/近端肱骨骨折", "肱骨幹骨折", "遠端肱骨/肘部骨折", "前臂骨折", 
        "橈骨遠端骨折 (手腕)", "掌指骨折", "大拇指腕掌關節",
        # 下肢與骨盆
        "骨盆骨折", "髖關節骨折 - 內固定手術", "髖關節骨折 - 人工關節置換手術", 
        "股骨骨折", "臏骨骨折", "近端脛骨骨折", "脛骨幹骨折", 
        "膝關節置換/鏡檢", "腳踝/足部骨折",
        # 關節鏡與其他
        "腕關節鏡", "肩關節鏡", "脊椎手術", 
        "移除內固定", "清創", "神經減壓", "肌腱縫合", "血管/神經吻合", 
        "腫瘤切除/切片", "其他"
    ])
    trauma_type = st.selectbox("受傷原因", ["低能量跌倒", "高能量車禍/創傷", "退化性疾病", "運動傷害", "職業/工作傷害"])
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
        with st.spinner("AI 醫師助理正在綜合評估臨床變數，為您撰寫專屬長信與指引..."):
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("models/gemini-2.5-flash")

            # 將勾選的共病轉換為文字敘述
            comorbidities = []
            if has_osteo: comorbidities.append("骨質疏鬆")
            if has_dm: comorbidities.append("糖尿病")
            if has_ckd: comorbidities.append("慢性腎臟病")
            if smoke_habit: comorbidities.append("抽菸習慣")

            comorb_text = "無明顯影響癒合之共病" if not comorbidities else "、".join(comorbidities)
            name_text = patient_name if patient_name else "病患"

            # 設計 System Prompt (加入 XML 標籤防呆，並要求加長信件)
            prompt = f'''
            你是一位台灣醫學中心專業且溫暖的骨科醫師。請根據以下病患資料，生成一份高度個人化的復健指引與關懷信。

            【病患臨床資料】
            姓名：{name_text}
            基本資料：{age}歲 {gender}
            部位：{surgery_part}
            原因：{trauma_type}
            術後進度：第 {post_op_weeks} 週
            傷口狀況：{sutures_removed}
            影響癒合之共病/習慣：{comorb_text}
            醫師特別叮嚀：{notes}

            【臨床推理與寫作要求】
            1. 復健指引：需精準、條列式。包含本週日常活動與禁忌、居家復健動作(次數)、傷口與共病管理(DM/CKD/抽菸/防跌)、立即回診徵象。
            2. 關懷信件：
               - 必須是一封字數至少 250~350 字的長信。
               - 請根據姓名與年齡加上適當尊稱（如：陳伯伯、王小姐）。
               - 請詳細說明「目前這週數的組織癒合狀況」，並解釋為何要遵守指引中的禁忌，讓病患了解「為什麼要這麼做」。
               - 針對受傷原因給予同理心（如：安撫車禍驚嚇、體恤職業傷害的焦慮、鼓勵退化性疾病的復健）。
               - 將冷冰冰的醫囑(如戒菸、控糖)轉化為溫暖的鼓勵。
               - 結尾署名：「您的骨科醫師 關心您」。

            【嚴格輸出格式】
            請務必使用以下 XML 標籤包覆兩部分的內容，方便系統正確擷取：

            <rehab_guide>
            (這裡放入排版好的條列式復健指引)
            </rehab_guide>

            <care_letter>
            (這裡放入豐富溫暖的關懷長信)
            </care_letter>
            '''

            try:
                response = model.generate_content(prompt)
                output_text = response.text

                # 使用正則表達式精準擷取
                rehab_match = re.search(r'<rehab_guide>(.*?)</rehab_guide>', output_text, re.DOTALL)
                letter_match = re.search(r'<care_letter>(.*?)</care_letter>', output_text, re.DOTALL)

                rehab_text = rehab_match.group(1).strip() if rehab_match else "無法正確解析復健指引，請重試。\n" + output_text
                letter_text = letter_match.group(1).strip() if letter_match else "無法正確解析關懷信件，請重試。\n" + output_text

                tab1, tab2, tab3 = st.tabs(["📋 復健指引", "💌 關懷信件", "📱 給病人掃描的 QR Code"])

                with tab1:
                    st.markdown(rehab_text)
                with tab2:
                    st.markdown(letter_text)
                with tab3:
                    st.warning("💡 請病人掃描下方 QR Code 即可將文字存入手機中。")
                    combined_text = f"【專屬復健指引】\n{rehab_text}\n\n【醫師關懷信】\n{letter_text}"

                    qr = qrcode.QRCode(version=1, box_size=10, border=4)
                    qr.add_data(combined_text[:1500]) # 放寬字數限制
                    qr.make(fit=True)

                    img = qr.make_image(fill_color="black", back_color="white")
                    buf = BytesIO()
                    img.save(buf, format="PNG")
                    st.image(buf.getvalue(), width=350)

            except Exception as e:
                st.error(f"發生錯誤：{e}\n請檢查 API Key 是否正確或是否有免費額度。")
