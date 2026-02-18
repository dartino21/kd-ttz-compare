# manage_db.py
import sqlite3
import argparse
from database import HistoryDatabase

def clean_old_records(days=30):
    """Удаляет записи старше указанного количества дней"""
    db = HistoryDatabase()
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()

    from datetime import datetime, timedelta
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    cursor.execute("DELETE FROM comparisons WHERE timestamp < ?", (cutoff,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()

    print(f"Удалено {deleted} записей старше {days} дней")

def export_to_excel():
    """Экспортирует всю историю в Excel"""
    db = HistoryDatabase()
    comparisons = db.get_all_comparisons()

    import pandas as pd
    df = pd.DataFrame(comparisons)
    df.to_excel("history_export.xlsx", index=False)
    print("Экспорт завершен: history_export.xlsx")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean", type=int, help="Очистить записи старше N дней")
    parser.add_argument("--export", action="store_true", help="Экспорт в Excel")

    args = parser.parse_args()

    if args.clean:
        clean_old_records(args.clean)
    elif args.export:
        export_to_excel()
    else:
        print("Использование: python manage_db.py --clean 30 или --export")