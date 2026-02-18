import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px

from pipeline.extract_text import extract_text
from pipeline.parse_ttz import parse_ttz_requirements
from pipeline.compare import compare_requirements
from database import HistoryDatabase

# Инициализация базы данных
@st.cache_resource
def init_db():
    return HistoryDatabase()

# Настройка страницы
st.set_page_config(
    page_title="Сравнить ТТЗ и КД",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown(
    """
    <style>
      /* ========== СПОКОЙНЫЙ КЛАССИЧЕСКИЙ САЙДБАР ========== */

      section[data-testid="stSidebar"] {
        border-right: 1px solid rgba(255,255,255,0.08);
      }

      section[data-testid="stSidebar"] > div {
        background: #111827; /* спокойный тёмный */
      }

      /* Заголовки */
      section[data-testid="stSidebar"] h1,
      section[data-testid="stSidebar"] h2,
      section[data-testid="stSidebar"] h3 {
        font-weight: 600;
        letter-spacing: 0.3px;
      }

      /* Кнопки в сайдбаре */
      section[data-testid="stSidebar"] button {
        border-radius: 8px;
      }

      /* Убираем яркую рамку истории */
      .history-cta {
        border: 1px solid rgba(255,255,255,0.08);
        background: rgba(255,255,255,0.02);
        border-radius: 10px;
        padding: 10px;
        margin-top: 6px;
        margin-bottom: 10px;
      }

      .history-cta .badge {
        background: rgba(255,255,255,0.08);
        border: none;
        font-weight: 600;
      }

      .history-cta .hint {
        opacity: 0.6;
        font-size: 12px;
      }

      /* ========== ДЕЛАЕМ ШТОРКУ (>>) ЗАМЕТНЕЕ ========== */

      button[data-testid="collapsedControl"] {
        background: rgba(255,255,255,0.08) !important;
        border-radius: 8px !important;
        width: 38px !important;
        height: 38px !important;
      }

      button[data-testid="collapsedControl"]:hover {
        background: rgba(255,255,255,0.15) !important;
      }

      /* увеличим иконку стрелки */
      button[data-testid="collapsedControl"] svg {
        transform: scale(1.3);
      }
      
      @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(255,255,255,0.2); }
        70% { box-shadow: 0 0 0 8px rgba(255,255,255,0); }
        100% { box-shadow: 0 0 0 0 rgba(255,255,255,0); }
      }  

    </style>
    """,
    unsafe_allow_html=True
)


# Инициализация сессии
if 'db' not in st.session_state:
    st.session_state.db = init_db()
if 'current_user' not in st.session_state:
    st.session_state.current_user = "Аноним"
if 'page' not in st.session_state:
    st.session_state.page = "main"

# Заголовок
st.markdown(
    """
    <div style="text-align:center; margin-top: 20px; margin-bottom: 30px;">
      <div style="font-size:48px; font-weight:800; letter-spacing:1px;">
        СРАВНИТЕЛЬ ТТЗ И КД
      </div>
    </div>
    """,
    unsafe_allow_html=True
)

# ========== ОПРЕДЕЛЕНИЕ ФУНКЦИЙ ==========

def display_results(df, comparison_id):
    """Отображает результаты сравнения"""

    st.divider()
    st.subheader(f"📊 Результаты сравнения (ID: {comparison_id})")

    # Метрики
    col1, col2, col3, col4, col5 = st.columns(5)

    total = len(df)
    ok = int((df["status"] == "OK").sum())
    partial = int((df["status"] == "PARTIAL").sum())
    found = int((df["status"].isin(["OK","PARTIAL","FOUND"])).sum())
    not_found = int((df["status"] == "NOT_FOUND").sum())

    with col1:
        st.metric("Всего", total)
    with col2:
        st.metric("Найдено", found, delta=f"{(found/total*100):.1f}%" if total > 0 else "0%")
    with col3:
        st.metric("✅ OK", ok)
    with col4:
        st.metric("⚠️ PARTIAL", partial)
    with col5:
        st.metric("❌ NOT_FOUND", not_found)

    # Таблица результатов
    st.dataframe(
        df[["req_id","ttz_section","status","match_type","numbers_covered","req_text"]],
        use_container_width=True,
        height=400
    )

    # Комментарии
    st.divider()
    st.subheader("💬 Комментарии")

    # Отображаем существующие комментарии
    comments = st.session_state.db.get_comments(comparison_id)
    if comments:
        for comment in comments:
            with st.container():
                col1, col2 = st.columns([6, 1])
                with col1:
                    st.markdown(f"**{comment['user_name']}** - {comment['timestamp'][:16]}")
                    st.markdown(comment['comment_text'])
                st.divider()
    else:
        st.info("Пока нет комментариев")

    # Форма для нового комментария
    with st.form(key=f"comment_form_{comparison_id}"):
        new_comment = st.text_area("Добавить комментарий", height=100)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            submitted = st.form_submit_button("📝 Отправить комментарий", use_container_width=True)

        if submitted and new_comment:
            st.session_state.db.add_comment(
                comparison_id=comparison_id,
                user_name=st.session_state.current_user,
                comment_text=new_comment
            )
            st.success("✅ Комментарий добавлен!")
            st.rerun()

    # Доказательства
    st.divider()
    st.subheader("🔍 Доказательства из КД")

    for _, row in df.iterrows():
        with st.expander(f"{row['req_id']} — {row['status']}"):
            st.markdown("**Требование (ТТЗ):**")
            st.write(row["req_text"])
            st.markdown("**Фрагмент из КД:**")
            if row["kd_evidence"]:
                st.write(row["kd_evidence"])
            else:
                st.write("*Фрагмент не найден*")
            if row["diff"]:
                st.markdown("**Различия:**")
                st.code(row["diff"])

def display_comparison_details(comparison_id):
    """Отображает детали конкретного сравнения"""

    comparison = st.session_state.db.get_comparison_details(comparison_id)
    if not comparison:
        st.error("Сравнение не найдено")
        return

    st.markdown(f"""
    ### Детали сравнения от {comparison['timestamp'][:16]}
    - **Пользователь:** {comparison['user_name']}
    - **Файл ТТЗ:** {comparison['ttz_filename']}
    - **Файл КД:** {comparison['kd_filename']}
    """)

    # Преобразуем JSON обратно в DataFrame
    df = pd.DataFrame(comparison['results_json'])

    display_results(df, comparison_id)

def show_main_page():
    """Отображает основную страницу с загрузкой файлов"""

    st.markdown(
        """
        <div style="text-align:center; font-size:16px; opacity:0.75; margin-bottom:30px;">
          Загрузите ТТЗ и КД для анализа соответствия требований
        </div>
        """,
        unsafe_allow_html=True
    )

    col1, col2 = st.columns(2)
    with col1:
        ttz_file = st.file_uploader(
            "📄 ТТЗ (PDF/DOCX/TXT)",
            type=["pdf", "docx", "txt"],
            key="ttz"
        )
    with col2:
        kd_file = st.file_uploader(
            "📄 КД (PDF/DOCX/TXT)",
            type=["pdf", "docx", "txt"],
            key="kd"
        )

    st.divider()

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        run = st.button(
            "🔍 Сравнить файлы",
            use_container_width=True,
            type="primary",
            disabled=not (ttz_file and kd_file)
        )

    if run and ttz_file and kd_file:
        with st.status("🔄 Обработка файлов...", expanded=True) as status:
            try:
                # Извлечение текста из ТТЗ
                st.write("📑 Извлекаю текст из ТТЗ...")
                ttz_text, ttz_meta = extract_text(ttz_file.getvalue(), ttz_file.name)
                st.write(f"✅ Текст извлечен: {ttz_meta['text_len']} символов")

                # Извлечение текста из КД
                st.write("📑 Извлекаю текст из КД...")
                kd_text, kd_meta = extract_text(kd_file.getvalue(), kd_file.name)
                st.write(f"✅ Текст извлечен: {kd_meta['text_len']} символов")

                # Парсинг требований
                st.write("🔍 Анализирую требования ТТЗ...")
                reqs = parse_ttz_requirements(ttz_text)
                st.write(f"✅ Найдено требований: {len(reqs)}")

                # Сравнение
                st.write("🤝 Сопоставляю с КД...")
                rows = compare_requirements(reqs, kd_text)

                # Создаем DataFrame
                df = pd.DataFrame(rows)

                # Сохраняем в историю
                comparison_id = st.session_state.db.save_comparison(
                    ttz_filename=ttz_file.name,
                    kd_filename=kd_file.name,
                    df_results=df,
                    user_name=st.session_state.current_user
                )

                status.update(
                    label=f"✅ Готово! ID сравнения: {comparison_id}",
                    state="complete"
                )

                # Сохраняем результаты в сессию для отображения
                st.session_state.last_results = df
                st.session_state.last_comparison_id = comparison_id
                st.session_state.page = "history"
                st.rerun()

            except Exception as e:
                status.update(label="❌ Ошибка при обработке", state="error")
                st.error(f"Произошла ошибка: {str(e)}")

    # Отображение результатов, если они есть
    if (
            st.session_state.page == "main"
            and 'last_results' in st.session_state
            and 'last_comparison_id' in st.session_state
    ):
        display_results(
            st.session_state.last_results,
            st.session_state.last_comparison_id
        )



def show_history_page():
    """Отображает страницу с историей загрузок"""

    st.header("📜 История сравнений")

    # Получаем все сравнения из БД
    comparisons = st.session_state.db.get_all_comparisons()

    if not comparisons:
        st.info("📭 История пока пуста. Выполните сравнение на главной странице.")
        return

    # Создаем DataFrame для отображения
    history_df = pd.DataFrame(comparisons)
    history_df['timestamp'] = pd.to_datetime(history_df['timestamp'])
    history_df['date'] = history_df['timestamp'].dt.strftime('%d.%m.%Y %H:%M')

    # Статистика по всем сравнениям
    st.subheader("📊 Общая статистика")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Всего сравнений", len(comparisons))
    with col2:
        total_reqs = sum(c['total'] for c in comparisons)
        st.metric("Всего требований", total_reqs)
    with col3:
        avg_found = sum(c['found'] for c in comparisons) / len(comparisons)
        st.metric("Среднее найденных", f"{avg_found:.1f}")
    with col4:
        success_rate = (sum(c['found'] for c in comparisons) / total_reqs * 100) if total_reqs > 0 else 0
        st.metric("Общий % покрытия", f"{success_rate:.1f}%")

    st.divider()

    # График активности
    if len(comparisons) > 1:
        fig = px.line(
            x=[c['timestamp'] for c in comparisons],
            y=[c['found'] for c in comparisons],
            title="Динамика найденных требований",
            labels={'x': 'Дата', 'y': 'Найдено требований'}
        )
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Выбор сравнения для просмотра
    st.subheader("🔍 Детальный просмотр")

    # Создаем список для выбора
    options = {
        f"{row['date']} - {row['ttz_filename']} ({row['found']}/{row['total']})": row['id']
        for _, row in history_df.iterrows()
    }

    selected = st.selectbox(
        "Выберите сравнение для просмотра:",
        options=list(options.keys())
    )

    if selected:
        comparison_id = options[selected]
        display_comparison_details(comparison_id)

# ========== ОСНОВНАЯ ЛОГИКА ==========

# Боковая панель с настройками пользователя
with st.sidebar:
    st.header("👤 Пользователь")
    user_name = st.text_input("Ваше имя", value=st.session_state.current_user)
    if user_name != st.session_state.current_user:
        st.session_state.current_user = user_name

    st.divider()

    # Навигация
    st.header("Навигация")

    # обычная кнопка главной страницы
    if st.button("📊 Основная страница", use_container_width=True):
        st.session_state.page = "main"
        st.rerun()

    # количество записей истории (достаем быстро из БД)
    try:
        history_count = len(st.session_state.db.get_all_comparisons())
    except Exception:
        history_count = 0

    # АКЦЕНТНЫЙ БЛОК ИСТОРИИ
    st.markdown(
        f"""
        <div class="history-cta">
          <div style="font-weight:800; font-size:16px;">
            📜 История загрузок
            <span class="badge">{history_count}</span>
          </div>
          <div class="hint">Тут все предыдущие сравнения, результаты и комментарии.</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    if st.button("➡️ Открыть историю", use_container_width=True, type="primary"):
        st.session_state.page = "history"
        st.rerun()


# Отображение выбранной страницы
if st.session_state.page == "main":
    show_main_page()
else:
    show_history_page()