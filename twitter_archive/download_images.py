#!/usr/bin/env python3

from datetime import datetime, timedelta
import os
import shutil
import subprocess

subprocess.check_call(["gallery-dl", "--cookies-from-browser", "Chrome", "https://x.com/vertexarchive"])

existing, new = 0, 0

epoch = datetime(1970, 1, 1)
source_dir = os.path.join('gallery-dl', 'twitter', 'VertexArchive')
for cur in sorted(os.listdir(source_dir)):
    if not cur.endswith(".part"):
        tweet_id, extra = cur.split("_", 1)
        at = epoch + timedelta(seconds=((int(tweet_id) / (2 ** 22)) + 1288834974657) / 1000)
        dest_dir = os.path.join(at.strftime("%Y"), at.strftime("%m"))
        if not os.path.isdir(dest_dir):
            os.makedirs(dest_dir)
        dest_file = os.path.join(dest_dir, at.strftime("%Y-%m-%d-%H-%M-%S") + "_" + extra)
        if not os.path.isfile(dest_file):
            print(f"{cur} -> {dest_file}")
            shutil.copyfile(os.path.join(source_dir, cur), dest_file)
            new += 1
        else:
            existing += 1

print(f"Done, {existing} existing, and {new} new")
