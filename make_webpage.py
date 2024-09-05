#!/usr/bin/env python3

from datetime import datetime, timedelta
from make_image import show_puzzle
import html, json, os, re

SERIALIZE_DATA = os.path.join(os.path.expanduser("~"), ".vertex-data.json")
USE_LOCAL_FILES = False

def github(fn):
    if USE_LOCAL_FILES:
        return fn
    else:
        fn = fn.replace("\\", "/")
        return 'https://raw.githubusercontent.com/Q726kbXuN/vertex/master/' + fn

def walk_dir(dirname, exts):
    dirs = [dirname]
    while len(dirs) > 0:
        cur_dir = dirs.pop(0)
        for cur in sorted(os.listdir(cur_dir)):
            fn = os.path.join(cur_dir, cur)
            if os.path.isdir(fn):
                dirs.append(fn)
            else:
                if fn.split(".")[-1] in exts:
                    yield cur, fn

class Data:
    def __init__(self):
        self.data = {}
    def add(self, at, group, fn, title, use_title=False):
        if at not in self.data:
            self.data[at] = {"at": at}
        if len(title) > 0 and ("title" not in self.data[at] or use_title):
            self.data[at]["title"] = title
        self.data[at][group] = fn
    def serialize(self, fn):
        with open(fn, "wt", newline="", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4)
    def deserialize(self, fn):
        with open(fn, "rt", encoding="utf-8") as f:
            self.data = json.load(f)

def parse_date(val):
    return datetime(
        year=int(val[0:4]),
        month=int(val[5:7]),
        day=int(val[8:10]),
    )

old_cwd = os.getcwd()
os.chdir(os.path.split(__file__)[0])

data = Data()

# Load the tweet info, crack open the metadata to get the title from the 
# tweet text itself
months = {
    'January': 1, 'February': 2, 'March': 3, 'April': 4, 
    'May': 5, 'June': 6, 'July': 7, 'August': 8, 
    'September': 9, 'October': 10, 'November': 11, 'December': 12, 'Decmber': 12,
}
# These are unrelated tweets
ignore = {
    "2022-10-02-18-00-51",
    "2024-04-26-14-44-47",
    "2024-07-04-15-00-33",
    "2023-12-21-16-17-41",
    "2021-11-06-15-49-56",
    "2021-03-31-15-04-45",
    "2021-08-18-15-22-46",
    "2022-04-22-16-19-22",
    "2023-03-23-15-31-24",
    "2023-07-17-16-02-40",
    "2024-03-12-10-47-20",
    "2024-04-12-15-33-43",
    "2024-05-13-18-28-19",
    "2024-07-11-18-00-10",
    "2024-08-07-10-19-51",
}
# These tweets doesn't follow the normal format
special = {
    "2021-03-07-16-16-37": ("2024-03-07", "Growing bananas"),
    "2021-07-22-13-15-32": ("2021-07-22", "Music box"),
}

# Load the youtube links
youtube = {}
with open(os.path.join("images", "youtube.jsonl")) as f:
    for row in f:
        row = json.loads(row)
        youtube[row[0]] = "https://youtu.be/" + row[1]

if SERIALIZE_DATA is not None and os.path.isfile(SERIALIZE_DATA):
    # Since it takes a while to read all the little JSON files, and the data
    # no longer changes, go ahead and serialize the final state of the data
    # and load that state once we've done that.
    data.deserialize(SERIALIZE_DATA)
else:
    for tweet, fn in walk_dir('twitter_archive', {"png", "jpg"}):
        tweet = tweet.split("_")[0]
        if tweet not in ignore:
            with open(fn + ".json", "rt", encoding="utf-8") as f:
                temp = json.load(f)

            if tweet in special:
                # Doesn't follow the normal format, just use the hardcoded one
                at, title = special[tweet]
            else:
                # Parse out the datetime
                title = temp['content']
                m = re.search("^(?P<month>" + "|".join(months) + ") (?P<day>[0-9]+)(,|\\.|) (?P<year>[0-9]+)[. ]*(?P<title>.*?)(#|$)", title)
                if m is None:
                    m = re.search("^(?P<title>.*?\\.) (?P<month>" + "|".join(months) + ") (?P<day>[0-9]+)(,|\\.|) (?P<year>[0-9]+)", title)
                if m is None:
                    # Boom?  Show the user something went wrong
                    print("TWEET: " + tweet)
                    print("ERROR: " + title)
                    exit(1)
                # Pull out the data we care about
                at = datetime(int(m.group("year")), months[m.group("month")], int(m.group("day")))
                at = at.strftime("%Y-%m-%d")
                title = m.group("title").strip(" .")

            group = fn.split("_")[2][0]
            data.add(at, group, fn, title)
            if group == '1':
                # Store the link to the tweet
                data.add(at, "tweet", f"https://x.com/{temp['author']['name']}/status/{temp['tweet_id']}", '')

    # Load the data from the puzzle data
    for at, fn in walk_dir('data', {'json'}):
        with open(fn) as f:
            temp = json.load(f)
        data.add(at[:10], 'json', fn, temp['theme'], use_title=True)

    if SERIALIZE_DATA is not None:
        data.serialize(SERIALIZE_DATA)

# Show an entry for every day, including days missing both puzzle data and tweets
start = parse_date(min(data.data))
end = parse_date(max(data.data))

with open(os.path.join(old_cwd, "index.html"), "wt", newline="", encoding="utf-8") as f:
    f.write('''<!DOCTYPE html>
<html>
<head>
<link rel="icon" type="image/png" sizes="32x32" href="images/favicon.png"/>
<title>Vertex</title>
<style>
html {
    height: 100%;
}
a {
    color: #000;
    text-decoration: none;
}
a:hover {
    color: #000;
    text-decoration: underline;
}
.obj {
    position: relative;
}
a.youtube {
    width: 50px;
    height: 30px;
    position: absolute;
    bottom: 10px;
    right: 10px;
    background-image: url('images/play.png');
}
a.youtube:hover {
    background-image: url('images/play-hover.png');
}
body {
    height: 100%;
    background-color: #fff;
    color: #000;
    display: flex;
    box-sizing: border-box;
    margin: 0;
}
img {
    object-fit: contain;
    width: 300px;
    height: 300px;
    border: 1px solid #000;
}
.missing {
    width: 300px;
    height: 300px;
    border: 1px solid #000;
    background-color: #666;
    display: inline-block;
}
.column {
    height: 100%;
    display: flex;
    flex-direction: column;
}
#left {
    width: 5em;
    background-color: #eee;
}
#right {
    width: 100%;
}
.bottom {
    padding: 0.5em;
    flex-grow: 1;
    overflow-y: auto;
}
</style>
<base target="_blank">
</head>
<body>
''')

    f.write('<div id="left" class="column"><div class="bottom">')
    at = start
    last_year = ''
    last_month = ''
    while at <= end:
        if at.strftime('%Y') != last_year:
            if len(last_year) > 0:
                f.write("<br>\n")
            f.write(f"{at.strftime('%Y')}<br>\n")
            last_month = ''
            last_year = at.strftime('%Y')
        if at.strftime("%b") != last_month:
            f.write(f'&nbsp;<a target="_self" href="#{at.strftime('%Y-%m-%d')}">{at.strftime('%b')}</a><br>\n')
            last_month = at.strftime("%b")
        at += timedelta(days=1)
    f.write('</div></div>\n')
    f.write('<div id="right" class="column"><div class="bottom">')

    at = start
    while at <= end:
        cur = at.strftime("%Y-%m-%d")
        if cur in data.data:
            value = data.data[cur]
        else:
            # We have nothing for this day, just show a place holder
            value = {"at": cur, "title": "(missing)"}
        
        f.write(f"<span id=\"{cur}\">{at.strftime('%B')} {at.strftime('%d').lstrip('0')}, {at.strftime('%Y')}. {html.escape(value['title'])}</span><br>\n")

        if 'tweet' in value or 'json' in value:
            if 'tweet' in value:
                f.write(f'<a href="{value['tweet']}">')

            if '1' in value:
                f.write(f'<img loading="lazy" src="{github(value['1'])}">\n')
            else:
                f.write('<span class="missing"></span>\n')

            if '2' in value:
                f.write(f'<img loading="lazy" src="{github(value['2'])}">\n')
            else:
                f.write('<span class="missing"></span>\n')

            if 'tweet' in value:
                f.write("</a>")

            if 'json' in value:
                img_dn = os.path.join("images", at.strftime("%Y"), at.strftime("%m"))
                if not os.path.isdir(img_dn):
                    os.makedirs(img_dn)
                img_fn = os.path.join(img_dn, cur + ".png")
                if not os.path.isfile(img_fn):
                    with open(value['json']) as f_puzzle:
                        temp = json.load(f_puzzle)
                    print("Create image for " + cur)
                    im = show_puzzle(temp)
                    im.thumbnail((300, 300))
                    im.save(img_fn)
                url = f"https://github.com/Q726kbXuN/vertex/blob/master/data/{at.strftime('%Y')}/{at.strftime('%m')}/{cur}.json"
                f.write(f'<span class="obj"><a href="{url}"><img loading="lazy" src="{github(img_fn)}">')
                if at.strftime("%Y-%m-%d") in youtube:
                    url = youtube[at.strftime("%Y-%m-%d")]
                    f.write(f'<a href="{url}" class="youtube"></a>')
                f.write('</a></span>\n')
            else:
                f.write('<span class="missing"></span>\n')

            f.write("<br>\n")

        # print(f"{value['at']} {'json' if 'json' in value else '    '} {'t1' if '1' in value else '  '} {'t2' if '2' in value else '  '} {value['title']}")
        # print(data.data[key])
        at += timedelta(days=1)
    f.write('</div></div>\n')
    f.write('''</body></html>\n''')