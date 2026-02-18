# database.py
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd
import os

class HistoryDatabase:
    def __init__(self, db_path="comparison_history.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Инициализация таблиц в базе данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Таблица для истории сравнений
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS comparisons (
                                                                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                                  timestamp TEXT NOT NULL,
                                                                  ttz_filename TEXT NOT NULL,
                                                                  kd_filename TEXT NOT NULL,
                                                                  total_requirements INTEGER,
                                                                  found_count INTEGER,
                                                                  ok_count INTEGER,
                                                                  partial_count INTEGER,
                                                                  not_found_count INTEGER,
                                                                  results_json TEXT NOT NULL,
                                                                  user_name TEXT DEFAULT 'Аноним'
                       )
                       ''')

        # Таблица для комментариев
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS comments (
                                                               id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                               comparison_id INTEGER NOT NULL,
                                                               timestamp TEXT NOT NULL,
                                                               user_name TEXT NOT NULL,
                                                               comment_text TEXT NOT NULL,
                                                               FOREIGN KEY (comparison_id) REFERENCES comparisons (id) ON DELETE CASCADE
                           )
                       ''')

        conn.commit()
        conn.close()

    def save_comparison(self, ttz_filename: str, kd_filename: str,
                        df_results: pd.DataFrame, user_name: str = "Аноним") -> int:
        """Сохраняет результаты сравнения в БД"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Подсчет статистики
        total = len(df_results)
        found = int((df_results["status"].isin(["OK","PARTIAL","FOUND"])).sum())
        ok_count = int((df_results["status"] == "OK").sum())
        partial_count = int((df_results["status"] == "PARTIAL").sum())
        not_found_count = int((df_results["status"] == "NOT_FOUND").sum())

        # Преобразуем DataFrame в JSON для хранения
        results_json = df_results.to_json(orient="records", force_ascii=False, indent=2)

        cursor.execute('''
                       INSERT INTO comparisons
                       (timestamp, ttz_filename, kd_filename, total_requirements,
                        found_count, ok_count, partial_count, not_found_count,
                        results_json, user_name)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ''', (
                           datetime.now().isoformat(),
                           ttz_filename,
                           kd_filename,
                           total,
                           found,
                           ok_count,
                           partial_count,
                           not_found_count,
                           results_json,
                           user_name
                       ))

        comparison_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return comparison_id

    def get_all_comparisons(self) -> List[Dict[str, Any]]:
        """Получает список всех сравнений"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
                       SELECT id, timestamp, ttz_filename, kd_filename,
                           total_requirements, found_count, ok_count,
                           partial_count, not_found_count, user_name
                       FROM comparisons
                       ORDER BY timestamp DESC
                       ''')

        rows = cursor.fetchall()
        conn.close()

        comparisons = []
        for row in rows:
            comparisons.append({
                'id': row[0],
                'timestamp': row[1],
                'ttz_filename': row[2],
                'kd_filename': row[3],
                'total': row[4],
                'found': row[5],
                'ok': row[6],
                'partial': row[7],
                'not_found': row[8],
                'user_name': row[9]
            })

        return comparisons

    def get_comparison_details(self, comparison_id: int) -> Optional[Dict[str, Any]]:
        """Получает детали конкретного сравнения"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
                       SELECT id, timestamp, ttz_filename, kd_filename,
                           total_requirements, found_count, ok_count,
                           partial_count, not_found_count, results_json, user_name
                       FROM comparisons
                       WHERE id = ?
                       ''', (comparison_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'id': row[0],
                'timestamp': row[1],
                'ttz_filename': row[2],
                'kd_filename': row[3],
                'total': row[4],
                'found': row[5],
                'ok': row[6],
                'partial': row[7],
                'not_found': row[8],
                'results_json': json.loads(row[9]),
                'user_name': row[10]
            }
        return None

    def add_comment(self, comparison_id: int, user_name: str, comment_text: str):
        """Добавляет комментарий к сравнению"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
                       INSERT INTO comments (comparison_id, timestamp, user_name, comment_text)
                       VALUES (?, ?, ?, ?)
                       ''', (
                           comparison_id,
                           datetime.now().isoformat(),
                           user_name,
                           comment_text
                       ))

        conn.commit()
        conn.close()

    def get_comments(self, comparison_id: int) -> List[Dict[str, Any]]:
        """Получает все комментарии для сравнения"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
                       SELECT id, timestamp, user_name, comment_text
                       FROM comments
                       WHERE comparison_id = ?
                       ORDER BY timestamp ASC
                       ''', (comparison_id,))

        rows = cursor.fetchall()
        conn.close()

        comments = []
        for row in rows:
            comments.append({
                'id': row[0],
                'timestamp': row[1],
                'user_name': row[2],
                'comment_text': row[3]
            })

        return comments