// A requested item larger than the QtTest window is silently cropped by grabImage.
// Size the fixture window before rendering and assert the pixels actually captured.
function resize(test, host, window, width, height) {
    host.width = width
    host.height = height
    window.width = width
    window.height = height
    test.tryCompare(window, "width", width)
    test.tryCompare(window, "height", height)
}

function grab(test, target) {
    const image = test.grabImage(target)
    test.compare(image.width, Math.ceil(target.width), "capture width must match its viewport")
    test.compare(image.height, Math.ceil(target.height), "capture height must match its viewport")
    return image
}
