import ignition
import matplotlib.pyplot as plt
import math
import os
import networkx as nx
from time import sleep, time
from copy import deepcopy
from threading import Thread, Lock
from queue import Queue
from concurrent.futures import ThreadPoolExecutor

G = nx.Graph()
lock = Lock()
start_time = time()
halt = False
uris = Queue()

def line_to_uri(line, source):
	if not line.startswith("=>"): return None
	link = line.split()[1]
	if link.startswith("gemini://"): return link
	if "://" not in link: return ignition.url(link, source)
	return None

def crawl_queue():
	global G
	while True:
		if halt: 
			break
		try:
			lock.acquire()
			if uris.qsize() == 0: 
				lock.release()
				continue
			uri = uris.get()
			lock.release()
			resp = ignition.request(uri)
			status = resp.status[0]
			if status == "3":
				if ignition.url(resp.data()) == uri: break
				uris.put(resp.data())
				break
			elif status == "2":
				sublinks = []
				# if type(resp.data() == str): # TODO: handle things that fail this - could data be readable still?
				for line in resp.data().splitlines():
					link = line_to_uri(line, uri)
					if link != None:
						if not G.has_node(link):
							lock.acquire()
							uris.put(link)
							lock.release()
						sublinks.append(link)
				lock.acquire()
				G.add_node(uri, size=10*math.log(10, len(resp.data())))
				for sublink in sublinks:
					G.add_edge(uri, sublink)
				lock.release()
		except Exception as e:
			raise e

# def crawl_threaded(uri):
	# crawler = Thread(target=crawl_site, args=(uri,))
	# crawler.start()

def stop_it():
	global halt

	time_start = time()
	# while time() - time_start < 1200:
	while time() - time_start < 1400:
		sleep(1)

	halt = True
	os._exit(1)

def progress():
	time_start = time()
	while True:
		print(f"{round(time() - time_start)}s: {len(G.nodes)} nodes")
		sleep(10)
		save()

def save():
	lock.acquire()
	nx.write_gexf(G, "gemini.gexf")
	lock.release()

# crawl_threaded("gemini://gemini.circumlunar.space")
# ThreadPoolExecutor(max_workers=500)
uris.put("gemini://gemini.circumlunar.space")
for _ in range(500):
	Thread(target=crawl_queue).start()
Thread(target=progress).start()
stop_it()