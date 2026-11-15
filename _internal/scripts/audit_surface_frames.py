"""Measure a floating surface and its shadow independently in decoded UI frames.

Manifest: video, baseline, reference, edge_y, template [x,y,w,h], search
[x,y,w,h], fit [x,y,w,h], scan [top,bottom], radius, frames [first,last].
Coordinates and thresholds are source-video pixels and 8-bit luminance levels.
Uses audit_navigation_frames' decoder/template tracker, including variable-rate
screenrecord frames. Reports UNKNOWN for missing evidence, never an empty PASS.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import uniform_filter

from audit_navigation_frames import crop, frames, track


def endpoint_measurement(recorded, reference, rect):
    """Compare boundary bands without classifying H.264 text ringing as a ghost.

    Remove the median RGB conversion bias, then average 8x8 pixel neighborhoods.
    Keep the raw p99 in the evidence; thresholds apply to spatial band contrast.
    """
    delta=crop(recorded,rect).astype(float)-crop(reference,rect).astype(float)
    raw=float(np.quantile(abs(delta).mean(2),.99))
    bias=np.median(delta,axis=(0,1))
    delta-=bias
    band=uniform_filter(delta,size=(8,8,1))[::8,::8]
    return {'p99_levels':round(float(np.quantile(abs(band).mean(2),.99)),3),
            'raw_p99_levels':round(raw,3),'rgb_bias':[round(float(v),3) for v in bias]}


def backdrop(base, current, rect, scrim_color=None):
    """Robustly estimate the scrim from an independent, stationary screen ROI."""
    a, b = crop(base, rect).mean(2).ravel(), crop(current, rect).mean(2).ravel()
    keep = (a > 6) & (a < 254)
    if np.std(a) < 3 and scrim_color is not None:
        color = float(np.mean(scrim_color))
        if abs(float(np.mean(a))-color) < 3:
            raise ValueError('flat background cannot separate the scrim from the page')
        gain = float((np.mean(b)-color)/(np.mean(a)-color))
        offset = color*(1-gain)
        return base.mean(2)*gain+offset-current.mean(2),gain,offset
    for _ in range(3):
        if keep.sum() < 40 or np.std(a[keep]) < 3:
            raise ValueError("scrim fit ROI needs varied, stationary pixels")
        gain, offset = np.polyfit(a[keep], b[keep], 1)
        error = abs(b - (gain * a + offset))
        keep &= error < max(2., float(np.quantile(error[keep], .85)))
    return base.mean(2) * gain + offset - current.mean(2), float(gain), float(offset)


def measure(seq, spec, baseline=None):
    base = np.asarray(baseline,dtype=float) if baseline is not None else (
        np.asarray(Image.open(spec['baseline_image']).convert('RGB')).astype(float)
        if 'baseline_image' in spec else seq[spec['baseline']].astype(float))
    reference = seq[spec['reference']]
    template = crop(reference, spec['template'])
    tracking = {key: spec[key] for key in ['search', 'analysis_width', 'widths'] if key in spec}
    reference_match = track(reference, template, tracking)
    delta = reference_match['rect'][1] - spec['edge_y']
    first, last = spec['frames']
    radius = spec['radius']
    distance_limit = spec.get('max_shadow_distance', max(32, radius * 1.5))
    strength_limit = spec.get('min_shadow_levels', 2.)
    rows = []
    h, w = base.shape[:2]
    for index in range(first, last + 1):
        current = seq[index]
        found = track(current, template, tracking)
        row = {'frame': index, 'match': found['score'], 'matched': found['score'] >= spec.get('threshold', .8)}
        if not row['matched']:
            rows.append(row)
            continue
        scale = found['rect'][2] / reference_match['rect'][2]
        edge = found['rect'][1] - delta * scale
        surface_left = found['rect'][0] - (reference_match['rect'][0] - spec.get('surface_x', 0)) * scale
        surface_width = spec.get('surface_width', w) * scale
        if 'panel_color' in spec:
            # Correlation of a short title can also match its opener behind the
            # dialog. Require the independently measured opaque surface fill.
            color = np.array(spec['panel_color'])
            coverage = np.mean(np.max(abs(current.astype(float)-color),axis=2) < spec.get('panel_tolerance',5),axis=1)
            candidates = np.where(np.convolve((coverage>.8).astype(float),np.ones(10),mode='valid')>=9)[0]
            candidates = candidates[(candidates >= spec.get('panel_min_y',spec['edge_y']-20)) & (candidates < h-50)]
            if not len(candidates) or abs(float(candidates[0])-edge)>spec.get('fill_match_distance',80):
                row.update(matched=False,reason='template not supported by the surface fill')
                rows.append(row)
                continue
            edge = float(candidates[0])
        residual, gain, offset = backdrop(base, current.astype(float), spec['fit'], spec.get('scrim_color'))
        # Quantization and an imperfect scrim fit can leave a uniform residual.
        # Measure shadow contrast against an external local background band,
        # retaining any separate shadow farther up the stationary page.
        far_top, far_bottom = max(0, round(edge-radius*3)), max(1, round(edge-radius*2))
        local_offset = float(np.median(residual[far_top:far_bottom]))
        residual -= local_offset
        surface_opacity = 1.
        if 'surface_color' in spec:
            top=max(0,min(h-1,round(edge+30)))
            bottom=max(top+1,min(h,round(edge+100)))
            x0=max(0,round(surface_left+radius));x1=min(w,round(surface_left+surface_width-radius))
            seen=current[top:bottom,x0:x1].mean(2)
            diff=residual[top:bottom,x0:x1]
            background=seen+diff
            denominator=float(np.mean(spec['surface_color']))-background
            valid=abs(denominator)>4
            if not valid.any():
                row.update(matched=False,reason='no measurable surface contrast')
                rows.append(row);continue
            surface_opacity=float(np.clip(np.median((-diff[valid])/denominator[valid]),0,1))
            if surface_opacity < .2:
                row.update(matched=False,reason='surface is below measurable opacity')
                rows.append(row);continue
        left, right = spec.get('profile_x', [round(w * .12), round(w * .88)])
        strips = spec.get('profile_ranges', [[left,right]])
        profile = np.quantile(np.concatenate([residual[:, a:b] for a,b in strips],axis=1),spec.get('profile_quantile',.5),axis=1)
        profile = np.convolve(profile, np.ones(8) / 8, mode='same')
        lo, hi = spec['scan']
        hi = min(hi, int(edge) - 4, h - 8)
        if hi <= lo:
            row.update(matched=False, reason='no visible external edge band')
            rows.append(row)
            continue
        peak = int(np.argmax(profile[lo:hi]) + lo)
        strength = float(profile[peak])
        separation = float(edge - peak)
        # A weak single H.264 block around background text is not a shadow
        # band. Require spatial support for weak, detached candidates; retain
        # strong one-frame artifacts and all measurable near-edge shadows.
        band_limit=max(strength_limit,strength*.5)
        band_start=band_end=peak
        while band_start>lo and profile[band_start-1]>band_limit:band_start-=1
        while band_end+1<hi and profile[band_end+1]>band_limit:band_end+=1
        band_width=band_end-band_start+1
        measurable=separation<=distance_limit or band_width>=spec.get('min_detached_band_px',12) or strength>=spec.get('strong_artifact_levels',6.)
        edge_profile = [float(profile[max(0, min(h-1, round(edge-d)))]) for d in [8, 12, 16, 24, 32, 48]]
        cut_y = round(edge - max(6, radius * .25))
        cut_step = 0.
        if 2 <= cut_y < h-2:
            line = np.median(residual[cut_y-2:cut_y+3], axis=0)
            # The viewport may cut a full-width sheet. Interior panel boundaries
            # must retain the smooth external shadow on both sides.
            steps = []
            for boundary in [surface_left, surface_left+surface_width]:
                bx = round(boundary)
                if 5 < bx < w-5:
                    steps.extend(abs(np.diff(line[max(0,bx-radius):min(w,bx+radius)])))
            cut_step = float(max(steps, default=0.))
        # Compare equal signed distances from the rounded top contour. Text and
        # compression outliers are suppressed with medians over each sample.
        arc = []
        edge_int = round(edge)
        frame_radius = radius * scale
        for fraction in [.15, .3, .5, .7, .85, 1.]:
            x = max(2, round(frame_radius * fraction))
            arc_y = edge_int + frame_radius - np.sqrt(max(0, frame_radius ** 2 - (x - frame_radius) ** 2))
            y = round(arc_y - max(6, radius * .25))
            if 2 <= y < h - 2:
                for px in [round(surface_left+x), round(surface_left+surface_width-1-x)]:
                    if 2 <= px < w-2:
                        arc.append(float(np.median(residual[y-2:y+3, px-2:px+3])))
        # A stationary rectangular band far above a moving surface is a fault
        # regardless of how unobtrusive it is in the final resting frame.
        detached = measurable and strength > strength_limit and separation > distance_limit
        center_y=round(edge-max(6,radius*.25))
        center_level=float(np.median(residual[max(0,center_y-2):min(h,center_y+3),left:right]))
        arc_shape_error=float(np.quantile(abs(np.array(arc)-center_level),.8)) if arc and surface_opacity>=.9 else None
        row.update(edge_y=round(edge, 2), surface_scale=round(scale, 4), surface_opacity=round(surface_opacity,3), shadow_y=peak, shadow_levels=round(strength, 3),
                   shadow_offset_px=round(separation, 2), detached=detached,
                   shadow_measurable=measurable, shadow_band_width_px=band_width,
                   scrim_gain=round(gain, 5), scrim_offset=round(offset, 3),
                   corner_levels=[round(v, 2) for v in arc],
                   corner_shape_error_levels=None if arc_shape_error is None else round(arc_shape_error,3),
                   edge_profile=[round(v, 3) for v in edge_profile], cut_step_levels=round(cut_step, 3))
        rows.append(row)
    good = [r for r in rows if r['matched']]
    resting = next((r for r in good if r['frame'] == spec['reference']), None)
    if resting is None:
        return {'status':'UNKNOWN','failures':['reference frame is not matched'], 'matched':len(good), 'rows':rows}
    for row in good:
        values = np.array(row['corner_levels'])
        comparison = np.array(resting['corner_levels'])
        row['corner_error_levels'] = round(float(np.quantile(abs(values - comparison), .8)), 3) if row['surface_opacity']>=.9 and len(values) == len(comparison) and len(values) else None
        a, b = np.array(row['edge_profile']), np.array(resting['edge_profile'])
        peak_a, peak_b = float(max(a)), float(max(b))
        row['profile_error_levels'] = round(float(np.quantile(abs(a * peak_b / peak_a - b), .85)),3) if min(peak_a,peak_b)>strength_limit else None
    strong = [r for r in good if r['shadow_measurable'] and r['shadow_levels'] > strength_limit]
    travel = float(np.ptp([r['edge_y'] for r in good])) if good else 0.
    offset_span = float(np.ptp([r['shadow_offset_px'] for r in strong])) if strong else None
    failures = [f"detached shadow in frame {r['frame']}: offset {r['shadow_offset_px']} px" for r in good if r['detached']]
    if spec.get('check_corners', True):
        bad_corners = [r for r in good if r['corner_error_levels'] is not None
                       and r['corner_error_levels'] > spec.get('max_corner_levels', 6.)]
        failures += [f"corner shadow mismatch in frame {r['frame']}: {r['corner_error_levels']} levels" for r in bad_corners]
    failures += [f"shadow profile changed in frame {r['frame']}: {r['profile_error_levels']} levels"
                 for r in good if r['profile_error_levels'] is not None and r['profile_error_levels'] > spec.get('max_profile_levels',6.)]
    failures += [f"straight shadow cut in frame {r['frame']}: {r['cut_step_levels']} levels"
                 for r in good if r['cut_step_levels'] > spec.get('max_cut_step_levels',8.)]
    failures += [f"shadow does not follow the rounded contour in frame {r['frame']}: {r['corner_shape_error_levels']} levels"
                 for r in good if r['corner_shape_error_levels'] is not None and r['corner_shape_error_levels'] > spec.get('max_corner_shape_levels',8.)]
    if len(strong) >= 3 and offset_span > spec.get('max_offset_span',8.):
        failures.append(f"shadow offset changed by {offset_span:.3f} px")
    # Regression is only meaningful with measured shadow contrast and travel.
    gain = None
    if len(strong) >= 3 and np.ptp([r['edge_y'] for r in strong]) > spec.get('regression_travel', 30):
        gain = float(np.polyfit([r['edge_y'] for r in strong], [r['shadow_y'] for r in strong], 1)[0])
        if gain < .5 and (spec.get('strict_motion_gain') or any(r['detached'] for r in strong)):
            failures.append(f"shadow motion gain {gain:.3f}; expected approximately 1")
    unknown = len(good) < spec.get('min_matched', 4) or travel < spec.get('min_travel', 30)
    return {'status': 'FAIL' if failures else 'UNKNOWN' if unknown else 'PASS',
            'failures': failures, 'matched': len(good), 'requested': len(rows),
            'surface_travel_px': round(travel, 2),
            'shadow_motion_gain': None if gain is None else round(gain, 4),
            'max_shadow_distance_px': distance_limit, 'min_shadow_levels': strength_limit,
            'max_measured_offset_px': max((r['shadow_offset_px'] for r in strong), default=None),
            'shadow_offset_span_px': None if offset_span is None else round(offset_span,3),
            'max_corner_error_levels': max((r['corner_error_levels'] for r in good if r['corner_error_levels'] is not None), default=None),
            'max_profile_error_levels': max((r['profile_error_levels'] for r in good if r['profile_error_levels'] is not None), default=None),
            'max_cut_step_levels': max((r['cut_step_levels'] for r in good), default=None),
            'max_corner_shape_error_levels': max((r['corner_shape_error_levels'] for r in good if r['corner_shape_error_levels'] is not None),default=None),
            'rows': rows}


def run(manifest, output):
    spec = json.loads(manifest.read_text(encoding='utf-8-sig'))
    if 'images' in spec:
        seq = [np.asarray(Image.open(manifest.parent / name).convert('RGB')) for name in spec['images']]
        meta = {'size': [seq[0].shape[1], seq[0].shape[0]]}
        video = 'consecutive PNG captures'
    else:
        video = Path(spec['video'])
        if not video.is_absolute():
            video = manifest.parent / video
        stream = frames(video)
        meta = next(stream)
        seq = list(stream)
    baseline=None
    if 'baseline_image' in spec:
        baseline=np.asarray(Image.open(manifest.parent/spec['baseline_image']).convert('RGB'))
    if spec.get('axis') == 'x':
        seq = [np.swapaxes(frame, 0, 1).copy() for frame in seq]
        if baseline is not None:baseline=np.swapaxes(baseline,0,1).copy()
    result = measure(seq, spec, baseline)
    endpoint_results=[]
    for check in spec.get('endpoints',[]):
        recorded=seq[check['frame']]
        ref=np.asarray(Image.open(manifest.parent/check['image']).convert('RGB'))
        if spec.get('axis')=='x':ref=np.swapaxes(ref,0,1)
        measured=endpoint_measurement(recorded,ref,check['rect'])
        percentile=measured['p99_levels']
        passed=percentile<=check.get('max_p99_levels',8.)
        endpoint_results.append({'frame':check['frame'],**measured,'pass':passed})
        if not passed:
            result['status']='FAIL';result['failures'].append(f"endpoint artifact in frame {check['frame']}: {percentile:.3f} levels")
    result['endpoints']=endpoint_results
    result.update(video=str(video), decoded_frames=len(seq), size=meta['size'])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    chosen = [r for r in result['rows'] if r.get('matched')]
    if chosen:
        chosen = chosen[::max(1, len(chosen)//6)][:6]
        tile_w = 432
        canvas = Image.new('RGB', (tile_w * len(chosen), 330), '#252525')
        pen = ImageDraw.Draw(canvas)
        for at, row in enumerate(chosen):
            y = round(min(row['edge_y'], row['shadow_y']) - 30)
            image = Image.fromarray(seq[row['frame']]).crop((0, y, seq[0].shape[1], y+260))
            image = image.point(lambda v: round(255 * (v/255) ** (1/2.2)))
            image.thumbnail((tile_w, 280))
            canvas.paste(image, (tile_w * at, 40))
            pen.text((tile_w*at+5,5), f"frame {row['frame']} edge {row['edge_y']:.0f} shadow {row['shadow_y']}", fill='white')
        canvas.save(output.with_suffix('.png'))
    print(json.dumps({k:v for k,v in result.items() if k != 'rows'}, indent=2))
    return 0 if result['status']=='PASS' else 1 if result['status']=='FAIL' else 2


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args=parser.parse_args()
    raise SystemExit(run(args.manifest,args.output))
