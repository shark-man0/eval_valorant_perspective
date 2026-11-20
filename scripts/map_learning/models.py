from __future__ import annotations

from torch import nn


class PortraitCNN(nn.Module):
    """Classifies a center crop without the minimap outline."""

    def __init__(self, classes: int):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 16, 3),
            nn.ReLU(),
            nn.Conv2d(16, 24, 3),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(24, 32, 3),
            nn.ReLU(),
            nn.Conv2d(32, 40, 3),
            nn.ReLU(),
        )
        self.output = nn.Linear(40 * 2 * 2, classes)

    def forward(self, image):
        return self.output(self.features(image).flatten(1))


class MarkerCNN(nn.Module):
    """Predicts centered recorder-rim evidence on a stride-two dense lattice."""

    receptive_field = 19
    stride = 2

    def __init__(self):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 8, 7, stride=2),
            nn.ReLU(),
            nn.Conv2d(8, 12, 3),
            nn.ReLU(),
            nn.Conv2d(12, 12, 3),
            nn.ReLU(),
            nn.Conv2d(12, 8, 3),
            nn.ReLU(),
            nn.Conv2d(8, 1, 1),
        )

    def forward(self, image):
        return self.features(image)
