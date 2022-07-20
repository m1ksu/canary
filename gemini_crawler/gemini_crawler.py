import Agunua
import math
import networkx as nx
from time import sleep, time
from threading import Thread, Lock
from queue import Queue
import os
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from urllib.parse import urljoin

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
    if not line.startswith("=>") or not len(line) > 2:
        return None
    if not line[2] == " ":
        line = line[:2] + " " + line[2:]  # force whitespace
    try:
        link = line.split()[1]
    except:
        print(line)
        # pass
    if link.startswith("gemini://"):
        return link
    if "://" not in link:
        return ignition.url(link, current_path)
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


def request(uri):
    return Agunua.GeminiUri(uri, insecure=True, accept_expired=True, parse_content=True)


def crawl_uri(uri):
    global G
    with ThreadPoolExecutor(max_workers=1) as executor:
        try:
            future = executor.submit(request, uri)
            resp = future.result(5)
            if resp.error != "No error":
                return
            status = resp.header[0]
            if status == "3":
                if resp.meta is not uri:
                    crawl_uri(resp.meta)
                return
            elif status == "2":
                G_lock.acquire()
                # print(f"{uri} has lock", flush=True)
                try:
                    G.add_node(uri, size=10*math.log(len(resp.payload),
                               10) if len(resp.payload) > 0 else 1)
                    if hasattr(resp, "links") and resp.links is not None:
                        for link in resp.links:
                            if "gemini://" not in link and "://" in link:
                                continue
                            absolute_link = link if "gemini://" in link else urljoin(
                                uri, link)
                            if "gemini://" not in link:
                                print(absolute_link)
                            if absolute_link not in set(G) and absolute_link not in set(bad_uris):
                                uri_queue.put(absolute_link)
                            G.add_edge(uri, absolute_link)
                except Exception as e:
                    log_error(uri, traceback.format_exc())
                finally:
                    G_lock.release()
        except TimeoutError:
            # for pid, process in executor._processes.items():
            #     process.terminate()
            # executor.shutdown()
            pass
        except Exception as e:
            log_error(uri, traceback.format_exc())


def log_error(uri, trace):
    error_log.write(f"{uri}\n\n{trace}\n\n---")
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
        print(
            f"{round(time() - time_start)}s: {len(G.nodes)} nodes; {uri_queue.qsize()} in queue")
        # if len(G.nodes) - last_nodes < 20:
        #     print("Stagnation.")
        #     stag += 1
        #     if stag > 1:
        #         print("printing threadthing")
        #         for thread in threads:
        #             pos = get_thread_position(thread)
        #             write_to(
        #                 thread_log, f"{pos[0]} {pos[1]} {pos[2]} \n{''.join(pos[3])}\n---")
        #         thread_log.flush()
        #         os.fsync(thread_log.fileno())
        #         stag = -10000
        # last_nodes = len(G.nodes)
        sleep(1)


def saver():
    while True:
        sleep(10)
        G_lock.acquire()
        nx.write_gexf(G, "gemini.gexf")
        print("Gemini written.")
        G_lock.release()


uri_queue.put("gemini://gemini.circumlunar.space")
# uri_queue.put("gemini://skyjake.fi/gemlog/images/dutch_baby.jpg")

for _ in range(100):
    thread = Thread(target=crawler)
    thread.start()
    threads.append(thread)

Thread(target=saver).start()
tracker()
