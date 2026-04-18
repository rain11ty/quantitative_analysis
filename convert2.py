# -*- coding: utf-8 -*-
import os

filepath = os.path.join(os.getcwd(), 'app', 'templates', 'backtest.html')
try:
    with open(filepath, 'rb') as file:
        content = file.read().decode('gb18030', errors='replace')
    with open(filepath, 'w', encoding='utf-8') as file:
        file.write(content)
    print("Fixed backtest.html")
except Exception as e:
    print(e)
