"""T3 models; T2 BasicCNN stays untouched. All models use [N,1,48,48]."""
import torch
from torch import nn
from src.model import BasicCNN
from src.dataset import LABELS


class BatchNormCNN(BasicCNN):
    """Same widths, pools, classifier and dropout as T2; add only BatchNorm."""
    def __init__(self):
        super().__init__()
        layers = []
        # Reuse the freshly initialized T2 layers, so a matched seed gives the
        # control and BN variant exactly the same initial Conv/Linear weights.
        for layer in self.features:
            layers.append(layer)
            if isinstance(layer, nn.Conv2d):
                layers.append(nn.BatchNorm2d(layer.out_channels))
        self.features = nn.Sequential(*layers)


class ResidualBlock(nn.Module):
    def __init__(self, source, target, stride=1):
        super().__init__()
        self.branch = nn.Sequential(
            nn.Conv2d(source, target, 3, stride, 1, bias=False), nn.BatchNorm2d(target), nn.ReLU(),
            nn.Conv2d(target, target, 3, 1, 1, bias=False), nn.BatchNorm2d(target))
        self.shortcut = nn.Identity() if source == target and stride == 1 else nn.Sequential(
            nn.Conv2d(source, target, 1, stride, bias=False), nn.BatchNorm2d(target))
        self.relu = nn.ReLU()

    def forward(self, x):
        return self.relu(self.branch(x) + self.shortcut(x))


class SmallResNet(nn.Module):
    """18-layer residual CNN, width 16; 3x3 stride-1 grayscale stem, no maxpool.

    Four stages [2,2,2,2], widths 16/32/64/128, spatial 48/24/12/6.
    Random initialization only; no pretrained weights or external data.
    """
    def __init__(self):
        super().__init__()
        layers = [nn.Conv2d(1, 16, 3, padding=1, bias=False), nn.BatchNorm2d(16), nn.ReLU()]
        source = 16
        for i, target in enumerate([16, 32, 64, 128]):
            layers.extend([ResidualBlock(source, target, 1 if i == 0 else 2),
                           ResidualBlock(target, target)])
            source = target
        self.features = nn.Sequential(*layers)
        self.classifier = nn.Sequential(nn.AdaptiveAvgPool2d(1), nn.Flatten(), nn.Dropout(0.3),
                                        nn.Linear(128, 7))

    def forward(self, images):
        if images.ndim != 4 or tuple(images.shape[1:]) != (1, 48, 48):
            raise ValueError('Expected [N,1,48,48]')
        return self.classifier(self.features(images))


def make_model(name):
    return {'basic': BasicCNN, 'batchnorm': BatchNormCNN, 'resnet18_w16': SmallResNet}[name]()


def load_t3(path):
    checkpoint = torch.load(path, map_location='cpu', weights_only=True)
    if (checkpoint.get('format_version') != 3 or tuple(checkpoint['labels']) != LABELS
            or checkpoint.get('preprocessing') != 'float32 / 255; [N,1,48,48]'):
        raise ValueError('Incompatible T3 checkpoint')
    model = make_model(checkpoint['config']['model'])
    model.load_state_dict(checkpoint['model_state_dict'], strict=True)
    return model.eval(), checkpoint
