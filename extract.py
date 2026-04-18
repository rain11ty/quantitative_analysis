# -*- coding: utf-8 -*-
import re
import os

filepath = os.path.join(os.getcwd(), '..', 'history_202604152136.md')
with open(filepath, 'r', encoding='utf-8') as f:
    txt = f.read()
    
with open('tool_calls.txt', 'w', encoding='utf-8') as f:
    for m in re.findall(r'write_to_file.{0,200}', txt, re.S):
        f.write(m + '\n-------------------\n')
