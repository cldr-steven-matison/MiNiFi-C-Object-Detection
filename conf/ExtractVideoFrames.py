# ExtractVideoFrames: a MiNiFi C++ Python processor (native minifi_native style).
#
# One video clip in, one JPEG FlowFile per sampled frame out: the piece MiNiFi C++ 2.26.09's
# image processors (DetectObject, ClassifyImage, DrawBoundingBox) need in front of them and
# that the release does not ship. The sampling, resize and HUD mask are the ones
# NanoStream's dashcam_walker.py uses against the Hailo daemon, so both engines see the same
# frames.
#
# Input: a FlowFile from ListFile (attributes absolute.path + filename; the clip is opened in
# place, no content copy) or any FlowFile whose content is the clip (spooled to a temp file).
# Out: success, one per frame, with filename <stem>__<sample>.jpg and the video.* attributes;
# original, the input with video.frames.extracted; failure, a clip cv2 cannot open.
# Frames go out when the clip is done (one session per clip): cap a long clip with Max Seconds.
# Deps (requirements.txt beside this file, installed into MiNiFi's own venv):
# opencv-python-headless 4.8.1.78 and numpy < 2.
import os
import tempfile

import cv2

HUD_MASKS = {
    # Corvette Performance Data Recorder (the sample clip): speed top-left, gear ring top-right,
    # G-force and RPM band across the bottom. Add your own camera's overlay zones here.
    "pdr": [(0.03, 0.02, 0.19, 0.22), (0.83, 0.02, 0.96, 0.22), (0.0, 0.76, 1.0, 1.0)],
    "none": [],
}


class _Bytes:
    def __init__(self, data):
        self.data = data

    def process(self, output_stream):
        output_stream.write(self.data)
        return len(self.data)


class _Spool:
    def __init__(self, path):
        self.path = path

    def process(self, input_stream):
        data = input_stream.read()
        with open(self.path, "wb") as f:
            f.write(data)
        return len(data)


def describe(processor):
    processor.setDescription(
        "Samples a video clip into JPEG frames, one FlowFile per frame, with the clip name, "
        "frame number and timestamp as attributes. Opens the clip in place when the FlowFile "
        "carries absolute.path and filename (ListFile), else spools the content.")


def onInitialize(processor):
    processor.addProperty("Frames Per Second", "Frames sampled per second of video.", "2", True, False)
    processor.addProperty("Max Width", "Frames wider than this are scaled down, aspect kept.", "1280", True, False)
    processor.addProperty("JPEG Quality", "JPEG quality, 1-100.", "85", True, False)
    processor.addProperty("Start Seconds", "Skip this many seconds at the start of the clip.", "0", True, False)
    processor.addProperty("Max Seconds", "Stop after this many seconds of video; 0 reads the whole clip.", "0", True, False)
    processor.addProperty("Mask HUD", "Black out a burned-in overlay before the frame leaves: none or pdr (Corvette PDR).",
                          "none", True, False)


def _prop(context, name, cast):
    return cast(context.getProperty(name))


def _set(ff, key, value):
    # addAttribute leaves an existing attribute alone (every new FlowFile already has a numeric
    # filename), and updateAttribute does nothing for a key that is not there yet. getAttribute
    # does not return None for a missing key, so testing it first leaves every video.* attribute
    # unset. Call both: one creates, the other overwrites.
    ff.addAttribute(key, value)
    ff.updateAttribute(key, value)


def _mask(frame, zones):
    if not zones:
        return frame
    h, w = frame.shape[:2]
    for fx0, fy0, fx1, fy1 in zones:
        frame[int(fy0 * h):int(fy1 * h), int(fx0 * w):int(fx1 * w)] = 0
    return frame


def onTrigger(context, session):
    clip_ff = session.get()
    if clip_ff is None:
        return
    fps = _prop(context, "Frames Per Second", float)
    max_w = _prop(context, "Max Width", int)
    quality = _prop(context, "JPEG Quality", int)
    start_s = _prop(context, "Start Seconds", float)
    max_s = _prop(context, "Max Seconds", float)
    zones = HUD_MASKS.get(context.getProperty("Mask HUD").strip().lower(), [])

    name = clip_ff.getAttribute("filename") or "clip.mp4"
    folder = clip_ff.getAttribute("absolute.path")
    path, spooled = None, None
    if folder:
        path = folder if os.path.isfile(folder) else os.path.join(folder, name)
    if not path or not os.path.isfile(path):
        fd, spooled = tempfile.mkstemp(suffix=os.path.splitext(name)[1] or ".mp4")
        os.close(fd)
        session.read(clip_ff, _Spool(spooled))
        path = spooled

    try:
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            _set(clip_ff, "video.error", f"cannot open {name}")
            session.transfer(clip_ff, REL_FAILURE)
            return
        src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        step = max(1, int(round(src_fps / fps)))
        first = int(start_s * src_fps)
        last = int((start_s + max_s) * src_fps) if max_s > 0 else None
        stem = os.path.splitext(name)[0]
        i, n = -1, 0
        while True:
            if not cap.grab():
                break
            i += 1
            if i < first or (i - first) % step:
                continue
            if last is not None and i >= last:
                break
            ok, frame = cap.retrieve()
            if not ok:
                continue
            if frame.shape[1] > max_w:
                s = max_w / frame.shape[1]
                frame = cv2.resize(frame, (max_w, int(frame.shape[0] * s)), interpolation=cv2.INTER_AREA)
            ok, jpg = cv2.imencode(".jpg", _mask(frame, zones), [cv2.IMWRITE_JPEG_QUALITY, quality])
            if not ok:
                continue
            n += 1
            ff = session.create()
            for k, v in {
                "filename": f"{stem}__{n:06d}.jpg", "mime.type": "image/jpeg",
                "video.clip": stem, "video.source": name, "video.frame": str(i), "video.sample": str(n),
                "video.t_s": f"{i / src_fps:.2f}", "video.src_fps": f"{src_fps:.2f}",
                "video.width": str(frame.shape[1]), "video.height": str(frame.shape[0]),
            }.items():
                _set(ff, k, v)
            session.write(ff, _Bytes(jpg.tobytes()))
            session.transfer(ff, REL_SUCCESS)
        cap.release()
        _set(clip_ff, "video.frames.extracted", str(n))
        _set(clip_ff, "video.src_fps", f"{src_fps:.2f}")
        session.transfer(clip_ff, REL_ORIGINAL)
    finally:
        if spooled:
            os.unlink(spooled)
