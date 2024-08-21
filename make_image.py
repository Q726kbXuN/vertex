#!/usr/bin/env python3

from PIL import Image, ImageDraw
import os
import json

def show_puzzle(data):
    min_x, min_y, max_x, max_y = None, None, None, None
    for key, value in data["vertices"].items():
        x, y = value["coordinates"]
        if min_x is None:
            min_x, min_y, max_x, max_y = x, y, x, y
        else:
            min_x = min(min_x, x)
            max_x = max(max_x, x)
            min_y = min(min_y, y)
            max_y = max(max_y, y)

    width, height = 1000, 1000
    transparent = False
    length = max(max_x - min_x, max_y - min_y) * 1.1

    im = Image.new('RGBA' if transparent else 'RGB', (width, height), (0,0,0,0) if transparent else (255, 255, 255))
    dr = ImageDraw.Draw(im)
    for shape in data["shapes"]:
        pts = []
        for cur in shape["vertices"]:
            x, y = data["vertices"][str(cur)]["coordinates"]
            x = ((x - ((min_x + max_x) / 2)) / (length / 2)) * (width / 2) + (width / 2)
            y = ((y - ((min_y + max_y) / 2)) / (length / 2)) * (height / 2) + (height / 2)
            pts.append((x, y))
        c = int(shape["color"])
        c = data["palette"][c]
        if len(c) == 4:
            c = (int(c[1:2]+c[1:2], 16), int(c[2:3]+c[2:3], 16), int(c[3:4]+c[3:4], 16)) + ((255,) if transparent else tuple())
        else:
            c = (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)) + ((255,) if transparent else tuple())
        dr.polygon(pts, c)

    return im

def enum_puzzles():
    dirs = ["data"]
    while len(dirs):
        cur_dir = dirs.pop(0)
        for cur in sorted(os.listdir(cur_dir)):
            cur = os.path.join(cur_dir, cur)
            if os.path.isdir(cur):
                dirs.append(cur)
            else:
                yield cur

def main():
    width, height = 50, 50
    target_size = 1000

    images = []
    x, y = 0, 0

    for cur in enum_puzzles():
        images.append({
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "fn": cur,
        })

        x += width
        if x > target_size:
            x = 0
            y += height

    width = max((x['width'] + x['x']) for x in images)
    height = max((x['height'] + x['y']) for x in images)

    im = Image.new('RGB', (width, height), (255, 255, 255))
    for cur in images:
        print(cur['fn'])
        with open(cur['fn']) as f:
            data = json.load(f)
        temp = show_puzzle(data)
        temp.thumbnail((cur['width'], cur['height']))
        im.paste(temp, (cur['x'], cur['y']))

    im.save("preview.png")

if __name__ == "__main__":
    main()
