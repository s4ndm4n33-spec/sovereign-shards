import sqlite3
import os

class BibleInterface:
    def __init__(self, db_path='shard_database.db'):
        self.db_path = db_path

    def add_verse(self, master, verse, tags=''):
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO bible (master, verse, tags) VALUES (?, ?, ?)',
                (master, verse, tags)
            )
            conn.commit()
            os.fsync(conn.fileno()) # Force physical commit to NAND[cite: 10]
            return True
        except Exception as e:
            return f'Database Error: {e}'
        finally:
            conn.close()