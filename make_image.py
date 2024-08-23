#!/usr/bin/env python3

from PIL import Image, ImageDraw, ImageFont
import os
import json
import time
from datetime import datetime, timedelta

def show_puzzle(data):
    # Simple helper to decode a Vertex data dump into an image
    min_x, min_y, max_x, max_y = None, None, None, None
    # Run through all of the vertex points and figure out the size of the image
    for key, value in data["vertices"].items():
        x, y = value["coordinates"]
        if min_x is None:
            min_x, min_y, max_x, max_y = x, y, x, y
        else:
            min_x = min(min_x, x)
            max_x = max(max_x, x)
            min_y = min(min_y, y)
            max_y = max(max_y, y)

    # Scale everthing to a big image
    width, height = 1000, 1000
    transparent = False
    length = max(max_x - min_x, max_y - min_y) * 1.1

    # Draw each polygon in turn
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
        # Turn the #rrggbb or #rgb into a normal PIL color tuple
        if len(c) == 4:
            c = (int(c[1], 16) * 17, int(c[2], 16) * 17, int(c[3], 16) * 17) + ((255,) if transparent else tuple())
        else:
            c = (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)) + ((255,) if transparent else tuple())
        # Draw the polygon
        dr.polygon(pts, c)

    return im

def enum_puzzles():
    # Simple helper to enumerate a directory and return the results
    # in alphabetical order
    dirs = ["data"]
    while len(dirs):
        cur_dir = dirs.pop(0)
        for fn in sorted(os.listdir(cur_dir)):
            cur = os.path.join(cur_dir, fn)
            if os.path.isdir(cur):
                dirs.append(cur)
            else:
                yield fn, cur

def main():
    width, height = 50, 50
    target_size = 1000

    images = []
    x, y = 0, 0

    fnt = ImageFont.truetype(os.path.join("images", "OpenSans-Regular.ttf"), 40)
    last_year = "--"

    expected_date = datetime(2019, 12, 20)

    for file_only, fn in enum_puzzles():
        # This is the "image" we're showing on the grid
        temp = {
            "width": width,
            "height": height,
            "fn": fn,
            "file_only": file_only,
            "year": file_only[:4],
        }

        # If we're starting a new year, add a placeholder for the text of the year
        if temp['year'] != last_year:
            if x != 0:
                x = 0
                y += height
            to_disp = f"    {temp['year']}"
            disp_size = fnt.getbbox(to_disp)
            images.append({
                "text": to_disp,
                "x": x,
                "y": y,
                "width": int(disp_size[2]),
                "height": int(disp_size[3] * 1.2),
            })
            y += images[-1]['height']
            last_year = temp['year']

        # If this image skips days after the last one, add "empty" images
        while datetime.strptime(file_only[:10], "%Y-%m-%d") > expected_date:
            images.append({
                "missing": True,
                "width": width,
                "height": height,
                "x": x,
                "y": y,
            })
            x += width
            if x > target_size:
                x = 0
                y += height
            expected_date += timedelta(days=1)

        # Finally, add the image to the list of things to do
        temp["x"] = x
        temp["y"] = y
        images.append(temp)

        # Update the date we expect to see
        expected_date += timedelta(days=1)
        # And move to the next spot in the grid
        x += width
        if x > target_size:
            x = 0
            y += height

    # Draw the placeholder image
    missing_size = 1000
    square_size = 150
    empty = Image.new('RGB', (missing_size, missing_size), (255, 255, 255))
    empty_draw = ImageDraw.Draw(empty)
    for xi, x in enumerate(range(square_size // 2, missing_size - (square_size // 2), square_size)):
        for yi, y in enumerate(range(square_size // 2, missing_size - (square_size // 2), square_size)):
            if (xi + yi) % 2 == 0:
                empty_draw.rectangle((x, y, x+square_size, y+square_size), (225, 225, 255))
    empty.thumbnail((width, height))

    # Figure out how big the final image needs to be
    width = max((x['width'] + x['x']) for x in images)
    height = max((x['height'] + x['y']) for x in images)

    # Add some padding and move evertyhing over a bit
    width += 20
    height += 20
    for cur in images:
        cur['x'] += 10
        cur['y'] += 10

    im = Image.new('RGB', (width, height), (255, 255, 255))
    dr = ImageDraw.Draw(im)
    last_year = "--"

    next_msg = time.time()
    for i, cur in enumerate(images):
        if 'missing' in cur:
            # Just place the "empty" image
            im.paste(empty, (cur['x'], cur['y']))
        elif 'text' in cur:
            # Draw the year
            dr.text((cur['x'], cur['y']), cur['text'], (0, 0, 0), fnt)
        else:
            # Decode the data into an image and place it on the final image
            if time.time() >= next_msg:
                next_msg += 0.5
                print(f"Working on {i}: {cur['fn']}")
            with open(cur['fn']) as f:
                data = json.load(f)
            temp = show_puzzle(data)
            temp.thumbnail((cur['width'], cur['height']))
            im.paste(temp, (cur['x'], cur['y']))
            temp.close()

    im.save(os.path.join("images", "preview.png"))
    print("Done!")

if __name__ == "__main__":
    main()
