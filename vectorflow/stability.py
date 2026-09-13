"""Conservative temporal noise reduction without blending moving edges or cuts."""
import numpy as np


class Stabilizer:
    def __init__(self):
        self.previous = None

    def apply(self, rgb):
        current = rgb.astype(np.float32)
        if self.previous is not None and current.shape == self.previous.shape:
            delta = np.max(np.abs(current-self.previous), axis=2)
            # A broad change resets history; local motion remains unblended.
            if float(np.mean(delta)) < 18:
                quiet = delta < 10
                current[quiet] = .65*current[quiet] + .35*self.previous[quiet]
        self.previous = current
        return np.rint(current).astype(np.uint8)
