import streamlit as st
import pandas as pd

from pipeline.extract_text import extract_text
from pipeline.parse_ttz import parse_ttz_requirements
from pipeline.compare import compare_requirements

st.set_page_config(page_title="Сравнить файл", layout="wide")

st.markdown(
    """
    <div style="text-align:center; margin-top: 40px; margin-bottom: 10px;">
      <div style="font-size:48px; font-weight:800; letter-spacing:1px;">СРАВНИТЬ ФАЙЛ</div>
      <div style="font-size:16px; opacity:0.75; margin-top:10px;">
        Загрузите ТТЗ и КД. Мы построим таблицу соответствия требований.
      </div>
    </div>
    """,
    unsafe_allow_html=True
)

col1, col2 = st.columns(2)
with col1:
    ttz_file = st.file_uploader("ТТЗ (PDF/DOCX)", type=["pdf", "docx", "txt"], key="ttz")
with col2:
    kd_file = st.file_uploader("КД (PDF/DOCX)", type=["pdf", "docx", "txt"], key="kd")

st.divider()

run = st.button("Сравнить", use_container_width=True, type="primary")

if run:
    if not ttz_file or not kd_file:
        st.error("Нужно загрузить оба файла: ТТЗ и КД.")
        st.stop()

    with st.status("Обработка…", expanded=True) as status:
        st.write("Извлекаю текст из ТТЗ…")
        ttz_text, ttz_meta = extract_text(ttz_file.getvalue(), ttz_file.name)

        st.write("Извлекаю текст из КД…")
        kd_text, kd_meta = extract_text(kd_file.getvalue(), kd_file.name)

        st.write("Извлекаю требования из ТТЗ…")
        reqs = parse_ttz_requirements(ttz_text)
        st.write(f"Найдено требований: {len(reqs)}")

        st.write("Сопоставляю требования с КД…")
        rows = compare_requirements(reqs, kd_text)

        status.update(label="Готово", state="complete")

    df = pd.DataFrame(rows)

    left, right = st.columns([2, 1])
    with left:
        st.subheader("Отчёт по требованиям")
        st.dataframe(df[["req_id","ttz_section","status","match_type","numbers_covered","req_text"]], use_container_width=True)
    with right:
        st.subheader("Сводка")
        total = len(df)
        ok = int((df["status"] == "OK").sum())
        partial = int((df["status"] == "PARTIAL").sum())
        nf = int((df["status"] == "NOT_FOUND").sum())
        found = int((df["status"].isin(["OK","PARTIAL","FOUND"])).sum())

        st.metric("Всего требований", total)
        st.metric("Найдено покрытие", f"{found}/{total}")
        st.metric("OK", ok)
        st.metric("PARTIAL", partial)
        st.metric("NOT_FOUND", nf)

    st.divider()
    st.subheader("Доказательства (фрагменты из КД)")
    # show expandable evidence per row
    for _, row in df.iterrows():
        with st.expander(f"{row['req_id']} — {row['status']}"):
            st.markdown("**Требование (ТТЗ):**")
            st.write(row["req_text"])
            st.markdown("**Фрагмент из КД:**")
            st.write(row["kd_evidence"] if row["kd_evidence"] else "—")
            if row["diff"]:
                st.markdown("**Короткий diff (очень грубо):**")
                st.code(row["diff"])
