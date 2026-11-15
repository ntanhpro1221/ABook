"""Identity keys cover their retained value, never an unrelated mutable input."""
from scripts import ui_instant


def covered(key, condition):
    source = f'SwapContent(state, contentKey = {{ {key} }}, inPlace = true) {{ value -> if ({condition}) Icon() }}'
    return ui_instant._kt_inside_motion(ui_instant.mask(source), source.index('if ('), condition, source)


def test_identity_key_covers_nullable_value_and_tuple_fields():
    assert covered('it', 'value != null')
    assert covered('item -> item', 'value.first && value.second')


def test_identity_key_does_not_cover_another_input():
    assert not covered('it', 'value && outside')
    assert not covered('item -> item', 'outside')


def test_partial_key_cannot_hide_a_change_in_the_retained_value():
    assert not covered('item -> item.first', 'value.second')
    assert covered('item -> item.first', 'value.first')
