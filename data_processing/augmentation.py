"""Training-only image transformations used by the experiments."""

import torch
from torch.nn import functional as F


def augment(images):
    """Per-image horizontal flip (p=.5), reflected translation up to 4 px."""
    n = len(images)
    flip = torch.rand(n) < 0.5
    images = torch.where(flip[:, None, None, None], images.flip(-1), images)
    padded = F.pad(images, (4, 4, 4, 4), mode="reflect")
    dy, dx = torch.randint(0, 9, (2, n))
    return padded[
        torch.arange(n)[:, None, None],
        0,
        dy[:, None, None] + torch.arange(48)[None, :, None],
        dx[:, None, None] + torch.arange(48)[None, None, :],
    ].unsqueeze(1)


def augment_t35(x, photometric=False):
    x = augment(x)
    if photometric:
        # Per image contrast in [.9,1.1] and brightness offset in [-.05,.05].
        contrast = 0.9 + 0.2 * torch.rand(len(x), 1, 1, 1)
        brightness = 0.1 * torch.rand(len(x), 1, 1, 1) - 0.05
        mean = x.mean((2, 3), keepdim=True)
        x = ((x - mean) * contrast + mean + brightness).clamp(0, 1)
    return x


def seeded_augment(x, g):
    n = len(x)
    flip = torch.rand(n, generator=g) < 0.5
    x = torch.where(flip[:, None, None, None], x.flip(-1), x)
    padded = F.pad(x, (4, 4, 4, 4), mode="reflect")
    dy, dx = torch.randint(0, 9, (2, n), generator=g)
    return padded[
        torch.arange(n)[:, None, None],
        0,
        dy[:, None, None] + torch.arange(48)[None, :, None],
        dx[:, None, None] + torch.arange(48)[None, None, :],
    ].unsqueeze(1)
