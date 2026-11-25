"""Write an original 48 × 48 grayscale test pattern to a new path."""
import argparse
from pathlib import Path

from PIL import Image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    image = Image.new("L", (48, 48))
    image.putdata([(x * 5 + y * 3) % 256 for y in range(48) for x in range(48)])
    with args.output.open("xb") as output:
        image.save(output, format="PNG")


if __name__ == "__main__":
    main()
