# -*- coding: utf-8 -*-
import os

f = os.path.join(os.getcwd(), 'app', 'templates', 'screen.html')
try:
    with open(f, 'rb') as file:
        content = file.read().decode('gbk')
    with open(f, 'w', encoding='utf-8') as file:
        file.write(content)
    print("Fixed screen.html")
except Exception as e:
    print(e)
