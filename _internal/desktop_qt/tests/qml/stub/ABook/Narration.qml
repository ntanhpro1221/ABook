pragma Singleton
import QtQuick
QtObject {
    signal consentRequested(var voice)
    function configure(voices, allowed) {}
    function authorize(provider) {}
    function cancelConsent() {}
}
