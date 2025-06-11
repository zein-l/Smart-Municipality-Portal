import sqlite3

conn = sqlite3.connect("municipality.db")
cursor = conn.cursor()

cursor.execute("SELECT * FROM category_3_license_requests")
rows = cursor.fetchall()

for row in rows:
    print(row)

conn.close()
