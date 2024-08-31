#!/usr/bin/env python3

import os

def walk_dir(dirname, exts):
    for dirname, dirnames, filenames in os.walk(dirname):
        for fn in filenames:
            if fn.split(".")[-1] in exts:
                yield fn[:10], os.path.join(dirname, fn)

class Data:
    def __init__(self):
        self.data = {}
    def add(self, at, group, fn):
        if at not in self.data:
            self.data[at] = {"at": at}
        self.data[at][group] = fn

data = Data()
for at, fn in walk_dir('twitter_archive', {"png"}):
    data.add(at, fn.split("_")[2][0], fn)
for at, fn in walk_dir('data', {'json'}):
    data.add(at, 'json', fn)
for key in sorted(data.data):
    print(data.data[key])
