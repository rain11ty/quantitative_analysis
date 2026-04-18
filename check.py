# -*- coding: utf-8 -*-
import os

d = os.path.join(os.getcwd(), 'app', 'templates')
for r, dirs, files in os.walk(d):
    for f in files:
        if f.endswith('.html'):
            try:
                with open(os.path.join(r, f), 'r', encoding='utf-8') as file:
                    file.read()
            except UnicodeDecodeError as e:
                print(f"Error in {f}: {e}")
