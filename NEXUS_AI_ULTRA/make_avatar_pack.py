"""Build a .nexus-avatar pack with up to eight mouth shapes from images you made yourself.

    python make_avatar_pack.py portrait.png expressions.png my.nexus-avatar
    python make_avatar_pack.py portrait.png expressions.png my.nexus-avatar --shapes 1,2,3,4,5

portrait.png     transparent 8-bit RGBA PNG of the person (same rules as a normal import).
expressions.png  one sheet of matching frames of the SAME person. Cells run left to right, top to
                 bottom: cell 0 = eyes closed (blink); then one cell per mouth shape, in the order
                 given by --shapes (default 1..8). The default sheet is a 3x3 grid; with three
                 shapes or fewer it is the original 2x2 grid.

Mouth shapes (the app uses the nearest frame you provide for any shape you leave out):
    1 slightly parted (t d n s l)    2 round "o u w"        3 wide open "a"      4 wide smile "e i"
    5 lips pressed (m b p)           6 teeth on lip (f v)   7 pursed (sh ch r)   8 half open (uh h k g)

Every frame is placed with the same face boxes as the original pack. If your frames need other
boxes, pass --rig rig.json (a full rig, validated the same way as inside a pack).
Run it from this folder, with the NEXUS virtual environment, so the pack is checked by the app's own
validation before it is written.
"""
import argparse
import copy
import io
import json
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nexus.human_avatar import DEFAULT_RIG, parse_import  # noqa: E402


def build_rig(shapes, grid):
    rig = copy.deepcopy(DEFAULT_RIG)
    # Shapes 1-3 keep the tuned boxes of the original pack; the new shapes start from shape 1's box.
    boxes = [DEFAULT_RIG['mouths'][shape - 1 if shape <= 3 else 0][1:] for shape in shapes]
    rig['mouths'] = [[cell, *copy.deepcopy(box)] for cell, box in enumerate(boxes, 1)]
    if shapes != [1, 2, 3] or grid != [2, 2]:
        rig['grid'] = grid
        rig['shapes'] = shapes
    return rig


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('portrait', type=Path)
    parser.add_argument('expressions', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--shapes', default='1,2,3,4,5,6,7,8', help='mouth shape of each cell after cell 0, e.g. 1,2,3')
    parser.add_argument('--grid', help='columns x rows of the sheet, e.g. 3x3 (default: 2x2 for up to 3 shapes, else 3x3)')
    parser.add_argument('--rig', type=Path, help='use this rig.json instead of the default face boxes')
    args = parser.parse_args(argv)
    try:
        shapes = [int(n) for n in args.shapes.split(',')]
        grid = [int(n) for n in args.grid.lower().split('x')] if args.grid else ([2, 2] if len(shapes) <= 3 else [3, 3])
    except ValueError:
        parser.error('--shapes and --grid must be numbers, e.g. --shapes 1,2,3 --grid 2x2')
    if len(grid) != 2 or grid[0] * grid[1] < len(shapes) + 1:
        parser.error('The grid has too few cells: you need 1 blink cell plus one cell per mouth shape.')
    rig = json.loads(args.rig.read_text('utf-8')) if args.rig else build_rig(shapes, grid)
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as pack:
        pack.writestr('portrait.png', args.portrait.read_bytes())
        pack.writestr('expressions.png', args.expressions.read_bytes())
        pack.writestr('rig.json', json.dumps(rig))
    try:
        parse_import(archive.getvalue())
    except ValueError as exc:
        sys.exit('Not written. ' + str(exc))
    args.output.write_bytes(archive.getvalue())
    print('Wrote %s (%d bytes) with %d mouth shapes. Import it in NEXUS Settings, then Apply avatar.'
          % (args.output, archive.tell(), len(rig['mouths'])))


if __name__ == '__main__':
    main()
