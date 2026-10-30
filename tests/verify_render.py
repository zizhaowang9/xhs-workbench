"""Check exact six PNG names and dimensions; visual review remains separate."""
from pathlib import Path
import struct
import sys
folder = Path(sys.argv[1])
names = {'cover.png', *(f'card_{i}.png' for i in range(1, 6))}
actual = {p.name for p in folder.glob('*.png')}
assert actual == names, (actual, names)
for name in sorted(names):
    raw = (folder / name).read_bytes()
    assert raw[:8] == b'\x89PNG\r\n\x1a\n', name
    assert struct.unpack('>II', raw[16:24]) == (1080, 1440), name
print('PASS: six PNGs, each 1080x1440. Content/order still require visual review.')
