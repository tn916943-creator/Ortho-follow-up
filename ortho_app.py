import streamlit as st
import google.generativeai as genai
import qrcode
import re
from io import BytesIO

# ─────────────────────────────────────────
# 系統介面設定
# ─────────────────────────────────────────
st.set_page_config(page_title="骨科復健與關懷系統", page_icon="🦴", layout="wide")

st.title("🦴 骨科專屬復健與關懷系統")
st.markdown("輸入病患狀況，自動生成**精簡復健指引**與**專屬關懷信**，並產生 **QR Code** 讓病患掃描帶走。")

# ─────────────────────────────────────────
# 左側邊欄 - 設定與輸入
# ─────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 系統設定")
    api_key = st.text_input("輸入 Gemini API Key", type="password",
                             help="Key 僅用於本次產生，不會被儲存。")

    st.header("📋 基本資訊")
    patient_name = st.text_input("病患姓氏或姓名（選填）", placeholder="例如：陳、王大明")
    age = st.number_input("病患年齡", min_value=1, max_value=120, value=65)
    gender = st.selectbox("性別", ["女性", "男性"])

    st.header("🦴 手術與傷口狀況")
    surgery_part = st.selectbox("手術／受傷部位", [
        # 上肢
        "鎖骨／近端肱骨骨折", "肱骨幹骨折", "遠端肱骨／肘部骨折", "前臂骨折",
        "橈骨遠端骨折（手腕）", "掌指骨折", "大拇指腕掌關節",
        # 下肢與骨盆
        "骨盆骨折", "髖關節骨折－內固定手術", "髖關節骨折－人工關節置換手術",
        "股骨骨折", "臏骨骨折", "近端脛骨骨折", "脛骨幹骨折",
        "膝關節置換／鏡檢", "腳踝／足部骨折",
        # 關節鏡與其他
        "腕關節鏡", "肩關節鏡", "脊椎手術",
        "移除內固定", "清創", "神經減壓", "肌腱縫合", "血管／神經吻合",
        "腫瘤切除／切片", "其他"
    ])
    trauma_type = st.selectbox("受傷原因", [
        "低能量跌倒", "高能量車禍／創傷", "退化性疾病", "運動傷害", "職業／工作傷害"
    ])
    post_op_weeks = st.number_input("術後／受傷週數", min_value=0, max_value=52, value=2)
    sutures_removed = st.radio("傷口拆線狀況", ["未拆線（需保持乾燥）", "已拆線（可碰水）"])

    st.header("🩺 共病與生活習慣（影響癒合）")
    has_osteo  = st.checkbox("骨質疏鬆（T-score < −2.5）")
    has_dm     = st.checkbox("糖尿病（DM）")
    has_ckd    = st.checkbox("慢性腎臟病（CKD）")
    smoke_habit= st.checkbox("有抽菸習慣")

    notes = st.text_area("醫師特別叮嚀（選填）", placeholder="例如：不能提大於 1 公斤重物…")

    generate_btn = st.button("🚀 生成指引與 QR Code", use_container_width=True)

# ─────────────────────────────────────────
# 核心邏輯
# ─────────────────────────────────────────
if generate_btn:
    if not api_key:
        st.error("請先在左側輸入您的 Gemini API Key！")
        st.stop()

    with st.spinner("李天慶醫師助理正在為您撰寫個人化指引…"):

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("models/gemini-2.5-flash")

        # 共病文字
        comorbidities = []
        if has_osteo:   comorbidities.append("骨質疏鬆")
        if has_dm:      comorbidities.append("糖尿病")
        if has_ckd:     comorbidities.append("慢性腎臟病")
        if smoke_habit: comorbidities.append("抽菸習慣")
        comorb_text = "無" if not comorbidities else "、".join(comorbidities)

        # 稱謂推斷（年齡 ≥ 60 → 長輩稱謂）
        name_text = patient_name if patient_name else ""
        if age >= 60:
            honorific = f"{name_text}阿伯" if gender == "男性" else f"{name_text}阿姨"
        else:
            honorific = f"{name_text}先生" if gender == "男性" else f"{name_text}小姐"

        prompt = f"""
你現在是高雄醫學大學附設醫院骨科的「李天慶醫師」。
請以下方病患資料，生成【精簡復健指引】與【關懷信件】。

【病患資料】
稱謂：{honorific}
年齡：{age} 歲 {gender}
手術部位：{surgery_part}
受傷原因：{trauma_type}
術後第幾週：第 {post_op_weeks} 週
傷口狀況：{sutures_removed}
共病／習慣：{comorb_text}
醫師叮嚀：{notes if notes else "無"}

【李天慶醫師說話風格】
1. 親切稱謂：直接用上方推斷的稱謂（{honorific}），不要更改。
2. 台灣醫療語境：使用「回診、復健、主治醫師」，禁用大陸用語（大夫、康復）。
3. 第一段必須肯定病人辛苦（一到兩句即可）。
4. 信中必須提到具體手術部位（{surgery_part}）與術後週數（第 {post_op_weeks} 週），
   讓病患感受到這是專為他寫的。

【精簡要求——這是最重要的規則】
- 復健指引：全部加起來不超過 120 字，用 emoji 條列，每項一行。
  格式固定為：
  ⛔ 絕對禁止（1～2 項）
  ✅ 本週可以做（2～3 項）
  🏃 復健動作（最多 3 個，附次數）
  🚨 立刻回診的警示（2 項）

- 關懷信件：100～150 字，溫暖簡短，病患站在診間門口能一分鐘內讀完。
  結尾署名固定為：「您的骨科主治醫師 李天慶 敬上」

【輸出格式（必須嚴格遵守 XML 標籤）】
<rehab_guide>
（復健指引放這裡）
</rehab_guide>

<care_letter>
（關懷信件放這裡）
</care_letter>
"""

        try:
            response = model.generate_content(prompt)
            output_text = response.text

            rehab_match  = re.search(r'<rehab_guide>(.*?)</rehab_guide>',   output_text, re.DOTALL)
            letter_match = re.search(r'<care_letter>(.*?)</care_letter>',   output_text, re.DOTALL)

            rehab_text  = rehab_match.group(1).strip()  if rehab_match  else "⚠️ 解析失敗，請重試。\n\n" + output_text
            letter_text = letter_match.group(1).strip() if letter_match else "⚠️ 解析失敗，請重試。\n\n" + output_text

            tab1, tab2, tab3 = st.tabs(["📋 復健指引", "💌 關懷信件", "📱 QR Code（給病患掃描）"])

            with tab1:
                st.markdown(rehab_text)

            with tab2:
                st.markdown(letter_text)

            with tab3:
                st.info("💡 請讓病患掃描下方 QR Code，即可將內容存入手機。")

                # QR Code 只放關懷信件（字數精簡，掃描成功率高）
                qr_content = f"【李天慶醫師專屬復健指引】\n{rehab_text}\n\n【醫師關懷信】\n{letter_text}"

                # 超過 800 字則截斷並提示
                if len(qr_content) > 800:
                    qr_content = qr_content[:800] + "\n…（請向護理站索取完整版）"

                qr = qrcode.QRCode(
                    version=None,          # 自動選擇最小版本
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=8,
                    border=4,
                )
                qr.add_data(qr_content)
                qr.make(fit=True)

                img = qr.make_image(fill_color="black", back_color="white")
                buf = BytesIO()
                img.save(buf, format="PNG")
                st.image(buf.getvalue(), width=320)

                # 同時提供純文字複製區
                with st.expander("📄 展開純文字（可複製）"):
                    st.text(qr_content)

        except Exception as e:
            st.error(f"發生錯誤：{e}\n請確認 API Key 是否正確，或目前是否有可用額度。")
