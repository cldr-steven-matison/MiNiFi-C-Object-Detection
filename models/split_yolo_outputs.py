#!/usr/bin/env python3
"""Reshape a YOLOv8 ONNX export for MiNiFi C++ DetectObject.

ultralytics exports one output, output0 [1, 4+nc, anchors]: rows 0-3 are cx, cy, w, h in
input pixels, rows 4.. the per-class scores, already sigmoid'ed. DetectObject reads boxes and
scores from two different output tensors (Box output index != Score output index), one row per
box, so this appends Transpose -> [1, anchors, 4+nc] and two Slices:
    output 0  scores  [1, anchors, nc]   -> Score output index 0, Score activation None
    output 1  boxes   [1, anchors, 4]    -> Box output index 1, Box format Cxcywh
--normalize N divides the boxes by N (the input size), for when DetectObject wants [0,1] boxes.

    python split_yolo_outputs.py yolov8s.onnx yolov8s-split.onnx [--normalize 640]
"""
import argparse
import numpy as np
import onnx
from onnx import helper, numpy_helper, TensorProto

ap = argparse.ArgumentParser()
ap.add_argument("src")
ap.add_argument("dst")
ap.add_argument("--normalize", type=float, default=0.0)
a = ap.parse_args()

m = onnx.load(a.src)
g = m.graph
out = g.output[0]
dims = [d.dim_value for d in out.type.tensor_type.shape.dim]
assert len(dims) == 3 and dims[0] == 1, f"expected [1, 4+nc, anchors], got {dims}"
_, rows, anchors = dims
nc = rows - 4

def const(name, arr):
    g.initializer.append(numpy_helper.from_array(np.array(arr, dtype=np.int64), name))
    return name

g.node.append(helper.make_node("Transpose", [out.name], ["yolo_t"], perm=[0, 2, 1]))
g.node.append(helper.make_node("Slice", ["yolo_t", const("s_st", [4]), const("s_en", [rows]), const("s_ax", [2])], ["scores"]))
box_src = "boxes"
if a.normalize:
    box_src = "boxes_px"
g.node.append(helper.make_node("Slice", ["yolo_t", const("b_st", [0]), const("b_en", [4]), const("b_ax", [2])], [box_src]))
if a.normalize:
    g.initializer.append(numpy_helper.from_array(np.array(a.normalize, dtype=np.float32), "box_div"))
    g.node.append(helper.make_node("Div", ["boxes_px", "box_div"], ["boxes"]))

del g.output[:]
g.output.extend([
    helper.make_tensor_value_info("scores", TensorProto.FLOAT, [1, anchors, nc]),
    helper.make_tensor_value_info("boxes", TensorProto.FLOAT, [1, anchors, 4]),
])
onnx.checker.check_model(m)
onnx.save(m, a.dst)
print(f"{a.dst}: scores [1,{anchors},{nc}], boxes [1,{anchors},4]{' /' + str(a.normalize) if a.normalize else ' (input px)'}")
