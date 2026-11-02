# mkcrate.py: copies the files listed in crate.txt (one absolute path per line: the audition page's export) into a new
# crate folder for Recycler's Deck mode, numbered in list order: 01_<name>, 02_<name> ... A missing file is reported and
# its number skipped. A non-empty destination is refused so an old crate never mixes into a new order. Originals stay put.
# Usage: py -3 tools/mkcrate.py <crate.txt> <crate folder>    |    py -3 tools/mkcrate.py --selftest
# Author: Ari Klopfer / A_Development. MIT
import os, shutil, sys, tempfile


def build(lines, dest):
    """returns (copied paths, missing paths); raises FileExistsError when dest has files"""
    if os.path.isdir(dest) and os.listdir(dest):
        raise FileExistsError(f'{dest} is not empty: pick a new crate folder')
    os.makedirs(dest, exist_ok=True)
    paths = [l.strip().strip('"') for l in lines if l.strip()]
    width = max(2, len(str(len(paths))))
    copied, missing = [], []
    for i, p in enumerate(paths, 1):
        if not os.path.isfile(p):
            missing.append(p)
            continue
        target = os.path.join(dest, f'{i:0{width}d}_{os.path.basename(p)}')
        shutil.copy2(p, target)
        copied.append(target)
    return copied, missing


def selftest():
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, 'src'); os.makedirs(src)
        a, b = os.path.join(src, 'zeta.wav'), os.path.join(src, 'alpha.wav')
        for p in (a, b):
            open(p, 'wb').write(b'RIFF')
        crate = os.path.join(tmp, 'crate')
        copied, missing = build([a + '\n', '\n', os.path.join(src, 'gone.wav'), f'"{b}"'], crate)
        names = sorted(os.listdir(crate))
        assert names == ['01_zeta.wav', '03_alpha.wav'], names          # list order wins over the source names; gaps kept
        assert missing == [os.path.join(src, 'gone.wav')], missing
        assert open(a, 'rb').read() == b'RIFF'                         # the original is untouched
        try:
            build([a], crate)
            raise AssertionError('a non-empty crate folder must be refused')
        except FileExistsError:
            pass
    print('mkcrate selftest: ok')


if __name__ == '__main__':
    if sys.argv[1:] == ['--selftest']:
        selftest()
        sys.exit(0)
    if len(sys.argv) != 3:
        sys.exit(__doc__ or 'usage: mkcrate.py <crate.txt> <crate folder>')
    with open(sys.argv[1], encoding='utf-8-sig') as f:
        copied, missing = build(f.readlines(), sys.argv[2])
    for p in missing:
        print('missing, skipped:', p)
    print(f'{len(copied)} files -> {sys.argv[2]}')
