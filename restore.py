# -*- coding: utf-8 -*-
import os
import json
import shutil
import urllib.parse

appdata = r"C:\Users\ty\AppData\Roaming"
history_dirs = [
    os.path.join(appdata, "CodeBuddy", "User", "History"),
    os.path.join(appdata, "CodeBuddy CN", "User", "History"),
    os.path.join(appdata, "Cursor", "User", "History"),
    os.path.join(appdata, "Code", "User", "History")
]

project_dir = os.getcwd()
templates_dir = os.path.join(project_dir, 'app', 'templates')

def get_uris(filepath):
    # VS Code / Cursor URI format
    # file:///d%3A/G/%E5%B7%A5%E4%BD%9C...
    filepath = filepath.replace('\\', '/')
    if filepath[1] == ':':
        drive = filepath[0]
        filepath_lower_drive = '/' + drive.lower() + filepath[1:]
        filepath_upper_drive = '/' + drive.upper() + filepath[1:]
    else:
        filepath_lower_drive = filepath
        filepath_upper_drive = filepath
        
    return [
        "file://" + urllib.parse.quote(filepath_lower_drive),
        "file://" + urllib.parse.quote(filepath_upper_drive),
        "vscode-vfs://github" + urllib.parse.quote(filepath_lower_drive),
        "vscode-vfs://github" + urllib.parse.quote(filepath_upper_drive)
    ]

def restore_file():
    empty_files = []
    for r, dirs, files in os.walk(templates_dir):
        for f in files:
            if f.endswith('.html') and os.path.getsize(os.path.join(r, f)) == 0:
                empty_files.append(os.path.join(r, f))

    for target_file in empty_files:
        target_uris = [u.lower() for u in get_uris(target_file)]
        target_uris_unquoted = [urllib.parse.unquote(u) for u in target_uris]
        
        found = False
        for history_dir in history_dirs:
            if found or not os.path.exists(history_dir):
                continue
                
            for folder in os.listdir(history_dir):
                entries_path = os.path.join(history_dir, folder, 'entries.json')
                if not os.path.exists(entries_path):
                    continue
                try:
                    with open(entries_path, 'r', encoding='utf-8') as f:
                        entries = json.load(f)
                    
                    resource = entries.get("resource", "").lower()
                    unquoted_resource = urllib.parse.unquote(resource)
                    
                    if unquoted_resource in target_uris_unquoted:
                        history_entries = entries.get("entries", [])
                        history_entries.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
                        
                        for entry in history_entries:
                            entry_id = entry.get("id")
                            entry_path = os.path.join(history_dir, folder, entry_id)
                            # Check size > 0 and size != the size of the empty file
                            if os.path.exists(entry_path) and os.path.getsize(entry_path) > 0:
                                print(f"Restoring {target_file} from {entry_path}")
                                shutil.copy2(entry_path, target_file)
                                found = True
                                break
                except Exception as e:
                    pass
                if found:
                    break
        
        if not found:
            print(f"Could not find history for {target_file}")

if __name__ == '__main__':
    restore_file()
