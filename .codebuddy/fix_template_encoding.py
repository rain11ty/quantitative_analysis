from pathlib import Path

root = Path('app/templates')
fixed = []

for p in root.rglob('*.html'):
    raw = p.read_bytes()
    try:
        raw.decode('utf-8')
        continue
    except UnicodeDecodeError:
        pass

    text = None
    for enc in ('gbk', 'gb18030', 'latin1'):
        try:
            text = raw.decode(enc)
            break
        except Exception:
            continue

    if text is None:
        text = raw.decode('utf-8', errors='ignore')

    p.write_text(text, encoding='utf-8', newline='\n')
    fixed.append(str(p))

print('fixed_count', len(fixed))
for item in fixed:
    print(item)
