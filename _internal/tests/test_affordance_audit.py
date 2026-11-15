from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from affordance_audit import audit, text_spacing
import numpy as np


def tree(*nodes):
    return {'nodes': [dict(id=i, parent=-1 if i == 0 else 0, bounds=[0, 0, 100, 48], **n) for i, n in enumerate(nodes)]}


def test_plain_clickable_body_fails():
    count, failures = audit(tree({'clickable': True}, {'text': 'Add voice', 'color': '#ece8e1'}))
    assert count == 1
    assert [f['rule'] for f in failures] == ['AFFORDANCE_CLICK']


def test_action_icon_or_accent_passes():
    for cue in ({'icon': True}, {'text': 'Add voice', 'color': '#f0b961'}):
        assert audit(tree({'clickable': True}, {'text': 'Add voice'}, cue))[1] == []


def test_static_accent_fails_and_disabled_action_cannot_hide_it():
    for parent in ({}, {'clickable': True, 'disabled': True}):
        assert audit(tree(parent, {'text': 'Information', 'color': '#8a5309'}))[1][0]['rule'] == 'AFFORDANCE_ACCENT'


def test_nested_button_cannot_lend_its_icon_to_a_plain_row():
    sample = tree({'clickable': True, 'text': 'Voice'}, {'clickable': True, 'text': 'Try'}, {'icon': True})
    sample['nodes'][2]['parent'] = 1
    failures = audit(sample)[1]
    assert len(failures) == 1
    assert failures[0]['id'] == 0


def test_qt_overlay_has_to_cover_every_line_of_accent_text():
    sample = tree({'text': 'Open book', 'color': '#8a5309', 'lines': [{'text': 'Open book', 'bounds': [0, 0, 90, 24]}]},
                  {'clickable': True, 'icon': True})
    assert audit(sample)[1] == []
    sample['nodes'][1]['bounds'] = [80, 0, 100, 48]
    assert audit(sample)[1][0]['rule'] == 'AFFORDANCE_ACCENT'


def test_modal_layer_blocks_background_but_does_not_waive_its_own_plain_action():
    sample = tree({'text': 'Background', 'clickable': True}, {'tag': 'sheet_layer'},
                  {'text': 'Plain sheet action', 'clickable': True})
    sample['nodes'][2]['parent'] = 1
    assert [f['text'] for f in audit(sample)[1]] == ['Plain sheet action']


def test_full_window_scrim_blocks_earlier_actions():
    sample = tree({'text': 'Background', 'clickable': True}, {'clickable': True, 'description': 'Dismiss'},
                  {'text': 'Plain sheet action', 'clickable': True})
    sample.update(width=100, height=48)
    sample['nodes'][1]['parent'] = -1
    assert [f['text'] for f in audit(sample)[1]] == ['Plain sheet action']


def test_neutral_checkbox_requires_a_real_painted_outline():
    sample = tree({'clickable': True, 'description': 'Choose', 'role': 'checkbox'})
    sample.update(width=100, height=48)
    pixels = np.full((48,100,3),245,dtype=np.uint8)
    assert audit(sample,pixels)[1][0]['rule'] == 'AFFORDANCE_CLICK'
    pixels[2:4,2:98] = 100; pixels[44:46,2:98] = 100
    pixels[2:46,2:4] = 100; pixels[2:46,96:98] = 100
    assert audit(sample,pixels)[1] == []
    # Rounded corners leave only the middle 60 percent of each vertical edge.
    pixels[0:10,2:4] = 245; pixels[38:48,2:4] = 245
    pixels[0:10,96:98] = 245; pixels[38:48,96:98] = 245
    assert audit(sample,pixels)[1] == []


def test_interpolated_accent_is_still_an_action_cue():
    assert audit(tree({'clickable': True}, {'text': 'Listen', 'color': '#623f16'}))[1] == []


def test_qt_oversized_frame_is_clipped_without_horizontal_scaling():
    sample = tree({'clickable': True, 'description': 'Open', 'role': 'button'})
    sample.update(platform='qt', width=200, height=48, pixel_ratio=1)
    sample['nodes'][0]['bounds'] = [10,0,90,48]
    pixels = np.full((48,100,3),245,dtype=np.uint8)
    pixels[46:48,10:90] = [233,169,69]
    assert audit(sample,pixels)[1] == []


def text_node(id, text, bounds, parent=-1):
    return dict(id=id, parent=parent, text=text, bounds=bounds, lines=[dict(text=text, bounds=bounds)])


def test_text_gap_detects_touching_overlap_and_below_eight_dp():
    for gap in (-2, 0, 7):
        nodes = [text_node(0, 'Chosen', [0, 0, 50, 20]), text_node(1, 'Try', [50+gap, 0, 90+gap, 20])]
        assert text_spacing(nodes)[0]['gap_dp'] == gap


def test_text_gap_accepts_eight_dp_and_different_rows():
    a = text_node(0, 'Name', [0, 0, 50, 20])
    assert text_spacing([a, text_node(1, 'Try', [58, 0, 90, 20])]) == []
    assert text_spacing([a, text_node(1, 'Caption', [0, 24, 50, 44])]) == []


def test_text_gap_uses_lines_not_fill_width_and_ignores_semantic_copies():
    a = text_node(0, 'Name', [0, 0, 50, 20]); a['bounds'] = [0, 0, 200, 48]
    b = text_node(1, 'Try', [62, 0, 100, 20])
    assert text_spacing([a, b]) == []
    assert text_spacing([a, text_node(1, 'Name', [0, 0, 50, 20], parent=0)]) == []
    b['visible'] = [62, 30, 100, 40]
    assert text_spacing([a, b]) == []


def test_text_gap_respects_exposed_modal_and_qt_logical_scale():
    nodes = [text_node(0, 'Background', [0, 0, 50, 20]), text_node(1, 'Try', [50, 0, 100, 20])]
    assert text_spacing(nodes, exposed=lambda n: n['id'] == 1) == []
    sample = dict(platform='qt', pixel_ratio=2, nodes=nodes, width=100, height=48)
    assert audit(sample)[1][0]['rule'] == 'TEXT_GAP'


def test_text_gap_ignores_hidden_ancestors_and_overlaid_surfaces():
    sample = tree({}, {}, {})
    sample['nodes'][1].update(bounds=[0, 0, 0, 0])
    sample['nodes'] += [text_node(3, 'Hidden', [0, 0, 50, 20], parent=1), text_node(4, 'Visible', [50, 0, 100, 20], parent=2)]
    assert not [f for f in audit(sample)[1] if f['rule'] == 'TEXT_GAP']
    sample['nodes'][1]['bounds'] = [0, 0, 100, 200]
    sample['nodes'][2]['bounds'] = [0, 0, 100, 200]
    assert text_spacing(sample['nodes']) == []


def test_text_gap_checks_painted_ink_not_padded_boxes():
    sample = dict(width=100, height=48, nodes=[text_node(0, 'Name', [0, 0, 60, 20]), text_node(1, 'Try', [60, 0, 100, 20])])
    for n in sample['nodes']: n['color'] = '#000000'
    pixels = np.full((48, 100, 3), 255, dtype=np.uint8)
    pixels[5:15, 5:50] = 0; pixels[5:15, 65:90] = 0
    assert audit(sample, pixels)[1] == []
    pixels[5:15, 55:60] = 0
    assert audit(sample, pixels)[1][0]['gap_dp'] == 5
