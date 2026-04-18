# -*- coding: utf-8 -*-
import os
import chardet

def convert_to_utf8(file_path):
    with open(file_path, 'rb') as f:
        raw_data = f.read()
    
    result = chardet.detect(raw_data)
    encoding = result['encoding']
    
    if encoding and encoding.lower() != 'utf-8':
        try:
            print(f"Converting {file_path} from {encoding} to utf-8...")
            text = raw_data.decode(encoding)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(text)
            print(f"Successfully converted {file_path}")
        except Exception as e:
            print(f"Failed to convert {file_path}: {e}")

template_dir = 'd:/G/工作与学习/大四下/lianghua/quantitative_analysis/app/templates'
for root, dirs, files in os.walk(template_dir):
    for file in files:
        if file.endswith('.html'):
            convert_to_utf8(os.path.join(root, file))
