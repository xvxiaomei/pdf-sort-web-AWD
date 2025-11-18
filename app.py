import streamlit as st
import pandas as pd
from PyPDF2 import PdfReader, PdfWriter
import pdfplumber
import re
import tempfile

# ================= 页面设置 =================
st.set_page_config(page_title="PDF 排序工具", page_icon="📄", layout="wide")
st.title("📄 PDF 排序工具（AWD / FBA）")
st.write("上传 Excel + PDF，按条码顺序排序，FBA 自动识别指定区域条码。")

# ================= 类型选择 =================
pdf_type = st.radio("选择 PDF 类型", ["AWD", "FBA"])

# ================= 文件上传 =================
col1, col2 = st.columns(2)
with col1:
    uploaded_excel = st.file_uploader(
        "📊 上传 Excel 映射表（包含 label_bar_code 和 carton_code）",
        type=["xlsx"]
    )
with col2:
    uploaded_pdf = st.file_uploader(
        "📄 上传 PDF 文件",
        type=["pdf"]
    )

# ================= 提取条码函数 =================
def extract_barcode(page, pdf_type):
    """根据 PDF 类型提取条码"""
    if pdf_type == "AWD":
        text = page.extract_text() or ""
        match = re.search(r'\d{18}', text)
        return match.group() if match else ""
    else:  # FBA
        # FBA 纸张 100×100mm -> pt (1mm ≈ 2.83465 pt)
        # 示例条码区域坐标，可根据实际 PDF 调整
        x0, y0 = 50, 260   # 左下角偏移
        crop_width, crop_height = 150, 24
        x1 = x0 + crop_width
        y1 = y0 + crop_height

        # 限制坐标在页面范围内
        x0 = max(0, x0)
        y0 = max(0, y0)
        x1 = min(page.width, x1)
        y1 = min(page.height, y1)

        try:
            crop = page.within_bbox((x0, y0, x1, y1))
            text = crop.extract_text() or ""
        except ValueError:
            text = ""
        return text.strip()

# ================= 处理逻辑 =================
if uploaded_excel and uploaded_pdf:
    if st.button("🚀 开始处理"):
        st.info("正在处理 PDF，请稍等…")

        # 读取 Excel
        df = pd.read_excel(uploaded_excel)
        # 修正列名空格和大小写
        df.columns = df.columns.str.strip().str.lower()
        if 'label_bar_code' not in df.columns or 'carton_code' not in df.columns:
            st.error("Excel 必须包含列：label_bar_code 和 carton_code")
            st.stop()

        mapping = dict(zip(df['label_bar_code'].astype(str), df['carton_code']))

        # 临时保存 PDF
        tmp_pdf_path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
        with open(tmp_pdf_path, "wb") as f:
            f.write(uploaded_pdf.read())

        page_to_barcode = {}
        if pdf_type == "AWD":
            reader = PdfReader(tmp_pdf_path)
            for i, page in enumerate(reader.pages):
                barcode = extract_barcode(page, pdf_type)
                page_to_barcode[i] = barcode
                st.write(f"Page {i+1}: Detected Barcode = {barcode}")
        else:  # FBA
            with pdfplumber.open(tmp_pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    barcode = extract_barcode(page, pdf_type)
                    page_to_barcode[i] = barcode
                    st.write(f"Page {i+1}: Detected Barcode = {barcode}")
            reader = PdfReader(tmp_pdf_path)  # FBA 生成 PDF

        # 排序 PDF
        writer = PdfWriter()
        used_pages = set()
        failed = []

        progress_bar = st.progress(0)
        total = len(mapping)

        for i, barcode in enumerate(mapping.keys()):
            found = False
            for page_idx, code in page_to_barcode.items():
                if code == barcode and page_idx not in used_pages:
                    writer.add_page(reader.pages[page_idx])
                    used_pages.add(page_idx)
                    found = True
                    break
            if not found:
                failed.append(barcode)
            progress_bar.progress((i + 1) / total)

        # 输出 PDF
        output_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
        with open(output_file, "wb") as f:
            writer.write(f)

        st.success(f"🎉 PDF 已处理完成！({pdf_type})")
        with open(output_file, "rb") as f:
            st.download_button(
                "📥 下载排序后的 PDF",
                f,
                file_name=f"sorted_output_{pdf_type}.pdf"
            )

        if failed:
            st.warning("⚠️ 以下条码未匹配到 PDF：")
            st.code("\n".join(failed))
