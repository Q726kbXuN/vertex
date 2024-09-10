#!/usr/bin/env python3

import html, os, re, json
from datetime import datetime, timedelta

SHOW_TUI_CAL = False

def get_files_with_date():
    dirs = ["data"]
    while len(dirs):
        cur_dir = dirs.pop(0)
        for fn in sorted(os.listdir(cur_dir)):
            cur = os.path.join(cur_dir, fn)
            if os.path.isdir(cur):
                dirs.append(cur)
            else:
                if cur.endswith(".json"):
                    yield fn[:10], cur

def load_link_data():
    links = {}
    with open(os.path.join("images", "youtube.jsonl")) as f:
        for row in f:
            row = json.loads(row)
            links[row[0]] = {"url": "https://youtu.be/" + row[1], "desc": row[2]}
    return links

def get_links():
    data_fn = os.path.join("output", "daily.json")
    if os.path.isfile(data_fn):
        with open(data_fn) as f:
            data = json.load(f)
    else:
        return

    old_link_data = load_link_data()
    added = 0
    for key, value in data.items():
        if 'youtube' in value:
            if key not in old_link_data:
                added += 1
                print(f"New video {added}: {key}, '{value['theme']}'")

    if added > 0:
        with open(os.path.join("images", "youtube.jsonl"), "wt", encoding="utf-8", newline="") as f:
            for key, value in data.items():
                if 'youtube' in value:
                    f.write(json.dumps([key, value['youtube'], value['theme']]) + "\n")

def make_cal():
    get_links()

    known_dates = set(x[0] for x in get_files_with_date())
    start = min(known_dates)
    end = max(known_dates)

    cur = datetime(int(start[:4]), int(start[5:7]), int(start[8:10]))

    dates = {}
    while cur.strftime("%Y-%m-%d") <= end:
        year = cur.strftime("%Y")
        month = cur.strftime("%m")
        if year not in dates:
            dates[year] = {}
        if month not in dates[year]:
            dates[year][month] = []
        if len(dates[year][month]) == 0 or dates[year][month][-1][6] is not None:
            dates[year][month].append([None for _ in range(7)])
        dates[year][month][-1][cur.weekday()] = cur
        cur += timedelta(days=1)

    with open("videos.md", "rt", encoding="utf-8") as f:
        markdown = f.read()

    links = load_link_data()

    cal = "<table><!--\n"
    for year in sorted(dates):
        cal += f'--><tr><td colspan="23" align="center">{year}</td></tr><!--\n'
        if SHOW_TUI_CAL:
            print(" " * 10 + year)
        months = list(sorted(dates[year]))
        for i in range(0, len(months), 3):
            cluster = months[i:i+3]
            cal += '--><tr>'
            cal += '<td>&nbsp;</td>'.join(f'<td colspan="7" align="center">{datetime(2010, int(x), 1).strftime("%B"):17}</td>' for x in cluster)
            cal += '</tr><!--\n'
            if SHOW_TUI_CAL:
                print("  ".join(f'  {datetime(2010, int(x), 1).strftime("%B"):17}  ' for x in cluster))
            for row in range(max(len(dates[year][x]) for x in cluster)):
                target = []
                for month in cluster:
                    if len(target) > 0:
                        target.append(None)
                    if row < len(dates[year][month]):
                        target.extend(dates[year][month][row])
                    else:
                        target.extend([None for _ in range(7)])
                if row == 0:
                    days = 'MTWTFSS MTWTFSS MTWTFSS'
                    cal += '--><tr>'
                    for day, _ in zip(days, target):
                        if day == ' ':
                            day = '&nbsp;'
                        cal += f'<td align="right">{day}</td>'
                    cal += '</tr><!--\n'
                cal += '--><tr>'
                disp = []
                for x in target:
                    at = x.strftime("%Y-%m-%d") if x is not None else None
                    if x is None:
                        cal += '<td></td>'
                        disp.append('  ')
                    elif at in links:
                        cal += f'<td align="right"><a href="{links[at]['url']}" title="{html.escape(links[at]['desc'])}">{x.day}</a></td>'
                        disp.append(f"{x.day:2d}")
                    elif at in known_dates:
                        cal += f'<td align="right">{x.day}</td>'
                        disp.append(f"!!")
                    else:
                        cal += f'<td align="right">--</td>'
                        disp.append("--")
                cal += '</tr><!--\n'
                if SHOW_TUI_CAL:
                    print(" ".join(disp))

    cal += "--></table>\n"

    markdown = re.sub("<!-- CAL_START -->.*?<!-- CAL_END -->", "<!-- CAL_START -->\n" + cal + "<!-- CAL_END -->", markdown, flags=re.DOTALL)

    with open("videos.md", "wt", newline="", encoding="utf-8") as f:
        f.write(markdown)

if __name__ == "__main__":
    make_cal()
