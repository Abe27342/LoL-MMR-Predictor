from riotwatcher import RiotWatcher
from collections import defaultdict
from json import load, dump
import os
from datetime import datetime, timedelta
from riotwatcher import LoLException, error_404, error_429
import time

key = 'RGAPI-dc4a4568-8f39-4536-8cbd-5dd767808a15'

rw = RiotWatcher(key)
item_list = rw.static_get_item_list()

with open('data/static/items.json', 'w') as fp:
	dump(item_list, fp)
