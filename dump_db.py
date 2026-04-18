# -*- coding: utf-8 -*-
import sqlite3
import json
import re

db_path = r'C:\Users\ty\AppData\Roaming\CodeBuddy\User\globalStorage\state.vscdb'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("SELECT key, value FROM ItemTable")
    rows = cursor.fetchall()
    
    for key, value in rows:
        if isinstance(value, str):
            # Extract anything that looks like a markdown HTML block for screen.html
            blocks = re.findall(r'```(?:html)?\s*(.*?)```', value, re.S)
            for b in blocks:
                if 'screen' in b.lower() and 'body' in b.lower():
                    with open('screen_dump.txt', 'a', encoding='utf-8') as f:
                        f.write(f"Key: {key}\n")
                        f.write(b)
                        f.write("\n" + "="*80 + "\n")
            
            # Also just search for the file path write_to_file calls
            if 'screen.html' in value and 'content' in value:
                with open('screen_tool_dump.txt', 'a', encoding='utf-8') as f:
                    f.write(f"Key: {key}\n")
                    f.write(value)
                    f.write("\n" + "="*80 + "\n")
                    
except Exception as e:
    print(e)
finally:
    conn.close()
