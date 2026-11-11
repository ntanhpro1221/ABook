package vn.abook.player.readaloud

import org.json.JSONObject
import vn.abook.player.vieneu.PhonemePolicy

/**
 * A book's readings ([Readings]: {shown word: what to say}) together with what Studio's second tier decided for the book - the `sharedWords`
 * entry of book.json (readaloud/shared_rulings.py). It is a plain readings map everywhere (clip key, text layer); the VieNeu voice and its
 * clip key also read [rulings], the answers for words that are both Vietnamese and English. A phone has no model: it only reads the answers.
 */
class BookReadings(private val readings: Map<String, String>, val rulings: PhonemePolicy.Rulings?) : Map<String, String> by readings {
    override fun equals(other: Any?) = readings == other
    override fun hashCode() = readings.hashCode()
    override fun toString() = readings.toString()

    companion object {
        /**
         * [own]: the listener's readings; [shared]: `sharedWords` of the book, or null. The name readings Studio derived from each name's origin
         * ("Chiaki" read the Japanese way in a book of no settled origin) stand under the listener's own. No usable entry: [own] itself.
         */
        fun of(own: Map<String, String>, shared: JSONObject?): Map<String, String> {
            if (shared == null || shared.optInt("version") != 2) return own
            val names = shared.optJSONObject("readings")
            val origin = HashMap<String, String>()
            if (names != null) for (key in names.keys()) names.optString(key).takeIf { it.isNotEmpty() && Readings.isKey(key) }?.let { origin[key] = it }
            val rulings = PhonemePolicy.Rulings.of(shared)
            return if (origin.isEmpty() && rulings == null) own else BookReadings(origin + own, rulings)
        }

        /**
         * [proven]: the names the book proves by itself (JapanesePolicy.bookNameReadings), standing under [own] (what [of] gave). A Studio
         * book's rulings survive the layering: a plain `proven + own` is a bare map and would drop them.
         */
        fun over(proven: Map<String, String>, own: Map<String, String>): Map<String, String> =
            if (proven.isEmpty()) own else if (own is BookReadings) BookReadings(proven + own, own.rulings) else proven + own
    }
}
