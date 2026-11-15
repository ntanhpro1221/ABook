"""Pixel negative controls for the independent surface/shadow tracker."""
import sys
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from audit_surface_frames import measure, run


def scene(edge=None, shadow_edge=None):
    y, x = np.indices((480, 320))
    base = np.repeat((120 + (x % 90) + (y % 40))[:, :, None], 3, axis=2).astype(np.uint8)
    if edge is None:
        return base
    image = Image.fromarray((base * .6 + 2).astype(np.uint8)).convert('RGBA')
    shadow = Image.new('RGBA', (320, 480))
    draw = ImageDraw.Draw(shadow)
    draw.rounded_rectangle((0, shadow_edge, 320, 600), radius=20, fill=(0, 0, 0, 90))
    image = Image.alpha_composite(image, shadow.filter(ImageFilter.GaussianBlur(5)))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, edge, 320, 600), radius=20, fill=(80, 78, 75, 255))
    # Distinctive header, moving with the actual surface, independent of shadow.
    draw.rectangle((30, edge+25, 110, edge+30), fill='white')
    draw.rectangle((32, edge+34, 75, edge+42), fill='orange')
    return np.asarray(image.convert('RGB'))


def config():
    return dict(baseline=0, reference=1, edge_y=180, template=[25,200,150,40],
                search=[10,160,180,300], fit=[20,25,280,100], scan=[150,440],
                radius=20, frames=[1,5], min_travel=60, threshold=.8,
                max_shadow_distance=35, min_shadow_levels=3, max_corner_levels=16)


def test_shadow_tracks_a_moving_surface():
    edges = [180, 205, 245, 295, 360]
    verdict = measure([scene()] + [scene(e,e) for e in edges], config())
    assert verdict['status'] == 'PASS', verdict
    assert .8 < verdict['shadow_motion_gain'] < 1.2


def test_fixed_shadow_is_detected_while_the_surface_moves():
    verdict = measure([scene()] + [scene(e,180) for e in [180,205,245,295,360]], config())
    assert verdict['status'] == 'FAIL', verdict
    assert verdict['shadow_motion_gain'] < .2
    assert any('detached' in reason for reason in verdict['failures'])


def test_static_frames_are_not_animation_evidence():
    verdict = measure([scene()] + [scene(180,180)]*5, config())
    assert verdict['status'] == 'UNKNOWN'


def test_a_missing_surface_is_not_a_pass():
    cfg = config()
    frames = [scene(),scene(180,180)] + [scene()]*4
    assert measure(frames,cfg)['status'] != 'PASS'


def test_a_hard_rectangular_shadow_is_detected():
    edges=[180,205,245,295,360]
    seq=[scene()]
    for edge in edges:
        frame=scene(edge,edge).copy()
        # Plant a full-width, hard-cut band instead of a rounded soft shadow.
        frame[edge-24:edge,:]=20
        seq.append(frame)
    verdict=measure(seq,config())
    assert verdict['status']=='FAIL',verdict
    assert any('rounded contour' in reason for reason in verdict['failures'])


def test_endpoint_band_is_detected(tmp_path):
    seq=[scene()] + [scene(e,e) for e in [180,205,245,295,360]]
    for index,frame in enumerate(seq):
        Image.fromarray(frame).save(tmp_path/f'{index}.png')
    clean=seq[0].copy()
    clean[30:60]=20
    Image.fromarray(clean).save(tmp_path/'endpoint.png')
    cfg={**config(),'images':[f'{i}.png'for i in range(len(seq))],
         'endpoints':[{'frame':0,'image':'endpoint.png','rect':[0,0,320,120],'max_p99_levels':8}]}
    manifest=tmp_path/'manifest.json'
    manifest.write_text(json.dumps(cfg))
    output=tmp_path/'verdict.json'
    assert run(manifest,output)==1
    assert any('endpoint artifact' in reason for reason in json.loads(output.read_text())['failures'])
