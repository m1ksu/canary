from unittest import async_case
import ignition
import math
import networkx as nx
from time import sleep, time
from threading import Thread, Lock, get_ident
from multiprocessing.pool import ThreadPool
from queue import Queue
import os
import sys
import traceback

error_log = open("error_log.txt", "a") 
req_log = open("request_log.txt", "a")
thread_log = open("thread_log.txt", "a")
G = nx.Graph()
G_lock = Lock()
start_time = time()
uri_queue = Queue()
threads = []
stag = 0
bad_uris = []

def line_to_uri(line, current_path):
	if not line.startswith("=>") or not len(line) > 2: return None
	if not line[2] == " ": line = line[:2] + " " + line[2:] # force whitespace
	try:
		link = line.split()[1]
	except:
		print(line)
		# pass
	if link.startswith("gemini://"): return link
	if "://" not in link: return ignition.url(link, current_path)
	return None

def get_links(text, current_path):
	result = []
	for line in text.splitlines():
		link = line_to_uri(line, current_path)
		if link is not None:
			result.append(link)
	return result

def write_to(f, text):
	f.write(f"{text}\n")
	f.flush()
	os.fsync(f.fileno())

def crawl_uri(uri):
	global G
	try:
		resp = ignition.request(uri)
		status = resp.status[0]
		if status == "3":
			# if stag == True:
			# 	print(f"Redirected from {uri}")
			if ignition.url(resp.data()) == uri:
				return
			else:
				crawl_uri(resp.data())
		elif status == "2":
			G_lock.acquire()
			# if stag:
			# 	print("lock!")
			G.add_node(uri, size=10*math.log(len(resp.data()), 10) if len(resp.data()) > 0 else 1)
			if resp.meta == "" or resp.meta.startswith("text/"):
				for link_uri in get_links(resp.data(), uri):
					if link_uri not in set(G) and link_uri not in set(bad_uris):
						uri_queue.put(link_uri)
					G.add_edge(uri, link_uri)
			G_lock.release()
			# if stag:
			# 	print("Release!")
	except TypeError:
		pass
	except Exception as e:
		error_log.write(f"{uri}\n\n{traceback.format_exc()}\n\n---")
		error_log.flush()
		os.fsync(error_log.fileno())

def crawler():
	while True:
		crawl_uri(uri_queue.get())

def get_thread_position(thread):
    frame = sys._current_frames().get(thread.ident, None)
    if frame:
        return frame.f_code.co_filename, frame.f_code.co_name, frame.f_code.co_firstlineno, traceback.extract_stack(frame).format()

def tracker():
	global stag
	time_start = time()
	last_nodes = -1
	while True:
		print(f"{round(time() - time_start)}s: {len(G.nodes)} nodes; {uri_queue.qsize()} in queue")
		if len(G.nodes) == last_nodes:
			# print("Stagnation.")
			stag += 1
			if stag > 6:
				for thread in threads:
					pos = get_thread_position(thread)
					if "G_lock.acquire()" in ''.join(pos[3]): continue
					write_to(thread_log, f"{pos[0]} {pos[1]} {pos[2]} \n{''.join(pos[3])}\n---")
				stag = -10000
		else: stag = 0
		last_nodes = len(G.nodes)
		sleep(1)

def saver():
	while True:
		sleep(20)
		G_lock.acquire()
		G_lock_owner = get_ident()
		nx.write_gexf(G, "gemini.gexf")
		G_lock.release()

uri_queue.put("gemini://gemini.circumlunar.space")

for _ in range(500):
	thread = Thread(target=crawler)
	thread.start()
	threads.append(thread)

Thread(target=saver).start()
tracker()