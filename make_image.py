#!/usr/bin/env python3

from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import io, json, multiprocessing, os, sys

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
    im = Image.new('RGBA' if transparent else 'RGB', (width, height), (255, 255, 255, 0) if transparent else (255, 255, 255))
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

def load_single_image(fn):
    with open(fn) as f:
        data = json.load(f)
    im = show_puzzle(data)
    output_fn = os.path.join("images", "single_image.png")
    im.save(output_fn)
    print(f"File {fn} saved as {output_fn}")

def draw_worker(cur):
    # Decode the data into an image and place it on the final image
    with open(cur.fn) as f:
        data = json.load(f)

    temp = show_puzzle(data, transparent=True)
    temp.thumbnail((cur.width, cur.height), Image.Resampling.LANCZOS)
    bits = io.BytesIO()
    temp.save(bits, 'PNG')
    image_bits = bits.getvalue()
    temp.close()

    temp = show_puzzle(data, transparent=True, solid_color=(100, 100, 100))
    shadow_border = 10
    border_x = shadow_border * (temp.width // cur.width)
    border_y = shadow_border * (temp.height // cur.height)
    temp = ImageOps.expand(temp, (border_x, border_y), (255, 255, 255, 0))
    temp = temp.filter(ImageFilter.BoxBlur(cur.width * 1.25))
    temp.thumbnail((cur.width + shadow_border * 2, cur.height + shadow_border * 2), Image.Resampling.LANCZOS)
    bits = io.BytesIO()
    temp.save(bits, 'PNG')
    shadow_bits = bits.getvalue()
    temp.close()

    return cur.i, image_bits, shadow_bits, shadow_border

class Layout:
    def __init__(self, max_width=None, padding=0):
        self.objects = []
        self.row = []
        self.padding = padding
        self.x = padding
        self.y = padding
        self.max_width = max_width

    def add_elem(self, obj, move_offset=True):
        if move_offset and self.max_width is not None and len(self.row) > 0:
            if self.x + obj.width + self.padding >= self.max_width:
                self.new_row()
        self.objects.append(obj)
        self.row.append(obj)
        obj.x = self.x
        obj.y = self.y
        if move_offset:
            self.x += obj.width

    def new_row(self):
        if len(self.row) > 0:
            self.x = self.padding
            self.y += max(obj.height for obj in self.row)
            self.row = []

    def draw(self):
        width = max(obj.x + obj.width + self.padding for obj in self.objects)
        height = max(obj.y + obj.height + self.padding for obj in self.objects)
        im = Image.new('RGB', (width, height), (255, 255, 255))
        dr = ImageDraw.Draw(im)
        # Draw each layer in turn
        for layer in ["shadow", "image", "text"]:
            for obj in self.objects:
                if layer in obj.layers:
                    # This object wants to be drawn on this layer, so let it draw itself
                    obj.draw(layer, im, dr)
        return im

class ObjBase:
    def __init__(self, width, height, layers):
        self.x = 0
        self.y = 0
        self.width = width
        self.height = height
        self.layers = layers

class ObjText(ObjBase):
    def __init__(self, val, font_size):
        self.val = val
        self.fnt = ImageFont.truetype(os.path.join("images", "OpenSans-Regular.ttf"), font_size)
        bbox = self.fnt.getbbox(val)
        super().__init__(bbox[2], int(bbox[3] * 1.1), {"text"})
    def draw(self, layer, im, dr):
        dr.text((self.x, self.y), self.val, (0, 0, 0), self.fnt)

class ObjBlank(ObjBase):
    def __init__(self, layers):
        super().__init__(70, 70, layers)
    def draw(self, layer, im, dr):
        pass

class ObjMissing(ObjBlank):
    TARGET = None
    def __init__(self):
        super().__init__({"image"})
    def draw(self, layer, im, dr):
        if ObjMissing.TARGET is None:
            missing_size = 1000
            square_size = 150
            empty = Image.new('RGBA', (missing_size, missing_size), (0, 0, 0, 0))
            empty_draw = ImageDraw.Draw(empty)
            for xi, x in enumerate(range(square_size // 2, missing_size - (square_size // 2), square_size)):
                for yi, y in enumerate(range(square_size // 2, missing_size - (square_size // 2), square_size)):
                    empty_draw.rectangle((x, y, x+square_size, y+square_size), (225, 225, 225, 255) if ((xi + yi) % 2 == 0) else (255, 255, 255, 255))
            empty.thumbnail((self.width, self.height), Image.Resampling.LANCZOS)
            ObjMissing.TARGET = empty
        im.paste(ObjMissing.TARGET, (self.x, self.y), ObjMissing.TARGET)
    
class ObjImage(ObjBlank):
    def __init__(self, file_only, fn):
        super().__init__({"image", "shadow"})
        self.file_only = file_only
        self.fn = fn
    def draw(self, layer, im, dr):
        bits = io.BytesIO(self.image if (layer == "image") else self.shadow)
        temp = Image.open(bits)
        im.paste(temp, (self.x - (0 if (layer == "image") else self.shadow_border), self.y - (0 if (layer == "image") else self.shadow_border)), temp)
        temp.close()

def main():
    if len(sys.argv) == 2:
        load_single_image(sys.argv[1])
        exit(0)

    layout = Layout(padding=5)

    # Find all the images
    last_at = None
    images = []
    for file_only, fn in enum_puzzles():
        at = datetime.strptime(file_only[:10], "%Y-%m-%d")
        if last_at is not None:
            # Add Nones for any skipped days
            last_at += timedelta(days=1)
            while last_at < at:
                images.append((last_at, None, None))
                last_at += timedelta(days=1)
        images.append((at, file_only, fn))
        last_at = at

    last_at = None
    for at, file_only, fn in images:
        # If we're at the start, or a new year, add a year header
        if last_at is None or last_at.strftime("%Y") != at.strftime("%Y"):
            layout.new_row()
            layout.add_elem(ObjText(at.strftime("%Y"), 40))
            layout.new_row()
            while len(layout.row) < (at.weekday() + 1) % 7:
                layout.add_elem(ObjBlank(set()))

        # Add the placeholder image, or the real image
        if file_only is None:
            layout.add_elem(ObjMissing())
        else:
            layout.add_elem(ObjImage(file_only, fn))

        # If we're at a new month, then add the month info
        # This is too noisy, try another way?
        # if last_at is None or last_at.strftime("%b") != at.strftime("%b"):
        #     obj = ObjText(at.strftime("%b"), 20)
        #     layout.add_elem(obj, move_offset=False)
        #     obj.x = layout.objects[-2].x
        #     obj.y = layout.objects[-2].y

        # If we've shown 14 images, then go ahead and move to a new row
        if sum(1 for x in layout.row if issubclass(type(x), ObjBlank)) >= 14:
            layout.new_row()

        last_at = at

    # Prepare the data for all of the images
    todo = []
    for i, cur in enumerate(layout.objects):
        if isinstance(cur, ObjImage):
            cur.i = i
            todo.append(cur)

    # Draw everything in a pool to speed it up a bit    
    with multiprocessing.Pool() as pool:
        for i, image, shadow, shadow_border in pool.imap_unordered(draw_worker, todo):
            layout.objects[i].image = image
            layout.objects[i].shadow = shadow
            layout.objects[i].shadow_border = shadow_border

    # And finally draw all the things
    im = layout.draw()
    im.save(os.path.join("images", "preview.png"))
    print("Done!")

if __name__ == "__main__":
    main()
