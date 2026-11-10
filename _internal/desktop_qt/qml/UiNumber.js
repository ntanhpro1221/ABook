.pragma library
.import "UiStrings.js" as S

// The single decimal formatter for visible Vietnamese numbers.
function decimal(value, digits, fixed) {
    var text = (value === 0 ? 0 : value).toFixed(digits === undefined ? 2 : digits)
    if (Number(text) === 0) text = (0).toFixed(digits === undefined ? 2 : digits)
    if (!fixed && text.indexOf(".") >= 0) text = text.replace(/0+$/, "").replace(/\.$/, "")
    return text.replace(".", ",")
}

function balance(percent) {
    return percent === 0 ? S.s_value_middle : percent < 0 ? S.s_value_left(decimal(-percent, 0)) : S.s_value_right(decimal(percent, 0))
}
