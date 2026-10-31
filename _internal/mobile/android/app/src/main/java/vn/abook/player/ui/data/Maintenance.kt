package vn.abook.player.ui.data

import org.json.JSONObject

data class OldSave(val name: String, val size: Long, val modified: Long) {
    val title: String get() = name.replace(Regex("\\.abook(proj)?$"), "")
        .replace(Regex(" \\d{8}-\\d{6}(-\\d+)?$"), "").trim().ifBlank { name }
}

data class AppRelease(val version: String, val page: String, val apk: String?) {
    companion object {
        fun parse(json: JSONObject): AppRelease? {
            val tag = json.opt("tag_name") as? String ?: return null
            val page = json.opt("html_url") as? String ?: return null
            val assets = json.optJSONArray("assets")
            val apk = (0 until (assets?.length() ?: 0)).mapNotNull { assets?.optJSONObject(it) }
                .firstOrNull { it.optString("name").endsWith(".apk", ignoreCase = true) }?.opt("browser_download_url") as? String
            return AppRelease(tag.removePrefix("v").removePrefix("V"), page, apk)
        }

        fun newer(a: String, b: String): Boolean {
            fun parts(s: String) = s.removePrefix("v").removePrefix("V").split('.').map { Regex("^\\d+").find(it)?.value?.toLongOrNull() ?: 0 }
            val left = parts(a); val right = parts(b)
            for (i in 0 until maxOf(left.size, right.size)) {
                val x = left.getOrElse(i) { 0 }; val y = right.getOrElse(i) { 0 }
                if (x != y) return x > y
            }
            return false
        }
    }
}
