import streamlit as st
from PyPDF2 import PdfReader, PdfWriter
import pandas as pd
import pdfplumber
import tempfile

st.set_page_config(page_title="FBA PDF 排序工具", page_icon="📦", layout="wide")

st.title("📦 FBA PDF 排序工具（按 Excel 条码顺序）")
st.write("上传 Excel + FBA PDF，按条码顺序排序（条码为可提取文本，无 OCR）。")

uploaded_excel = st.file_uploader("上传 Excel（必须包含 label_bar_code 和 carton_code）", type=["xlsx"])
uploaded_pdf = st.file_uploader("上传 FBA PDF 文件", type=["pdf"])


# ============= FBA 条码提取（无 OCR） =============
def extract_fba_barcode(page):
    # 你提供的条码区域坐标
    x, y, w, h = 325, 846, 385, 24
    x1 = x + w
    y1 = y + h

    try:
        crop = page.within_bbox((x, y, x1, y1))
        text = crop.extract_text() or ""
    except:
        return ""

    return text.strip().replace(" ", "").upper()


# ============= 主逻辑 =============
if uploaded_excel and uploaded_pdf:
    
    if st.button("🚀 开始处理"):
        st.info("正在处理 PDF，请稍等…")

        # 读取 Excel
        df = pd.read_excel(uploaded_excel)
        mapping = dict(zip(df["label_bar_code"].astype(str), df["carton_code"]))

        # 保存 PDF
        tmp_pdf = tempfile.NamedTemporaryFile(delete=False).name
        with open(tmp_pdf, "wb") as f:
            f.write(uploaded_pdf.read())

        reader = PdfReader(tmp_pdf)
        pdf = pdfplumber.open(tmp_pdf)

        # 逐页提取条码
        page_to_barcode = {}
        for idx, page in enumerate(pdf.pages):
            barcode = extract_fba_barcode(page)
            page_to_barcode[idx] = barcode
            st.write(f"Page {idx+1} → Detected Barcode: {barcode}")

        # 排序
        writer = PdfWriter()
        used_pages = set()
        failed = []

        for barcode in mapping.keys():
            found = False
            for page_idx, code in page_to_barcode.items():
                if code == barcode and page_idx not in used_pages:
                    writer.add_page(reader.pages[page_idx])
                    used_pages.add(page_idx)
                    found = True
                    break

            if not found:
                failed.append(barcode)

        # 输出结果 PDF
        output_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
        with open(output_file, "wb") as f:
            writer.write(f)

        st.success("🎉 处理完成，点击下载：")
        with open(output_file, "rb") as f:
            st.download_button("📥 下载排序后的 FBA PDF", f, file_name="sorted_fba_output.pdf")

        if failed:
            st.error("以下条码未匹配到 PDF：")
            st.code("\n".join(failed))
