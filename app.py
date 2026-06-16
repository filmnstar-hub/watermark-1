import io
import os
from datetime import datetime
import streamlit as st
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib.colors import Color

# ── 폰트 등록 ──
pdfmetrics.registerFont(UnicodeCIDFont('HYGothic-Medium'))
pdfmetrics.registerFont(UnicodeCIDFont('HYSMyeongJo-Medium'))

COLOR_MAP = {
    '🔴 빨간색 — 계약서·기밀': (0.80, 0.00, 0.00),
    '🔵 파란색 — 초안 배포':   (0.00, 0.33, 0.80),
    '🟣 보라색 — 시나리오':    (0.38, 0.00, 0.80),
    '🟢 초록색 — 검토용':      (0.10, 0.47, 0.23),
    '⚫ 검정색':               (0.07, 0.07, 0.07),
    '🟡 골드 — KO Pictures':  (0.78, 0.56, 0.04),
}

FONT_MAP = {
    '고딕체': 'HYGothic-Medium',
    '명조체': 'HYSMyeongJo-Medium',
}

# ── 워터마크 생성 ──
def make_wm(text, sub, pw, ph, font, size, angle, opacity, color_rgb, mode):
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(pw, ph))
    r, g, b = color_rgb
    fill = Color(r, g, b, alpha=opacity / 100)
    sub_sz = size * 0.35

    def stamp(cx, cy):
        c.saveState()
        c.translate(cx, cy)
        c.rotate(angle)
        c.setFillColor(fill)
        c.setFont(font, size)
        tw = c.stringWidth(text, font, size)
        c.drawString(-tw / 2, 0, text)
        if sub:
            c.setFont(font, sub_sz)
            sw = c.stringWidth(sub, font, sub_sz)
            c.drawString(-sw / 2, -size * 0.75, sub)
        c.restoreState()

    if mode == '전체 반복 타일':
        gx, gy = pw / 3, ph / 4
        for row in range(5):
            for col in range(4):
                stamp(gx * col - gx * 0.5, gy * row - gy * 0.5)
    elif mode == '대각 3개':
        stamp(pw * 0.2, ph * 0.8)
        stamp(pw * 0.5, ph * 0.5)
        stamp(pw * 0.8, ph * 0.2)
    else:
        stamp(pw / 2, ph / 2)

    c.save()
    buf.seek(0)
    return buf

def apply_watermark(pdf_bytes, text, sub, font, size, angle, opacity, color_rgb, mode, layer):
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    for page in reader.pages:
        pw = float(page.mediabox.width)
        ph = float(page.mediabox.height)
        wm_buf = make_wm(text, sub, pw, ph, font, size, angle, opacity, color_rgb, mode)
        wm_page = PdfReader(wm_buf).pages[0]
        if layer == '글 앞':
            page.merge_page(wm_page)
            writer.add_page(page)
        else:
            wm_page.merge_page(page)
            writer.add_page(wm_page)
    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    return out.read()

# ── UI ──
st.set_page_config(page_title='KO Pictures 워터마크', page_icon='🎬', layout='centered')

st.markdown("""
<style>
[data-testid="stAppViewContainer"]{background:#0f0f0f;}
[data-testid="stSidebar"]{background:#1a1a1a;}
h1{color:#c8a96e !important;font-size:18px !important;letter-spacing:.1em;}
.sub{color:#555;font-size:12px;margin-top:-12px;margin-bottom:20px;}
div[data-testid="stFileUploader"] label{color:#999;}
</style>
""", unsafe_allow_html=True)

st.markdown('# KO PICTURES / 워터마크 편집기')
st.markdown('<p class="sub">PDF에 수신자 워터마크를 삽입합니다</p>', unsafe_allow_html=True)

# ── PDF 업로드 ──
st.subheader('📄 PDF 파일')
pdf_file = st.file_uploader('PDF를 선택하세요', type='pdf', label_visibility='collapsed')

# ── 수신자 ──
st.subheader('👤 수신자')
recip_input = st.text_area(
    '수신자 목록',
    placeholder='한 줄에 한 명씩 입력\n예)\n무술감독 권귀덕\n감독 홍길동\n제작부 김철수',
    height=120,
    label_visibility='collapsed'
)
sub_text = st.text_input('서브 문구', value='개인 수령 문서 · 무단 배포 금지')

# ── 스타일 ──
st.subheader('🎨 스타일')
col1, col2 = st.columns(2)
with col1:
    font_label = st.selectbox('폰트', list(FONT_MAP.keys()))
    color_label = st.selectbox('색상', list(COLOR_MAP.keys()))
    mode = st.selectbox('배치', ['전체 반복 타일', '대각 3개', '가운데 1개'])
with col2:
    size = st.slider('크기', 16, 100, 48)
    angle = st.slider('각도', -90, 90, -40)
    opacity = st.slider('불투명도', 3, 60, 15)
    layer = st.selectbox('레이어', ['글 뒤 (권장)', '글 앞'])

# ── 저장 ──
st.markdown('---')

if st.button('✅ 워터마크 저장', type='primary', use_container_width=True):
    if not pdf_file:
        st.error('PDF 파일을 업로드하세요.')
    elif not recip_input.strip():
        st.error('수신자를 입력하세요.')
    else:
        recips = [r.strip() for r in recip_input.strip().splitlines() if r.strip()]
        font = FONT_MAP[font_label]
        color_rgb = COLOR_MAP[color_label]
        layer_val = '글 앞' if '글 앞' in layer else '글 뒤'
        pdf_bytes = pdf_file.read()
        base_name = pdf_file.name.replace('.pdf', '').replace('.PDF', '')
        today = datetime.now().strftime('%Y%m%d')

        progress = st.progress(0)
        status = st.empty()

        results = []
        for i, recip in enumerate(recips):
            status.info(f'처리 중… {recip} ({i+1}/{len(recips)})')
            result = apply_watermark(
                pdf_bytes, recip, sub_text,
                font, size, angle, opacity, color_rgb, mode, layer_val
            )
            safe = recip.replace('/', '-').replace('\\', '-')
            fname = f'{base_name}_[{safe}]_{today}.pdf'
            results.append((fname, result))
            progress.progress((i + 1) / len(recips))

        status.empty()
        progress.empty()
        st.success(f'✅ {len(recips)}명 처리 완료! 아래 버튼으로 다운로드하세요.')

        if len(results) == 1:
            # 1명: PDF 직접 다운로드
            fname, data = results[0]
            st.download_button(
                label=f'⬇️ {fname} 다운로드',
                data=data,
                file_name=fname,
                mime='application/pdf',
            )
        else:
            # 여러 명: ZIP으로 묶어서 다운로드
            import zipfile
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
                for fname, data in results:
                    zf.writestr(fname, data)
            zip_buf.seek(0)
            zip_name = f'{base_name}_워터마크_{today}.zip'
            st.download_button(
                label=f'⬇️ 전체 ZIP 다운로드 ({len(results)}명)',
                data=zip_buf.read(),
                file_name=zip_name,
                mime='application/zip',
            )
            # 개별 다운로드도 제공
            with st.expander('개별 파일 다운로드'):
                for fname, data in results:
                    st.download_button(
                        label=f'⬇️ {fname}',
                        data=data,
                        file_name=fname,
                        mime='application/pdf',
                        key=fname
                    )
