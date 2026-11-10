# ExtractVideoFrames outside the agent: the processor module loaded as MiNiFi C++ loads it, with
# REL_SUCCESS, REL_FAILURE and REL_ORIGINAL injected, against fakes of the native session,
# context and FlowFile, on the repo's own sample clip.
import importlib.util
import os

import cv2
import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE_DIR = os.path.join(ROOT, "sample")
SAMPLE = "dashcam-street-30s.mp4"
FLOW_DEFAULTS = {  # what conf/config.yml sets on extract-frames
    "Frames Per Second": "1", "Max Width": "1280", "JPEG Quality": "85",
    "Start Seconds": "0", "Max Seconds": "0", "Mask HUD": "pdr",
}


def load_processor():
    spec = importlib.util.spec_from_file_location("ExtractVideoFrames", os.path.join(ROOT, "conf", "ExtractVideoFrames.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.REL_SUCCESS, mod.REL_FAILURE, mod.REL_ORIGINAL = "success", "failure", "original"
    return mod


EVF = load_processor()


class FlowFile:
    # The native semantics the processor's _set works around: addAttribute never overwrites,
    # updateAttribute only changes a key that is already there, and every new FlowFile has a
    # numeric filename.
    count = 0

    def __init__(self, attrs=None, content=b""):
        FlowFile.count += 1
        self.attrs = {"filename": str(FlowFile.count), **(attrs or {})}
        self.content = content

    def getAttribute(self, key):
        return self.attrs.get(key, "")

    def addAttribute(self, key, value):
        self.attrs.setdefault(key, value)

    def updateAttribute(self, key, value):
        if key in self.attrs:
            self.attrs[key] = value


class Stream:
    def __init__(self, ff):
        self.ff = ff

    def read(self):
        return self.ff.content

    def write(self, data):
        self.ff.content = bytes(data)


class Session:
    def __init__(self, incoming):
        self.incoming = [incoming]
        self.out = {"success": [], "failure": [], "original": []}

    def get(self):
        return self.incoming.pop() if self.incoming else None

    def create(self):
        return FlowFile()

    def read(self, ff, callback):
        callback.process(Stream(ff))

    def write(self, ff, callback):
        callback.process(Stream(ff))

    def transfer(self, ff, rel):
        self.out[rel].append(ff)


class Context:
    def __init__(self, **props):
        self.props = {**FLOW_DEFAULTS, **{k.replace("_", " "): str(v) for k, v in props.items()}}

    def getProperty(self, name):
        return self.props[name]


def run(clip_ff, **props):
    session = Session(clip_ff)
    EVF.onTrigger(Context(**props), session)
    return session.out


def listed():
    # what ListFile hands on: the folder and the name, opened in place
    return FlowFile({"absolute.path": SAMPLE_DIR, "filename": SAMPLE})


def decode(ff):
    return cv2.imdecode(np.frombuffer(ff.content, np.uint8), cv2.IMREAD_COLOR)


@pytest.fixture(scope="module")
def flow_run():
    return run(listed())


def test_sample_at_the_flow_defaults_gives_run_1s_30_frames(flow_run):
    frames = flow_run["success"]
    assert len(frames) == 30 and not flow_run["failure"]  # the README's "annotated 30  json 30"
    (orig,) = flow_run["original"]
    assert orig.attrs["video.frames.extracted"] == "30"
    a = frames[0].attrs
    assert a["filename"] == "dashcam-street-30s__000001.jpg" and frames[-1].attrs["filename"].endswith("__000030.jpg")
    assert a["video.clip"] == "dashcam-street-30s" and a["video.source"] == SAMPLE
    assert a["mime.type"] == "image/jpeg" and (a["video.width"], a["video.height"]) == ("1280", "720")
    step = round(float(a["video.src_fps"]))
    assert [int(f.attrs["video.frame"]) for f in frames] == [i * step for i in range(30)]
    assert [int(f.attrs["video.sample"]) for f in frames] == list(range(1, 31))
    ts = [float(f.attrs["video.t_s"]) for f in frames]
    assert ts == sorted(ts) and ts[0] == 0.0 and ts[-1] < 30.1
    assert decode(frames[0]).shape == (720, 1280, 3)


def test_pdr_mask_blacks_out_the_hud(flow_run):
    img = decode(flow_run["success"][5])
    h, w = img.shape[:2]
    for fx0, fy0, fx1, fy1 in EVF.HUD_MASKS["pdr"]:
        zone = img[int(fy0 * h) + 8:int(fy1 * h) - 8, int(fx0 * w) + 8:int(fx1 * w) - 8]  # inset past JPEG ringing
        assert zone.max() <= 8
    clean = decode(run(listed(), Mask_HUD="none", Max_Seconds=6)["success"][5])
    assert clean[int(0.76 * h):].max() > 64  # the G/RPM band is there without the mask


def test_window_and_max_width():
    out = run(listed(), Frames_Per_Second=2, Start_Seconds=10, Max_Seconds=5, Max_Width=640)
    frames = out["success"]
    assert len(frames) == 10
    assert all(10.0 <= float(f.attrs["video.t_s"]) < 15.0 for f in frames)
    assert {(f.attrs["video.width"], f.attrs["video.height"]) for f in frames} == {("640", "360")}
    assert decode(frames[0]).shape == (360, 640, 3)


def test_content_without_a_path_is_spooled():
    with open(os.path.join(SAMPLE_DIR, SAMPLE), "rb") as f:
        ff = FlowFile({"filename": SAMPLE}, f.read())
    out = run(ff, Max_Seconds=3)
    assert len(out["success"]) == 3 and out["original"][0].attrs["video.frames.extracted"] == "3"


def test_a_clip_opencv_cannot_open_goes_to_failure():
    out = run(FlowFile({"filename": "broken.mp4"}, b"not a video"))
    assert not out["success"] and not out["original"]
    (ff,) = out["failure"]
    assert ff.attrs["video.error"] == "cannot open broken.mp4"
