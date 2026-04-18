# -*- coding: utf-8 -*-
import os

templates_dir = os.path.join(os.getcwd(), 'app', 'templates')

for r, dirs, files in os.walk(templates_dir):
    for f in files:
        if f.endswith('.html'):
            filepath = os.path.join(r, f)
            if os.path.getsize(filepath) == 0:
                continue
            try:
                # Try reading as utf-8
                with open(filepath, 'r', encoding='utf-8') as file:
                    file.read()
            except UnicodeDecodeError:
                # If it fails, read as gbk and save as utf-8
                print(f"Converting {f} from GBK to UTF-8")
                try:
                    with open(filepath, 'rb') as file:
                        content = file.read().decode('gbk')
                    with open(filepath, 'w', encoding='utf-8') as file:
                        file.write(content)
                except Exception as e:
                    print(f"Failed to convert {f}: {e}")
