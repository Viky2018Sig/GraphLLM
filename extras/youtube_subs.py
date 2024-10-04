#!/usr/bin/python3

import requests
import xml.etree.ElementTree as ET
import sys

videoUrl="https://www.youtube.com/watch?v=Ic-7n8tIpPw"
if len(sys.argv) > 1:
  videoUrl = sys.argv[1]
print("opening video " + videoUrl, file=sys.stderr)
r = requests.get(videoUrl)
with open("/tmp/w2.txt","w") as f:
    f.write(r.text)

import json
with open("/tmp/w2.txt") as f:
    data = f.read()

print("looking for audio/subtitles tracks", file=sys.stderr)
cdata = data[data.find('"captions"')+11:]
decoder = json.JSONDecoder()
obj,idx = decoder.raw_decode(cdata)
b = obj['playerCaptionsTracklistRenderer']

tracceAudio = [ (el[0],el[1]["defaultCaptionTrackIndex"]) for el in enumerate(b['audioTracks']) if "defaultCaptionTrackIndex" in el[1]]
print("trovate tracce audio:",len(tracceAudio), file=sys.stderr)
tracceTesto = b["captionTracks"]
print("trovate tracce testo:",len(tracceTesto), file=sys.stderr)
ordineLingue = [".en",".it","a.en","a.it"]

sottotitolo = None
for lingua in ordineLingue:
    val = [el for el in tracceTesto if el["vssId"] == lingua]
    if len(val) > 0:
        sottotitolo = val[0]
        break
if sottotitolo:
    print("trovato sottotitolo:",sottotitolo,file=sys.stderr)
sottotitolUrl = sottotitolo["baseUrl"]
print("downloading subtitle:",sottotitolUrl, file=sys.stderr)

r = requests.get(sottotitolUrl)
with open("/tmp/w3.txt","w") as f:
    f.write(r.text)

tree = ET.fromstring(r.text)
caps = tree.findall("text")

sottotitoli = []
for el in caps:
    val = {}
    for k in el.keys():
        val[k] = el.get(k)
    val["text"] = el.text
    sottotitoli.append(val)

print("saving subtitles: /tmp/yt_transcript.txt", file=sys.stderr)
with open("/tmp/w4.txt","w") as f:
    for el in sottotitoli:
        _ = f.write(f"[{el['start']}]\n{el['text']}\n" )

with open("/tmp/w4.txt","r") as f:
    val = f.read()

# remove fractional seconds from timestamp
import re
val=re.sub(r"^\[(\d+)\.\d+\]",r"[\1s]",val,flags=re.M)

with open("/tmp/yt_transcript.txt","w") as f:
    _ = f.write(val)