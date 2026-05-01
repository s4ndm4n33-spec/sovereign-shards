import sys
import argparse
import sqlite3

def run_sql(query):
    try:
        conn = sqlite3.connect('shard_database.db')
        cursor = conn.cursor()
        cursor.execute(query)
        
        if query.strip().upper().startswith("SELECT"):
            results = cursor.fetchall()
            return f"Results: {results}"
        
        conn.commit()
        return "Query executed and committed."
    except Exception as e:
        return f"Database Error: {str(e)}"
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sql_query", required=True)
    args = parser.parse_args()
    print(run_sql(args.sql_query))
