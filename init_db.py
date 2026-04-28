import sqlite3
import os

db_path = 'shard_database.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create the table
cursor.execute('''
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    status TEXT DEFAULT 'Active',
    priority INTEGER DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

# Insert the Shard
cursor.execute("INSERT INTO projects (name, status, priority) VALUES ('Sovereign Shard', 'Stabilized', 1)")

conn.commit()
conn.close()
print(f"Database initialized at {os.path.abspath(db_path)}")
