import sqlite3

DB = 'database.db'  # Change path if needed

def reset_database():
    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()
        # Delete all users
        cursor.execute("DELETE FROM users")
        # Reset all candidate vote counts
        cursor.execute("UPDATE candidates SET votes = 0")
        conn.commit()
        print("✅ Database reset: users deleted and votes reset to 0.")

if __name__ == "__main__":
    reset_database()
