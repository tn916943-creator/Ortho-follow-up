
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
    st.markdown("[👉 點此取得免費 API Key](https://aistudio.google.com/app/apikey)")

    st.header("📋 病患資訊")
    age = st.number_input("病患年齡", min_value=1, max_value=120, value=65)
    gender = st.selectbox("性別", ["女性", "男性"])
    surgery_part = st.selectbox("手術/受傷部位", [
        "橈骨遠端骨折 (手腕)", 
        "大拇指腕掌關節", 
        "髖關節", 
        "膝關節", 
        "脊椎", 
        "其他"
    ])
    post_op_weeks = st.number_input("術後/受傷週數", min_value=0, max_value=52, value=2)
    has_osteo = st.checkbox("具有骨質疏鬆 (T-score < -2.5)")
    notes = st.text_area("其他特別叮嚀 (選填)", placeholder="例如：下週需拆線、可以開始拿輕物...")

    generate_btn = st.button("🚀 生成指引與 QR Code", use_container_width=True)

# 核心邏輯
if generate_btn:
    if not api_key:
        st.error("請先在左側輸入您的 Gemini API Key！")
    else:
        with st.spinner("AI 醫師助理正在為您撰寫專屬內容..."):
            # 設定 Gemini API
            genai.configure(api_key=api_key)
            # 使用 Gemini 1.5 Flash (速度極快且免費額度極高)
            model = genai.GenerativeModel("gemini-1.5-flash")

            # 設計 System Prompt (人設與輸出格式)
            prompt = f'''
            你是一位台灣醫學中心專業且溫暖的骨科醫師。請根據以下病患資料，生成兩部分內容：

            【病患資料】
            年齡/性別：{age}歲 {gender}
            部位：{surgery_part}
            術後週數：第 {post_op_weeks} 週
            骨鬆狀況：{'有骨質疏鬆' if has_osteo else '無骨質疏鬆'}
            特別叮嚀：{notes}

            【輸出格式要求】
            請嚴格輸出兩個段落，並用「---」分隔：

            第一部分：復健與照護指引 (標題：📋 專屬復健與照護指引)
            - 條列式說明本週可進行的活動。
            - 每日復健動作與次數。
            - 需立即回診的警示徵象。

            ---
            第二部分：專屬關懷信件 (標題：💌 醫師關懷信)
            - 語氣必須溫暖、親切，稱呼長輩為伯伯/阿姨，年輕人為先生/小姐。
            - 必須使用台灣醫療用語 (回診、復健、主治醫師)。
            - 信中要自然帶到病人的部位、週數與骨鬆狀況的叮嚀。
            - 結尾署名：「您的骨科醫師 關心您」
            '''

            try:
                response = model.generate_content(prompt)
                output_text = response.text

                # 拆分兩大區塊
                parts = output_text.split("---")
                rehab_text = parts[0].strip() if len(parts) > 0 else output_text
                letter_text = parts[1].strip() if len(parts) > 1 else "生成格式錯誤，請再試一次。"

                # 建立 UI 頁籤
                tab1, tab2, tab3 = st.tabs(["📋 復健指引", "💌 關懷信件", "📱 給病人掃描的 QR Code"])

                with tab1:
                    st.success("這份指引可以讓病人清楚知道本週該做什麼。")
                    st.markdown(rehab_text)
                with tab2:
                    st.info("這封信帶有您的專屬人設，提升醫病信任感。")
                    st.markdown(letter_text)
                with tab3:
                    st.warning("💡 請病人直接拿出手機相機，掃描下方 QR Code 即可將文字存入手機中。")

                    # 將結果合併，並產生 QR Code
                    combined_text = f"{rehab_text}\n\n{letter_text}"

                    # MVP 測試版：直接將文字編碼進 QR Code (限 800 字以保證掃描成功率)
                    qr = qrcode.QRCode(version=1, box_size=10, border=4)
                    qr.add_data(combined_text[:800])
                    qr.make(fit=True)

                    img = qr.make_image(fill_color="black", back_color="white")
                    buf = BytesIO()
                    img.save(buf, format="PNG")

                    st.image(buf.getvalue(), width=350)
                    if len(combined_text) > 800:
                        st.caption("註：目前測試版為純文字 QR Code。未來正式上線時，將自動生成短網址，不受字數限制。")

            except Exception as e:
                st.error(f"發生錯誤：{e}")
