#!/usr/bin/env python3
r"""Write the demo flow as MiNiFi C++ config.yml (conf/config.yml).

v2 (default): ListFile(<work>/clips) -> ExtractVideoFrames (python, conf/ExtractVideoFrames.py)
v1:           ExecuteProcess(frames.sh) -> GetFile(<work>/in) -> UpdateAttribute(video.clip/frame)
then, both:
  -> ClassifyImage(TractModelService places, Places365 ResNet18; attribute `scene`, content untouched)
  -> DetectObject(TractModelService yolo, yolov8s) -> DrawBoundingBox -> PutFile(<work>/out)
                                                 \-> AttributesToJSON -> UpdateAttribute(.json) -> PutFile(<work>/meta)
Every failure goes to its own PutFile under <work>/fail/<stage>. Nothing listens on a port.

The paths are written as the tokens @MINIFI_HOME@ and @WORK_DIR@. scripts/run-agent.sh fills
them in when it lays the flow over an agent, and flow/efm_flow.py fills them in for the EFM class.

    python3 flow/build_flow.py [--version v2] [--fps 1] [--max-seconds 0] [--mask pdr] [--conf 0.35]
"""
import argparse
import os
import uuid
import yaml

ap = argparse.ArgumentParser()
ap.add_argument("--model", default="yolov8s-split-norm.onnx")
ap.add_argument("--conf", default="0.35", help="DetectObject confidence threshold")
ap.add_argument("--version", default="v2", choices=["v1", "v2"])
ap.add_argument("--fps", default="1", help="frames sampled per second of video (0.25 under NanoStream)")
ap.add_argument("--max-seconds", default="0", help="0 reads the whole clip")
ap.add_argument("--mask", default="pdr", choices=["none", "pdr"], help="pdr masks the sample clip's burned-in overlay")
ap.add_argument("--home", default="@MINIFI_HOME@")
ap.add_argument("--work", default="@WORK_DIR@")
ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "conf", "config.yml"))
a = ap.parse_args()

HOME, W = a.home, a.work
NS = uuid.UUID("0b1ec7de-7ec7-4000-8000-00000000d3e0")
def uid(n):
    return str(uuid.uuid5(NS, n))
procs, conns = [], []

def proc(name, cls, props, period="1 sec", auto=(), strategy="TIMER_DRIVEN"):
    procs.append({"name": name, "id": uid(name), "class": cls,
                  "scheduling strategy": strategy, "scheduling period": period,
                  "auto-terminated relationships list": list(auto), "Properties": props})

def conn(src, rel, dst):
    conns.append({"name": f"{src}/{rel}/{dst}", "id": uid(f"{src}/{rel}/{dst}"),
                  "source id": uid(src), "source relationship names": [rel],
                  "destination id": uid(dst), "max work queue size": 2000,
                  "max work queue data size": "512 MB", "flowfile expiration": "0 sec"})

def sink(stage):
    name = f"fail-{stage}"
    proc(name, "PutFile", {"Directory": f"{W}/fail/{stage}", "Conflict Resolution Strategy": "replace",
                           "Create Missing Directories": "true"}, auto=("success", "failure"))
    return name

if a.version == "v1":
    proc("frames", "ExecuteProcess", {"Command": f"{HOME}/bin-demo/frames.sh", "Redirect Error Stream": "true"},
         period="30 sec", auto=("success",))
    proc("get-frames", "GetFile", {"Input Directory": f"{W}/in", "File Filter": r".*\.jpg",
                                   "Minimum File Age": "2 sec", "Batch Size": "4", "Recurse Subdirectories": "false"})
    proc("tag-frame", "UpdateAttribute", {
        "video.clip": "${filename:substringBeforeLast('__')}",
        "video.frame": "${filename:substringAfterLast('__'):substringBefore('.')}",
        "mime.type": "image/jpeg"})
    head = "tag-frame"
else:
    proc("list-clips", "ListFile", {"Input Directory": f"{W}/clips", "File Filter": r".*\.mp4",
                                    "Recurse Subdirectories": "false", "Minimum File Age": "5 sec"}, period="10 sec")
    proc("extract-frames", "org.apache.nifi.minifi.processors.ExtractVideoFrames", {
        "Frames Per Second": a.fps, "Max Width": "1280", "JPEG Quality": "85",
        "Start Seconds": "0", "Max Seconds": a.max_seconds, "Mask HUD": a.mask}, auto=("original",))
    head = "extract-frames"
# ClassifyImage writes its Top-K into the `scene` attribute and leaves the JPEG alone. With
# Output attribute name empty it would replace the content with its JSON and detect would get no image.
proc("classify", "ClassifyImage", {
    "Tract model service": "places", "Target width": "224", "Target height": "224",
    "Resize mode": "Stretch", "Resize filter": "Bilinear",
    "Color format": "RGB", "Tensor shape format": "CHW", "Pixel divisor": "255.0",
    "Mean": "0.485,0.456,0.406", "Standard Deviation": "0.229,0.224,0.225",
    "Score output index": "0", "Score activation": "Softmax", "Top K": "3", "Confidence Threshold": "0.0",
    "Labels file path": f"{HOME}/models/places365_labels.txt", "Label index offset": "0",
    "Output attribute name": "scene"}, period="0 sec")
proc("detect", "DetectObject", {
    "Tract model service": "yolo", "Target width": "640", "Target height": "640",
    "Resize mode": "Letterbox", "Letterbox pad value": "0.447", "Resize filter": "Bilinear",
    "Color format": "RGB", "Tensor shape format": "CHW",
    "Mean": "0.0", "Standard Deviation": "255.0", "Pixel divisor": "1.0",
    "Score output index": "0", "Box output index": "1", "Box format": "Cxcywh",
    "Score activation": "None", "Confidence Threshold": a.conf, "IoU Threshold": "0.45",
    "Output attribute name": "detections"}, period="0 sec")
proc("draw", "DrawBoundingBox", {"Bounding boxes": "${detections}", "Line color": "#76B900",
                                 "Line thickness": "3"}, period="0 sec")
proc("put-annotated", "PutFile", {"Directory": f"{W}/out", "Conflict Resolution Strategy": "replace",
                                  "Create Missing Directories": "true"}, auto=("success",), period="0 sec")
proc("to-json", "AttributesToJSON", {"Attributes List": "filename,video.clip,video.frame,video.sample,video.t_s,video.width,"
                                                        "video.height,scene,object.count,detections",
                                     "Destination": "flowfile-content", "Include Core Attributes": "false"}, period="0 sec")
proc("json-name", "UpdateAttribute", {"filename": "${filename:substringBeforeLast('.')}.json",
                                      "mime.type": "application/json"}, period="0 sec")
proc("put-meta", "PutFile", {"Directory": f"{W}/meta", "Conflict Resolution Strategy": "replace",
                             "Create Missing Directories": "true"}, auto=("success",), period="0 sec")
# Everything from classify to the last PutFile runs at 0 sec. At the default 1 sec a MiNiFi C++
# processor takes one FlowFile per trigger, and the whole flow runs at exactly 1 frame/s.

if a.version == "v1":
    conn("get-frames", "success", "tag-frame")
else:
    conn("list-clips", "success", "extract-frames")
conn(head, "success", "classify")
conn("classify", "success", "detect")
conn("detect", "success", "draw")
conn("detect", "success", "to-json")
conn("draw", "success", "put-annotated")
conn("to-json", "success", "json-name")
conn("json-name", "success", "put-meta")
fails = [("extract-frames", "failure")] if a.version == "v2" else []
# AttributesToJSON has no failure relationship in 2.26.09; UpdateAttribute has one (EFM validates it).
for src, rel in fails + [("classify", "failure"), ("detect", "failure"), ("draw", "failure"), ("json-name", "failure"),
                 ("put-annotated", "failure"), ("put-meta", "failure")]:
    conn(src, rel, sink(src))

flow = {
    "MiNiFi Config Version": 3,
    "Flow Controller": {"name": f"minifi-detect-{a.version}",
                        "comment": f"flow {a.version}: frames -> ClassifyImage -> DetectObject -> DrawBoundingBox"},
    "Processors": procs,
    "Controller Services": [{"name": "places", "id": uid("places"), "class": "TractModelService",
                             "Properties": {"Model File Path": f"{HOME}/models/resnet18-places365.onnx", "Model format": "Onnx"}},
                            {"name": "yolo", "id": uid("yolo"), "class": "TractModelService",
                             "Properties": {"Model File Path": f"{HOME}/models/{a.model}", "Model format": "Onnx"}}],
    "Connections": conns,
    "Remote Process Groups": [],
}
with open(a.out, "w") as f:
    f.write("# Generated by flow/build_flow.py; edit the script, not this file.\n")
    yaml.safe_dump(flow, f, sort_keys=False, width=200)
print(f"wrote {os.path.normpath(a.out)}: {len(procs)} processors, {len(conns)} connections, model {a.model}")
