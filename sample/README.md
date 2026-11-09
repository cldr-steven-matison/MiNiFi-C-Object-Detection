# The sample clip

`dashcam-street-30s.mp4`: 30 s of dashcam footage from a Corvette Performance Data Recorder, 1280×720 H.264 at about 30.5 fps, cut from a longer drive with `ffmpeg -ss 240 -t 30 -c copy`. It starts on a street with traffic and a pedestrian on the shoulder.

The recorder burns its telemetry into the picture (speed top-left, the gear ring top-right, the G-force and RPM band across the bottom). The flow's `Mask HUD pdr` blacks those zones out before inference; without it, the detector calls the gear ring a clock. Use `Mask HUD none` for your own clean footage.

At the flow's default 1 frame per second, the clip is about 30 frames.
