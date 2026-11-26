"""Independent width-controlled, randomly initialized small-image ResNet18."""

import torch
from torch import nn
from model_design.cnn_variants import ResidualBlock
from data_processing.dataset import LABELS


class ResNet18(nn.Module):
    def __init__(self, width):
        super().__init__()
        if width not in (16, 32):
            raise ValueError("Only preregistered widths 16/32")
        self.width = width
        layers = [
            nn.Conv2d(1, width, 3, padding=1, bias=False),
            nn.BatchNorm2d(width),
            nn.ReLU(),
        ]
        source = width
        for i, target in enumerate([width, width * 2, width * 4, width * 8]):
            layers += [
                ResidualBlock(source, target, 1 if i == 0 else 2),
                ResidualBlock(target, target),
            ]
            source = target
        self.features = nn.Sequential(*layers)
        self.head = nn.Sequential(
            nn.AdaptiveAvgPool2d(1), nn.Flatten(), nn.Dropout(0.3), nn.Linear(source, 7)
        )
        for m in self.modules():
            if isinstance(m, (nn.Conv2d, nn.Linear)):
                nn.init.kaiming_normal_(m.weight, mode="fan_out", nonlinearity="relu")
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.ones_(m.weight)
                nn.init.zeros_(m.bias)

    def forward(self, x):
        if x.ndim != 4 or tuple(x.shape[1:]) != (1, 48, 48):
            raise ValueError("Expected N,1,48,48")
        return self.head(self.features(x))


def load(path):
    cp = torch.load(path, map_location="cpu", weights_only=True)
    if (
        cp.get("format_version") != 37
        or tuple(cp["labels"]) != LABELS
        or cp["preprocessing"] != "float32 / 255; [N,1,48,48]"
    ):
        raise ValueError("Invalid contract")
    model = ResNet18(cp["config"]["width"])
    model.load_state_dict(cp["model"], strict=True)
    return model.eval(), cp
