import sqlite3

def check_users():
    conn = sqlite3.connect('municipality.db')
    cursor = conn.cursor()

    print("\nChecking if users exist in 'user_profiles'...\n")
    
    cursor.execute("SELECT * FROM user_profiles")
    users = cursor.fetchall()

    if not users:
        print("✅ No users exist in the database.")
    else:
        print("⚠️ Users exist in the database:")
        for user in users:
            print(user)

    conn.close()

check_users()
