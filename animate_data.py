#!/usr/bin/env python3

from PIL import Image, ImageDraw, ImageFont
import json, multiprocessing, os, random, shutil, subprocess, sys, time

USE_NVENC = False
VERIFY_SIZE = False
SECOND_FRAMES = False
OUTPUT_FN = None

def clean_data(data):
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

def show_puzzle(data, transparent=False, solid_color=None, appear=None, decay=None):
    # Simple helper to decode a Vertex data dump into an image

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
    width, height = 2000, 2000
    length = max(max_x - min_x, max_y - min_y) * 1.1

    # Draw each polygon in turn
    im = Image.new('RGBA' if transparent else 'RGB', (width, height), (0,0,0,0) if transparent else (255, 255, 255))
    dr = ImageDraw.Draw(im)

    for i, c in enumerate(data["palette"]):
        # Turn the #rrggbb or #rgb into a normal PIL color tuple
        if len(c) == 4:
            c = (int(c[1], 16) * 17, int(c[2], 16) * 17, int(c[3], 16) * 17) + ((255,) if transparent else tuple())
        else:
            c = (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)) + ((255,) if transparent else tuple())
        data['palette'][i] = c

    for shape in data["shapes"]:
        if shape.get('isPreDrawn', False) or shape.get('sides', 0) > 0:
            # Only draw "pre drawn" shapes, or ones with partial sides
            pts = []
            for cur in shape["vertices"]:
                x, y = data["vertices"][str(cur)]["coordinates"]
                x = ((x - ((min_x + max_x) / 2)) / (length / 2)) * (width / 2) + (width / 2)
                y = ((y - ((min_y + max_y) / 2)) / (length / 2)) * (height / 2) + (height / 2)
                pts.append((x, y))
            
            if decay is not None:
                center_x = sum(pt[0] for pt in pts) / len(pts)
                center_y = sum(pt[1] for pt in pts) / len(pts)
                perc = (1 - (decay * 0.75))
                pts = [(pt[0] * perc + center_x * (1 - perc), pt[1] * perc + center_y * (1 - perc)) for pt in pts]

            if not shape.get('isPreDrawn', False):
                # This means we should just draw some of the sides, so do that
                for i in range(shape.get('sides', 0)):
                    dr.line((pts[i], pts[(i+1) % len(pts)]), (0, 0, 0), 2)
            else:
                # Otherwise, draw the solid color
                if solid_color is None:
                    c = data["palette"][int(shape["color"])]
                    if decay is not None:
                        c = (int(c[0] * (1 - decay) + 255 * decay), int(c[1] * (1 - decay) + 255 * decay), int(c[2] * (1 - decay) + 255 * decay))
                else:
                    c = solid_color
                # Draw the polygon
                dr.polygon(pts, c)

    to_show = [x for x in data['vertices'].values() if x['hits'] > 0]

    if appear is not None:
        to_show.sort(key=lambda x: x['coordinates'][0] ** 2 + x['coordinates'][1] ** 2)
        to_show = to_show[:int(len(to_show) * appear)]

    # Run through and draw the circles for the vertix points
    for vertex in to_show:
        x, y = vertex["coordinates"]
        x = ((x - ((min_x + max_x) / 2)) / (length / 2)) * (width / 2) + (width / 2)
        y = ((y - ((min_y + max_y) / 2)) / (length / 2)) * (height / 2) + (height / 2)
        dr.circle((x, y), vertex['hits'] + 4 * 2, (255,255,255), (0,0,0), 2)

    return im

def get_filenames(target):
    bail = -1
    if (isinstance(target, str) and target == "all") or isinstance(target, tuple):
        dirs = ["data"]
        while len(dirs) and bail != 0:
            cur_dir = dirs.pop(0)
            for fn in sorted(os.listdir(cur_dir)):
                cur = os.path.join(cur_dir, fn)
                if os.path.isdir(cur):
                    dirs.append(cur)
                else:
                    if isinstance(target, tuple):
                        if target[0] <= fn <= target[1]:
                            yield cur
                    else:
                        yield cur
                    bail -= 1
                    if bail == 0:
                        break
    else:
        yield target

def get_items(target, full_data=True):
    # Load data
    frame_no = 0
    left = 0
    files_left = 0
    total_files = 0

    for fn in get_filenames(target):
        with open(fn) as f:
            data = json.load(f)
        clean_data(data)
        left += sum(1 for x in data['shapes'] if not x.get('isPreDrawn', False))
        files_left += 1
        total_files += 1

    for fn in get_filenames(target):
        files_left -= 1
        with open(fn) as f:
            data = json.load(f)
        clean_data(data)

        # Build up a list of frames to draw
        cur_vertex = None
        cur_shape = None
        todo = []
        first = True
        # Vertices we've touched, these are next to use
        vertices_to_use = []
        while True:
            if cur_shape is None:
                if not first:
                    # Figure out the shape to draw, after the first frame
                    while True:
                        if cur_vertex is not None:
                            # Ok, we've already picked a vertex to work on, find the next shape to work on
                            to_pick = [data['shapes'][int(x)] for x in cur_vertex['shapes'] if not data['shapes'][int(x)].get('isPreDrawn', False)]
                            if len(to_pick) == 0:
                                # There are no shapes left for this vertex
                                cur_vertex = None
                            else:
                                # We found something to do, break out of this loop
                                break
                        if cur_vertex is None:
                            # We finished our current vertex (or the first time), so find the next biggest vertex
                            while len(vertices_to_use) > 0:
                                # We've touched some other vertex, so use the next one
                                cur_vertex = data['vertices'][vertices_to_use.pop(-1)]
                                if cur_vertex['hits'] > 0:
                                    break
                                cur_vertex = None
                        if cur_vertex is None:
                            # Nothing left we've touched, just find something else
                            temp = list(data['vertices'].values())
                            temp.sort(key=lambda x:x['hits'])
                            cur_vertex = temp[-1]
                            if cur_vertex['hits'] == 0:
                                break
                    if len(to_pick) == 0:
                        # All done doing all the things
                        break
                    # Finally, pick a shape, just pick at random
                    cur_shape = random.choice(to_pick)
                else:
                    first = False

            if cur_shape is not None:
                for vertex in cur_shape['vertices']:
                    if str(vertex) not in vertices_to_use:
                        vertices_to_use.append(str(vertex))
                # When we're working on a shape, show an edge till we've shown them all
                cur_shape['sides'] = cur_shape.get('sides', 0) + 1
                if cur_shape['sides'] == 4:
                    # All sides shown, just draw this shape
                    cur_shape['isPreDrawn'] = True
                    cur_shape = None
                    left -= 1

            # Note the number of hits for each vertex that are left
            for vertex in data['vertices'].values():
                vertex['hits'] = 0

            for shape in data["shapes"]:
                if not shape.get('isPreDrawn', False):
                    for cur in shape["vertices"]:
                        data["vertices"][str(cur)]["hits"] += 1

            # Save this frame as something to do, using json.dumps here as a simple deep-copy
            if full_data:
                todo.append({"source": fn, "left": left, "data": json.dumps(data), "frames": 1, "files_left": files_left})
            else:
                todo.append({"source": fn, "left": left, "frames": 1, "files_left": files_left})

        # Add a little animation on the first and last state
        temp = []
        for i in range(31):
            temp.append(todo[0].copy())
            temp[-1]['appear'] = i / 30
            temp[-1]['type'] = i
        # Hold on the state before drawing for 0.5 seconds
        temp[-1]['frames'] = 30

        temp.extend(todo[1:-1])
        for i in range(31):
            temp.append(todo[-1].copy())
            temp[-1]['decay'] = i / 30
            if i == 0:
                if total_files == 1:
                    # Hold on the state when we're done for 5.0 seconds
                    temp[-1]['frames'] = 60 * 5
                else:
                    # Hold on the state when we're done for 1.0 seconds
                    temp[-1]['frames'] = 60
            else:
                temp[-1]['type'] = 30 - i
        todo = temp

        # Fill out the frame numbers
        for cur in todo:
            cur['frame_no'] = frame_no
            frame_no += cur['frames']
            yield cur
        yield frame_no

def make_daily():
    global OUTPUT_FN

    data_fn = os.path.join("output", "daily.json")
    if os.path.isfile(data_fn):
        with open(data_fn) as f:
            data = json.load(f)
    else:
        data = {}
        
    for fn in get_filenames("all"):
        if os.path.isfile("abort.txt"):
            break
        at = fn.replace("\\", "/").split("/")[-1][:10]
        if at not in data:
            target_dir = os.path.join("output", at[:4], at[5:7])
            if not os.path.isdir(target_dir):
                os.makedirs(target_dir)
            target_file = os.path.join(target_dir, at + ".mp4")
            OUTPUT_FN = target_file

            print(f"Creating {at}...")
            sys.argv = sys.argv[0:1] + [fn]
            main()

            with open(fn) as f:
                temp = json.load(f)
            data[at] = {"at": at, "video": "/".join([at[:4], at[5:7], at + ".mp4"]), "theme": temp['theme']}
            with open(data_fn, "wt", newline="", encoding="utf-8") as f:
                json.dump(data, f, indent=4, sort_keys=True)
                f.write("\n")
            with open(os.path.join("images", "youtube.jsonl"), "wt", encoding="utf-8", newline="") as f:
                for key, value in data.items():
                    if 'youtube' in value:
                        f.write(json.dumps([key, value['youtube'], value['theme']]) + "\n")

def make_chunks():
    chunks = [
        ["2019-01-01", "2019-12-31"],
        ["2020-01-01", "2020-05-31"],
        ["2020-06-01", "2020-12-31"],
        ["2021-01-01", "2021-12-31"],
        ["2022-01-01", "2022-03-31"],
        ["2022-04-01", "2022-06-30"],
        ["2022-07-01", "2022-09-30"],
        ["2022-10-01", "2022-12-31"],
        ["2023-01-01", "2023-03-31"],
        ["2023-04-01", "2023-06-30"],
        ["2023-07-01", "2023-09-30"],
        ["2023-10-01", "2023-12-31"],
        ["2024-01-01", "2024-03-31"],
        ["2024-04-01", "2024-06-30"],
        ["2024-07-01", "2024-09-30"],
    ]
    for target in chunks:
        sys.argv = sys.argv[0:1] + target
        main()

_second_offset = 0
def set_offset(val):
    global _second_offset
    _second_offset = val

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

def main():
    if len(sys.argv) == 3:
        target = (sys.argv[1], sys.argv[2])
    elif len(sys.argv) == 2:
        target = sys.argv[1]
        if target == "daily":
            make_daily()
            exit(0)
        elif target == "chunks":
            make_chunks()
            exit(0)
        if target != "all":
            if not os.path.isfile(target):
                target = None
    else:
        target = None
    
    if target is None:
        print("Usage: ")
        print("  <filename> = Animate a specific file")
        print("  all = Animate all files")
        print("  chunks = Make predefined chunks")
        print("  daily = Create an animation for each day")
        exit(0)

    if VERIFY_SIZE:
        counts = [x for x in get_items(target, full_data=False) if isinstance(x, dict)]
        total_days = len(set(x['source'] for x in counts))
        frames = sum(x['frames'] for x in counts)
        frames = frames // 60
        print(f"This will make a video of {frames//3600}:{(frames%3600)//60:02d}:{frames%60:02d} long for {total_days} days.")
        yn = input("Continue? [y/(n)] ")
        if yn != "y":
            exit(0)

    for dn in ["frames", "output"] + (["frames2"] if SECOND_FRAMES else []):
        if not os.path.isdir(dn):
            os.mkdir(dn)

    for cur in os.listdir("frames"):
        os.unlink(os.path.join("frames", cur))

    # Spin off to the workers to do the work
    occasional = OccasionalMessage(1)
    new_frames = 0
    global _second_offset
    with multiprocessing.Pool(initializer=set_offset, initargs=(_second_offset,)) as pool:
        for msg in pool.imap_unordered(worker, get_items(target)):
            if isinstance(msg, int):
                new_frames = msg
            else:
                occasional(msg)

    _second_offset += new_frames

    cmd = [
        'ffmpeg', 
        "-y", "-hide_banner", 
        '-framerate', '60', 
        '-i', os.path.join('frames', 'frame_%08d.png'), 
    ]
    if USE_NVENC:
        cmd += [
            '-c:v', 'h264_nvenc', 
            '-profile', 'high444p', 
            '-pixel_format', 'yuv444p', 
            '-preset', 'default', 
        ]

    if OUTPUT_FN is not None:
        cmd.append(OUTPUT_FN)
    elif isinstance(target, tuple):
        cmd.append(os.path.join("output", "vertex_" + target[0] + "_" + target[1] + ".mp4"))
    else:
        cmd.append(os.path.join("output", "vertex_" + target.replace("\\", "/").split("/")[-1] + ".mp4"))
    print("$ " + " ".join(cmd))
    subprocess.check_call(cmd)

_fnt_header, _fnt_footer = None, None
def worker(job):
    # Simple hack to return the total number of frames to the caller
    if isinstance(job, int):
        return job
    # Load the data and draw it
    data = json.loads(job['data'])
    im = show_puzzle(data, appear=job.get('appear'), decay=job.get('decay'))

    # Add some text
    global _fnt_header, _fnt_footer
    if _fnt_header is None:
        _fnt_header = ImageFont.truetype(os.path.join("images", "OpenSans-Regular.ttf"), 70)
        _fnt_footer = ImageFont.truetype(os.path.join("images", "OpenSans-Regular.ttf"), 40)
    dr = ImageDraw.Draw(im)

    # Simple helper to outline text
    def draw_text(x, y, val, fnt):
        for ox in range(-2, 3):
            for oy in range(-2, 3):
                dr.text((x + ox, y + oy), val, (255, 255, 255), fnt)
        dr.text((x, y), val, (0, 0, 0), fnt)

    # Draw the "Theme" at the top
    if 'type' in job:
        draw_text(10, 10, data['theme'][:job['type']], _fnt_header)
    else:
        draw_text(10, 10, data['theme'], _fnt_header)
        # And draw the number of remaining shapes at the bottom
        left = sum(1 for x in data['shapes'] if not x.get('isPreDrawn', False))
        left = f"{left:,}"
        size = _fnt_footer.getbbox(left)
        draw_text(1000 - size[2] // 2, 2000 - (size[3] + 10), left, _fnt_footer)
        date = job['source'].replace("\\", "/").split("/")[-1][:10]
        size = _fnt_footer.getbbox(date)
        draw_text(2000 - (size[2] + 10), 2000 - (size[3] + 10), date, _fnt_footer)

    # Shrink the image down
    im.thumbnail((1580, 1040))
    im_big = Image.new('RGB', (1920, 1080), (255, 255, 255))
    im_big.paste(im, ((im_big.width - im.width) // 2, (im_big.height - im.height) // 2))

    # Save out the frame
    make_fn = lambda x: os.path.join("frames", f"frame_{x:08d}.png")
    make_fn_2 = lambda x: os.path.join("frames2", f"frame_{x+_second_offset:08d}.png")
    source_fn = make_fn(job['frame_no'])
    im_big.save(source_fn, 'PNG', compress_level=1)
    if SECOND_FRAMES:
        shutil.copy(source_fn, make_fn_2(job['frame_no']))
    im_big.close()
    im.close()

    # Copy it if we need more copies
    for frame in range(job['frame_no']+1, job['frame_no'] + job['frames']):
        shutil.copy(source_fn, make_fn(frame))
        if SECOND_FRAMES:
            shutil.copy(source_fn, make_fn_2(frame))

    data_fn = job['source'].replace("\\", "/").split("/")[-1]
    target_fn = source_fn.replace("\\", "/").split("/")[-1]
    return f"Done with {data_fn}:{target_fn}, {job['left']:,} tris to show, {job['files_left']:,} files left"

if __name__ == "__main__":
    main()
