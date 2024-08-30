#!/usr/bin/env python3

from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import io, json, multiprocessing, os, sys, time

def show_puzzle(data, transparent=False, solid_color=None):
    # Simple helper to decode a Vertex data dump into an image

    # Normalize from different formats to a single format of data
    for key in ['vertices', 'shapes', 'palettes']:
        if key not in data and 'body' in data and key in data['body']:
            data[key] = data['body'][key]
    if 'palettes' in data and 'palette' not in data:
        data['palette'] = data['palettes']
    if isinstance(data["vertices"], list):
        data["vertices"] = {str(i): x for i, x in enumerate(data["vertices"])}
    if 'shapes' not in data['vertices']["0"]:
        for vertex in data['vertices'].values():
            vertex['shapes'] = []
        for i, shape in enumerate(data['shapes']):
            for vertex in shape['vertices']:
                if i not in data['vertices'][str(vertex)]['shapes']:
                    data['vertices'][str(vertex)]['shapes'].append(i)

    # Run through all of the vertex points and figure out the size of the image
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

    # Scale everthing to a big image
    width, height = 1000, 1000
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
        if solid_color is None:
            c = int(shape["color"])
            c = data["palette"][c]
            # Turn the #rrggbb or #rgb into a normal PIL color tuple
            if len(c) == 4:
                c = (int(c[1], 16) * 17, int(c[2], 16) * 17, int(c[3], 16) * 17) + ((255,) if transparent else tuple())
            else:
                c = (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)) + ((255,) if transparent else tuple())
        else:
            c = solid_color
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

class OccasionalMessage:
    def __init__(self, delay=0.5):
        self.delay = delay
        self.next_msg = time.time()
    def __call__(self, value):
        now = time.time()
        if now >= self.next_msg:
            while now >= self.next_msg:
                self.next_msg += self.delay
            print(value)

def load_single_image(fn):
    with open(fn) as f:
        data = json.load(f)
    im = show_puzzle(data)
    output_fn = os.path.join("images", "single_image.png")
    im.save(output_fn)
    print(f"File {fn} saved as {output_fn}")

def shadow_worker(cur):
    cur['msg'] = f"Working on {cur['i']} shadow: {cur['fn']}"
    with open(cur['fn']) as f:
        data = json.load(f)
    shadow = show_puzzle(data, transparent=True, solid_color=(64, 64, 64))
    shadow.thumbnail((cur['width'], cur['height']), Image.Resampling.LANCZOS)
    shadow = ImageOps.expand(shadow, (cur['width'], cur['height']), (0, 0, 0, 0))
    shadow = shadow.filter(ImageFilter.BoxBlur(cur['width']//15))
    bits = io.BytesIO()
    shadow.save(bits, 'PNG')
    cur['bits'] = bits.getvalue()
    shadow.close()
    return cur

def draw_worker(cur):
    if 'fn' in cur:
        # Decode the data into an image and place it on the final image
        with open(cur['fn']) as f:
            data = json.load(f)
        cur['msg'] = f"Working on {cur['i']}: {cur['fn']}"
        temp = show_puzzle(data, transparent=True)
        temp.thumbnail((cur['width'], cur['height']), Image.Resampling.LANCZOS)
        bits = io.BytesIO()
        temp.save(bits, 'PNG')
        cur['bits'] = bits.getvalue()
        temp.close()
    return cur

def main():
    if len(sys.argv) == 2:
        load_single_image(sys.argv[1])
        exit(0)

    width, height = 50, 50
    target_size = 1000

    images = []
    x, y = 0, 0

    fnt = ImageFont.truetype(os.path.join("images", "OpenSans-Regular.ttf"), 40)
    last_year = "--"

    expected_date = None

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

        # Note where we start
        if expected_date is None:
            expected_date = datetime(
                year=int(file_only[0:4]),
                month=int(file_only[5:7]),
                day=int(file_only[8:10]),
            )

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
    empty = Image.new('RGBA', (missing_size, missing_size), (0, 0, 0, 0))
    empty_draw = ImageDraw.Draw(empty)
    for xi, x in enumerate(range(square_size // 2, missing_size - (square_size // 2), square_size)):
        for yi, y in enumerate(range(square_size // 2, missing_size - (square_size // 2), square_size)):
            empty_draw.rectangle((x, y, x+square_size, y+square_size), (225, 225, 225, 255) if (xi + yi) % 2 == 0 else (255, 255, 255, 255))
    empty.thumbnail((width, height), Image.Resampling.LANCZOS)

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

    occasional = OccasionalMessage()

    for i, cur in enumerate(images):
        cur['i'] = i

    with multiprocessing.Pool() as pool:
        # Run through and draw drop shadows for all of the images
        for cur in pool.imap(shadow_worker, [x for x in images if 'fn' in x]):
            occasional(cur['msg'])
            bits = io.BytesIO(cur['bits'])
            shadow = Image.open(bits)
            im.paste(shadow, (cur['x']-cur['width']+(cur['width']//25), cur['y']-cur['height']+(cur['height']//25)), shadow)
            shadow.close()

        # And create the images themselves
        for cur in pool.imap(draw_worker, images):
            if 'missing' in cur:
                # Just place the "empty" image
                im.paste(empty, (cur['x'], cur['y']), empty)
            elif 'text' in cur:
                # Draw the year
                dr.text((cur['x'], cur['y']), cur['text'], (0, 0, 0), fnt)
            elif 'fn' in cur:
                # Draw the decoded image
                occasional(cur['msg'])
                bits = io.BytesIO(cur['bits'])
                temp = Image.open(bits)
                im.paste(temp, (cur['x'], cur['y']), temp)
                temp.close()
            else:
                raise Exception()

    im.save(os.path.join("images", "preview.png"))
    print("Done!")

if __name__ == "__main__":
    main()
