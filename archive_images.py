#!/usr/bin/env python3

import sqlite3
import os
import io
import time
import multiprocessing
import sys
from PIL import Image

class OccasionalMessage:
    def __init__(self, delay=0.5):
        self.delay = delay
        self.next_msg = time.time()
    def trigger(self):
        now = time.time()
        if now >= self.next_msg:
            while now >= self.next_msg:
                self.next_msg += self.delay
            return True
        return False

def loader(dn, queue, workers):
    bail = -1
    for fn in os.listdir(dn):
        bail -= 1
        if bail == 0:
            break
        if os.path.isfile("abort.txt"):
            break
        queue.put(fn)
    for _ in range(workers):
        queue.put(None)

def worker(dn, queue, queue_done):
    while True:
        fn = queue.get()
        if fn is None:
            queue_done.put((None, None))
            break
        im = Image.open(os.path.join(dn, fn))
        bits = io.BytesIO()
        im.save(bits, 'PNG', compress_level=9)
        data = bits.getvalue()
        queue_done.put((fn, data))

def main():
    if len(sys.argv) != 3:
        print("Usage:")
        print("  <dn> <db_name> = Archive all files in <dn> to <db_name>")
        exit(1)

    dn = sys.argv[1]
    db = sqlite3.connect(sys.argv[2])
    db.execute("CREATE TABLE IF NOT EXISTS frames (filename TEXT PRIMARY KEY, data BLOB NOT NULL) WITHOUT rowid;")
    db.commit()

    workers = multiprocessing.cpu_count()
    queue = multiprocessing.Queue(workers * 4)
    queue_done = multiprocessing.Queue(workers * 4 + 100)
    procs = [multiprocessing.Process(target=worker, args=(dn, queue, queue_done)) for _ in range(workers)]
    procs.append(multiprocessing.Process(target=loader, args=(dn, queue, workers)))
    [x.start() for x in procs]

    done = 0

    occasional = OccasionalMessage(5)
    to_insert = []
    to_delete = []
    left = sum(1 for x in os.listdir(dn))

    def dump_todo():
        nonlocal to_insert, to_delete
        if len(to_insert) > 0:
            db.executemany("INSERT INTO frames(filename, data) VALUES (?, ?);", to_insert)
            db.commit()
            to_insert = []
        if len(to_delete) > 0:
            for fn in to_delete:
                os.unlink(fn)
            to_delete = []

    last_done = 0
    while workers > 0:
        fn, data = queue_done.get()
        if fn is None:
            workers -= 1
        else:
            to_insert.append((fn, data))
            to_delete.append(os.path.join(dn, fn))
            if len(to_insert) >= 1000:
                dump_todo()
            done += 1
            left -= 1
            if occasional.trigger():
                print(f"Left: {left:,} / Done: {done:,} (+{done-last_done:,}) / Wrote {fn} with {len(data):,} bytes")
                last_done = done

    dump_todo()
    [x.join() for x in procs]
    print("All done")

if __name__ == "__main__":
    main()
