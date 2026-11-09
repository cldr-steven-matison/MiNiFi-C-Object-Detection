#!/usr/bin/env python3
"""Export CSAIL Places365 ResNet18 to ONNX for ClassifyImage, batch pinned to 1, plus a clean labels file.
   python3 -I export_places365.py resnet18_places365.pth.tar categories_places365.txt resnet18-places365.onnx places365_labels.txt
Run with the venv models/make-models.sh makes (torch, torchvision). The checkpoint loads with weights_only=True."""
import sys
import torch
import torchvision
src, cats, out_onnx, out_labels = sys.argv[1:]
ck = torch.load(src, map_location="cpu", weights_only=True)
sd = {k.replace("module.", ""): v for k, v in ck["state_dict"].items()}
m = torchvision.models.resnet18(num_classes=365)
m.load_state_dict(sd)
m.eval()
torch.onnx.export(m, torch.zeros(1, 3, 224, 224), out_onnx, input_names=["input"], output_names=["logits"],
                  opset_version=17, dynamo=False)
with open(cats) as f:
    names = [line.split(" ")[0][3:].replace("/", " ") for line in f.read().splitlines()]
with open(out_labels, "w") as f:
    f.write("\n".join(names) + "\n")
print("exported", out_onnx, len(names), "labels")
