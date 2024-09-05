#!/usr/bin/env python3

import os
import json

def fix_up(data):
    fixed = False
    for key in ['vertices', 'shapes', 'palettes']:
        if key not in data and 'body' in data and key in data['body']:
            data[key] = data['body'][key]
            del data['body'][key]
            fixed = True
    if 'palettes' in data and 'palette' not in data:
        data['palette'] = data['palettes']
        del data['palettes']
        fixed = True
    if isinstance(data["vertices"], list):
        data["vertices"] = {str(i): x for i, x in enumerate(data["vertices"])}
        fixed = True
    if 'shapes' not in data['vertices']["0"]:
        fixed = True
        for vertex in data['vertices'].values():
            vertex['shapes'] = []
        for i, shape in enumerate(data['shapes']):
            for vertex in shape['vertices']:
                if i not in data['vertices'][str(vertex)]['shapes']:
                    data['vertices'][str(vertex)]['shapes'].append(i)
    return fixed


changed, already_good = 0, 0
for base_dir in ["data", "extra"]:
    for dirname, dirnames, filenames in os.walk(base_dir):
        for fn in filenames:
            if fn.endswith(".json"):
                fn = os.path.join(dirname, fn)
                with open(fn) as f:
                    data = json.load(f)
                fixed = fix_up(data)
                if fixed:
                    changed += 1
                    print("Fixed: " + fn)
                    with open(fn, "wt", encoding="utf-8", newline="") as f:
                        json.dump(data, f)
                else:
                    already_good += 1

print(f"Done, {changed:,} changed, {already_good:,} already good.")
