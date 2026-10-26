pragma Singleton
import QtQuick
QtObject {
    property var requests: []
    property var responses: ({})
    property var pending: []
    property string thirdParty: "Qt Quick"
    property bool delayed: false
    function reset() { requests = []; responses = {}; pending = []; delayed = false }
    function request(method, path, body, done) {
        requests = requests.concat([{method: method, path: path, body: body}])
        const response = responses[path] || {status: 200, data: path === "/api/preferences" ? (method === "PUT" ? body : {theme: "system"}) : path === "/api/app" ? {version: "fixture"} : /voices$|online$/.test(path) ? [] : {}}
        if (delayed) pending = pending.concat([function() { done(response.status, response.data) }])
        else done(response.status, response.data)
        return requests.length
    }
    function finish() { const jobs = pending; pending = []; for (const job of jobs) job() }
    function cancel(id) { pending = [] }
    function localPath(url) { return String(url).replace(/^file:\/\//, "") }
    function mediaUrl(path) { return path }
    function refreshLibrary() {}
    function preview(path) {}
    function stopPreview() {}
    function imageData(file) { return "data:image/png;base64,fixture" }
}
