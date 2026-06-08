import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as genai
import qrcode
import re
from io import BytesIO

# ─────────────────────────────────────────
# 系統介面設定
# ─────────────────────────────────────────
st.set_page_config(page_title="骨科復健與關懷系統", page_icon="🦴", layout="wide")

# ─────────────────────────────────────────
# 密碼保護（Streamlit Cloud 版）
# 密碼存在 Streamlit Cloud 後台的 Secrets，不寫死在程式裡
# ─────────────────────────────────────────
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.title("🦴 骨科復健與關懷系統")
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### 🔐 請輸入診間密碼")
        pwd = st.text_input("密碼", type="password", placeholder="請向李天慶醫師索取")
        if st.button("登入", use_container_width=True):
            if pwd == st.secrets["APP_PASSWORD"]:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("密碼錯誤，請重新輸入。")
    return False

if not check_password():
    st.stop()

# ─────────────────────────────────────────
# 主畫面（通過密碼後才顯示）
# ─────────────────────────────────────────
st.title("🦴 骨科專屬復健與關懷系統")
st.markdown("輸入病患狀況，自動生成**精簡復健指引**與**專屬關懷信**，並產生 **QR Code** 讓病患掃描帶走。")

# 從 Streamlit Cloud Secrets 讀取 API Key，不需要使用者輸入
api_key = st.secrets["GEMINI_API_KEY"]

# ─────────────────────────────────────────
# 左側邊欄 - 病患資料輸入
# ─────────────────────────────────────────
with st.sidebar:
    st.header("📋 基本資訊")
    patient_name = st.text_input("病患姓氏（選填）", placeholder="例如：陳、王")
    age = st.number_input("病患年齡", min_value=1, max_value=120, value=65)
    gender = st.selectbox("性別", ["女性", "男性"])

    st.header("🦴 手術與傷口狀況")
    surgery_part = st.selectbox("手術／受傷部位", [
        # 上肢
        "鎖骨骨折", "近端肱骨骨折",
        "肱骨幹骨折", "遠端肱骨／肘部骨折", "前臂骨折",
        "橈骨遠端骨折（手腕）", "掌指骨折",
        "大拇指腕掌關節", "拇指掌指關節鏡",
        # 下肢與骨盆
        "骨盆骨折", "髖關節骨折－內固定手術", "髖關節骨折－人工關節置換手術",
        "股骨骨折", "臏骨骨折", "近端脛骨骨折", "脛骨幹骨折",
        "膝關節置換手術", "膝關節鏡", "腳踝／足部骨折",
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
    has_osteo   = st.checkbox("骨質疏鬆（T-score < −2.5）")
    has_dm      = st.checkbox("糖尿病（DM）")
    has_ckd     = st.checkbox("慢性腎臟病（CKD）")
    smoke_habit = st.checkbox("有抽菸習慣")

    notes = st.text_area("醫師特別叮嚀（選填）", placeholder="例如：不能提大於 1 公斤重物…")

    generate_btn = st.button("🚀 生成指引與 QR Code", use_container_width=True)

    # 登出按鈕
    st.markdown("---")
    if st.button("🚪 登出", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

# ─────────────────────────────────────────
# 核心邏輯
# ─────────────────────────────────────────
if generate_btn:
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

        # 稱謂推斷（年齡 ≥ 70 → 長輩稱謂）
        name_text = patient_name if patient_name else ""
        if age >= 70:
            honorific = f"{name_text}伯伯" if gender == "男性" else f"{name_text}阿姨"
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
  結尾署名固定為：「您的骨科醫師 李天慶」

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

            rehab_match  = re.search(r'<rehab_guide>(.*?)</rehab_guide>', output_text, re.DOTALL)
            letter_match = re.search(r'<care_letter>(.*?)</care_letter>', output_text, re.DOTALL)

            rehab_text  = rehab_match.group(1).strip()  if rehab_match  else "⚠️ 解析失敗，請重試。\n\n" + output_text
            letter_text = letter_match.group(1).strip() if letter_match else "⚠️ 解析失敗，請重試。\n\n" + output_text

            # 將結果存入 session_state，供後續審閱與 QR Code 使用
            st.session_state["rehab_text"]  = rehab_text
            st.session_state["letter_text"] = letter_text
            st.session_state["qr_approved"] = False  # 每次重新生成都需重新審閱

        except Exception as e:
            st.error(f"發生錯誤：{e}\n請確認 API Key 是否正確，或目前是否有可用額度。")

# ─────────────────────────────────────────
# 審閱區（生成後才顯示）
# ─────────────────────────────────────────
if "rehab_text" in st.session_state and "letter_text" in st.session_state:

    st.markdown("---")
    st.subheader("🩺 醫師審閱區｜請確認內容後再釋出給病患")
    st.caption("您可以直接在下方文字框修改 AI 產出的內容，確認無誤後再按「核准釋出」。")

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("**💌 關懷信件**")
        edited_letter = st.text_area(
            label="關懷信件（可直接修改）",
            value=st.session_state["letter_text"],
            height=220,
            label_visibility="collapsed"
        )

    with col_right:
        st.markdown("**📋 復健指引**")
        edited_rehab = st.text_area(
            label="復健指引（可直接修改）",
            value=st.session_state["rehab_text"],
            height=220,
            label_visibility="collapsed"
        )

    st.markdown("&nbsp;")

    approve_btn = st.button("✅ 內容確認無誤，核准釋出 QR Code", type="primary", use_container_width=True)

    if approve_btn:
        st.session_state["qr_approved"]     = True
        st.session_state["final_letter"]    = edited_letter
        st.session_state["final_rehab"]     = edited_rehab

    # ─────────────────────────────────────────
    # QR Code 區（核准後才顯示）
    # ─────────────────────────────────────────
    if st.session_state.get("qr_approved"):

        st.markdown("---")
        st.subheader("📱 病患專屬 QR Code")
        st.success("✅ 醫師已核准，此內容可交給病患。")

        final_letter = st.session_state["final_letter"]
        final_rehab  = st.session_state["final_rehab"]

        tab1, tab2, tab3, tab4 = st.tabs(["💌 關懷信件（最終版）", "📋 復健指引（最終版）", "📱 QR Code", "🖨️ 列印衛教單"])

        with tab1:
            st.markdown(final_letter)

        with tab2:
            st.markdown(final_rehab)

        with tab3:
            st.info("💡 請讓病患掃描下方 QR Code，即可將內容存入手機。")

            qr_content = f"【李天慶醫師關懷信】\n{final_letter}\n\n【專屬復健指引】\n{final_rehab}"

            if len(qr_content) > 800:
                qr_content = qr_content[:800] + "\n…（請向護理站索取完整版）"

            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=8,
                border=4,
            )
            qr.add_data(qr_content)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            buf = BytesIO()
            img.save(buf, format="PNG")

            col_qr, col_text = st.columns([1, 1])
            with col_qr:
                st.image(buf.getvalue(), width=280)
            with col_text:
                st.markdown("**📄 純文字（可複製給病患）**")
                st.text(qr_content)

        with tab4:
            st.info("💡 下方為列印預覽，點選「🖨️ 列印」按鈕即可印出給病患。")

            rehab_html = final_rehab.replace("\n", "<br>")
            letter_html = final_letter.replace("\n", "<br>")

            print_html = f"""
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<style>
  body {{
    font-family: "Noto Sans TC", "Microsoft JhengHei", sans-serif;
    max-width: 640px;
    margin: 24px auto;
    padding: 0 20px;
    color: #1a1a1a;
    font-size: 14px;
    line-height: 1.8;
  }}
  .header {{
    text-align: center;
    border-bottom: 2px solid #1a3c6e;
    padding-bottom: 10px;
    margin-bottom: 20px;
  }}
  .header h2 {{ color: #1a3c6e; margin: 0 0 4px 0; font-size: 18px; }}
  .header p  {{ margin: 0; color: #555; font-size: 12px; }}
  .section   {{ margin-bottom: 20px; }}
  .section-title {{
    font-size: 14px; font-weight: bold; color: #1a3c6e;
    border-left: 4px solid #1a3c6e;
    padding-left: 8px; margin-bottom: 8px;
  }}
  .content {{
    background: #f8f9fb; border-radius: 6px;
    padding: 12px 16px; white-space: pre-wrap;
  }}
  .footer {{
    text-align: center; font-size: 11px; color: #888;
    border-top: 1px solid #ddd; padding-top: 10px; margin-top: 24px;
  }}
  .print-btn {{
    display: block; width: 100%; padding: 10px;
    background: #1a3c6e; color: white; border: none;
    border-radius: 6px; font-size: 15px; cursor: pointer;
    margin-bottom: 20px;
  }}
  @media print {{ .print-btn {{ display: none; }} }}
</style>
</head>
<body>
  <button class="print-btn" onclick="window.print()">🖨️ 列印此衛教單</button>

  <div class="header">
    <h2>🏥 高雄醫學大學附設醫院 骨科部</h2>
    <p>病患專屬衛教單｜李天慶醫師</p>
  </div>

  <div class="section">
    <div class="section-title">💌 醫師關懷信</div>
    <div class="content">{letter_html}</div>
  </div>

  <div class="section">
    <div class="section-title">📋 專屬復健指引</div>
    <div class="content">{rehab_html}</div>
  </div>

  <div class="footer">
    本衛教單由 AI 輔助生成，經李天慶醫師審閱確認，請以主治醫師指示為準。<br>
    骨科門診諮詢：(07) 312-1101 轉 7841
  </div>
</body>
</html>
"""
            components.html(print_html, height=700, scrolling=True)
