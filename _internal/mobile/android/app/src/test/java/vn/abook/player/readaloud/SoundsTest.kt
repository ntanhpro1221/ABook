package vn.abook.player.readaloud

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import vn.abook.player.vieneu.VieneuUnits

/**
 * Viết tắt TOÀN HOA (Abbreviations.kt), thán từ kéo dài (Shouts.kt) và hậu tố gọi (Names.honorificReading) trong "Nghe ngay": cùng các ca với
 * tests/test_readaloud_sounds.py; các khúc đọc cả đoạn nằm trong fixture dùng chung (VieneuParityTest). Chữ hiện và số chữ không đổi.
 */
class SoundsTest {
    private fun said(text: String, origin: String? = null): List<String> {
        val toks = VieneuUnits.tokens(text)
        val out = VieneuUnits.spokenTokens(toks, origin)
        assertEquals(toks.size, out.size)
        return out
    }

    @Test
    fun anAbbreviationIsReadByItsLetterNames() {
        val cases = listOf("HP" to "hát pê", "MP" to "em pê", "NPC" to "en pê xê", "EXP" to "e ích pê", "SSR" to "ét ét e-rờ", "GOTY" to "giê ô tê i-dài", "QQ" to "quy quy",
            "XL" to "ích e-lờ", "BBQ" to "bê bê quy", "ATSM" to "a tê ét em", "WZ" to "vê-kép dét", "JK" to "gi ca", "AI" to "a i", "ABC" to "a bê xê", "USA" to "u ét a",
            "RPG" to "e-rờ pê giê", "VIT" to "vê i tê")
        for ((token, reading) in cases) {
            assertEquals(token, listOf("Rồi", "$reading."), said("Rồi $token."))
            assertEquals(token, listOf("Rồi", "$reading."), said("Rồi $token.", "ja"))
        }
    }

    @Test
    fun fourAbbreviationsAreReadAsWordsAndCapitalWordsAreLowered() {
        for ((token, reading) in listOf("VIP" to "víp", "ID" to "ai-đi", "OK" to "ô kê", "TV" to "ti vi", "LINE" to "line", "MAX" to "max", "YES" to "yes", "TIP" to "tip",
            "BAKA" to "baka", "NO" to "no", "WARNING" to "warning")) assertEquals(token, listOf("Rồi", "$reading."), said("Rồi $token."))
    }

    @Test
    fun otherTokensAreLeftAlone() {
        for (token in listOf("Hp", "hp", "NPCs", "A", "H", "10KG", "A12-B", "TP.HCM", "PGS.TS", "KIRITO", "X-RAY", "SS2", "ĐH", "CÁC")) assertEquals(token, listOf("Rồi", token, "đến."), said("Rồi $token đến."))
        assertEquals(listOf("“hát pê,”", "(em pê)", "en pê xê!", "3MP", "level 5", "5HP"), said("“HP,” (MP) NPC! 3MP LV5 5HP"))
        assertEquals(listOf("CÚT", "ĐI,", "AI", "ĐÓ"), said("CÚT ĐI, AI ĐÓ"))
        assertEquals(listOf("o-ni-chan", "LO", "LẮNG", "CHO", "CON", "KÌA"), said("ONII-CHAN LO LẮNG CHO CON KÌA"))
        assertEquals(listOf("hát pê", "em pê", "ét pê"), said("HP MP SP"))
        assertEquals(listOf("Chương", "bốn,", "hát pê."), said("Chương IV, HP."))
        assertEquals("i i i i", Abbreviations.spelled("IIII"))
        assertEquals("ích ích ích", Abbreviations.spelled("XXX"))
        assertEquals(listOf("Chương", "ba,", "ba mươi."), said("Chương III, XXX."))
        assertEquals(listOf("Ôi,", "ích ích ích!", "i i i"), said("Ôi, XXX! III"))
    }

    @Test
    fun aFixedLatinInterjectionIsReadAsAVietnameseSound() {
        for ((token, reading) in listOf("Umm" to "ừm", "Ugh" to "ức", "Boom" to "bùm", "Oh" to "ô", "Hmm" to "hừm", "UGH" to "ức", "oh" to "ô"))
            assertEquals(token, listOf("Rồi", "$reading,", "đến."), said("Rồi $token, đến."))
    }

    @Test
    fun aStretchedSoundIsTheSoundThenAnEllipsisThenTheVowel() {
        val cases = listOf(
            "Aaaa" to "a… a", "Haaa" to "ha… a", "Uuu" to "u… u", "Viiiiii" to "vi… i", "Taaa" to "ta… a", "oaaaa" to "oa… a", "Eeee" to "e… e",
            "rồiiiii" to "rồi… ì", "tớơơơơ" to "tớ… ớ", "chứứứứ" to "chứ… ứ", "quẹooo" to "quẹo… ọ", "đâuuuu" to "đâu… u", "màaaa" to "mà… à", "nhaaa" to "nha… a", "tooo" to "to… o",
            "Khônggg" to "không…", "Emmmm" to "em…", "Hầyyy" to "hầy…", "rấtttt" to "rất…", "hiếppppp" to "hiếp…", "Oáppp" to "oáp…", "Haizzz" to "hai…",
            "Hmmm" to "hừm…", "Ummm" to "ừm…", "Shhhh" to "suỵt…", "Ahhhh" to "a…", "Aaah" to "a… a", "Oooh" to "ô… ô", "Ughhh" to "ức…",
            "Kyaaa" to "ki-a… a", "Uwaaa" to "u-oa… a", "Yaaa" to "gia… a",
            "AAAA" to "a… a", "EMMMMMMM" to "em…", "HMMM" to "hừm…", "Aー" to "a… a", "Haー" to "ha… a", "Aーー" to "a… a",
        )
        for ((token, reading) in cases) {
            val want = listOf("Rồi", "$reading,", "đến.")
            assertEquals(token, want, said("Rồi $token, đến."))
            for (origin in listOf("ja", "ko")) assertEquals(token, want, said("Rồi $token, đến.", origin))
        }
    }

    @Test
    fun whatCannotBeTracedToASoundIsLeftAlone() {
        for (core in listOf("Weisss", "wwww", "zzz", "kkkkk", "Onii-channnn", "XXX", "III", "Hmm,Aa", "Aa", "Haiz")) assertNull(core, Shouts.stretchReading(core))
    }

    @Test
    fun stretchesInQuotesGluedToTheNextWordAndRanks() {
        assertEquals(listOf("“a… a…", "u… u!”", "‘nha… a”", "(hừm…)"), said("“Aaaa… Uuu!” ‘nhaaa’ (Hmmm)"))
        assertEquals(listOf("ừm…Ý", "bạn;", "ha… a…..cuối;", "mà… à, nếu;", "oáp....Hầy;", "-ê....nhìn"), said("Ummm…Ý bạn; Haaa…..cuối; màaaa—nếu; Oáppp~....Hầy; -EH....nhìn"))
        assertEquals(listOf("xoạt…", "vi… i"), said("Xoạttt- *Viiiii*-"))
        assertEquals(listOf("hạng", "a a a", "và", "a a a+++,", "rồi", "ét ét ét"), said("hạng AAA và AAA+++, rồi SSS"))
        assertEquals(listOf("Chương", "ba,", "ba mươi."), said("Chương III, XXX."))
    }

    @Test
    fun anHonorificSuffixIsReadWithAnyBookOrigin() {
        val cases = listOf("Ariel-sama" to "Ariel-xa-ma", "Mary-san" to "Mary-xan", "Zeros-sensei" to "Zeros-xen-xây", "Goblin-san" to "Goblin-xan", "Noel-chan" to "Noel-chan",
            "sĩ-sama" to "sĩ-xa-ma", "thần-chan" to "thần-chan", "diện-san" to "diện-xan", "Bá-sama" to "Bá-xa-ma",
            "Sora-sama" to "Xô-ra-xa-ma", "Hinata-sama" to "Hi-na-ta-xa-ma", "Haruto-kun" to "Ha-ru-tô-cun", "Tanaka-senpai" to "Ta-na-ca-xen-pai",
            "Kate-san" to "Kate-xan", "Ian-sama" to "Ian-xa-ma")
        for ((token, reading) in cases) for (origin in listOf(null, "ja")) assertEquals("$token $origin", listOf("Rồi", "$reading."), said("Rồi $token.", origin))
    }

    @Test
    fun koreanTermsAreReadAloneAndAfterAName() {
        assertEquals(listOf("“óp-pa,", "un-ni!", "hi-ung", "nu-na”"), said("“Oppa, unnie! hyung noona”"))
        assertEquals(listOf("hi-ung-nim,", "Soleum-xi,", "Minho-óp-pa"), said("Hyung-nim, Soleum-ssi, Minho-oppa"))
        for (token in listOf("san", "sama", "nim", "ssi", "tan", "nee", "nii", "Kun", "con-sans", "Ra-TAN")) assertEquals(token, token, said("Rồi $token đến.")[1])
    }

    // ---- TN "Nghe ngay" lượt 3 (cùng các ca với tests/test_readaloud_sounds.py) ----
    @Test
    fun aLaughOrAnInterjectionIsReadAsSounds() {
        val cases = listOf("Haha" to "ha ha", "hahaha" to "ha ha ha", "HAHA" to "ha ha", "Hehe" to "hê hê", "Hihi" to "hi hi", "fufu" to "phu phu", "Hm" to "hừm", "Huh" to "hả",
            "Hic" to "hích", "Ooh" to "ô", "Urgh" to "ức")
        for ((token, reading) in cases) assertEquals(token, listOf("Rồi", "$reading,", "đến."), said("Rồi $token, đến."))
    }

    @Test
    fun aWordStretchedInSeveralPlacesIsCollectedWhenItMakesOneSyllable() {
        assertEquals("chào… ò", Shouts.stretchReading("Cccchhhhàaaaaaoooo"))
        assertEquals("sáng…", Shouts.stretchReading("sssssáaaannnngggg"))
        assertNull(Shouts.stretchReading("Bbbbbuuuuuôooiiii"))
    }

    @Test
    fun aStutterIsReadAsTheSoundItStarts() {
        val cases = listOf("T-tôi không biết." to "tờ… tôi không biết.", "“C-Chuyện đó" to "“chờ… Chuyện đó", "Ng-ngài và K-Không và Đ-Điều" to "ngờ… ngài và khờ… Không và đờ… Điều",
            "E-em muốn A-anh" to "e… em muốn a… anh", "[Kh- Không phải" to "[khờ… Không phải", "“……T-, tức là" to "“……tờ, tức là",
            "Hà-Hà đến, X-quang, E-mail" to "Hà-Hà đến, X-quang, E-mail")
        for ((text, expected) in cases) assertEquals(text, expected, said(text).joinToString(" "))
        assertEquals("“tờ… Xu-ki-nô-ki-xen-pai cho", said("“T-Tsukinoki-senpai cho", "ja").joinToString(" "))
        assertEquals("a… a-ni-me", said("A-anime").joinToString(" "))
    }

    @Test
    fun lvIsALevelOnlyRightBeforeANumber() {
        assertEquals("level 5, level 15], level 1 level 5 và level 40.", said("Lv 5, Lv.15] Lvl.1 LV5 và lv 40.").joinToString(" "))
        assertEquals("lờ vê ơi, lờ vê lờ. lờ vê", said("Lv ơi, LVL. LV").joinToString(" "))
    }

    @Test
    fun aCommonLoanwordIsReadWithAnyBookOrigin() {
        val cases = listOf("sofa" to "xô-pha", "Logic" to "lô-gích", "video" to "vi-đê-ô", "violin" to "vi-ô-lông", "piano" to "pi-a-nô", "sandal" to "xăng-đan", "vali" to "va-li",
            "robot" to "rô-bốt", "gorilla" to "gô-ri-la", "anime" to "a-ni-me", "Ninja" to "nin-gia", "manga" to "man-ga", "bento" to "ben-tô", "kimono" to "ki-mô-nô", "sake" to "xa-ke",
            "takoyaki" to "ta-cô-gia-ki", "senpai" to "xen-pai", "Umu" to "u-mu", "tsukkomi" to "xúc-cô-mi")
        for ((token, reading) in cases) for (origin in listOf(null, "ja", "ko")) assertEquals("$token $origin", "$reading.", said("Rồi $token.", origin)[1].lowercase())
    }

    @Test
    fun wonYenAndKwanAreUnitsOnlyAfterANumber() {
        assertEquals(listOf("3", "triệu", "guôn,", "100", "yên,", "5", "quan,", "mười", "guôn"), said("3 triệu won, 100 yen, 5 kwan, mười won"))
        assertEquals(listOf("Anh", "won,", "rồi", "yen."), said("Anh won, rồi yen."))
    }

    @Test
    fun aCapitalOStartingAHyphenatedNameIsASyllableNotALetter() {
        assertEquals(listOf("o-xu-ki-xan,", "o-ca-gia-ma,", "o-ni-xa-ma"), said("Otsuki-san, Okayama, Onii-sama", "ja"))
    }

    @Test
    fun aParenthesisedAbbreviationAndWordsGluedByAnEllipsisOrADash() {
        assertEquals(listOf("đó.”(giê em)", "xong"), said("đó.”(GM) xong"))
        assertEquals(listOf("rồi…xen-pai.”", "Babi, người"), said("rồi…Senpai.” Babi—người"))
        assertEquals(listOf("Thế", "chiến", "hai, thời", "kỳ"), said("Thế chiến II—thời kỳ"))
    }

    // ---- TN "Nghe ngay" lượt 4 (cùng các ca với tests/test_readaloud_sounds.py): gọi viết hoa cả, danh xưng viết tắt, mũi tên chữ ----
    @Test
    fun aShoutedHonorificIsReadLikeItsLowerCaseForm() {
        assertEquals("o-ni-chan, o-ni-chan LO LẮNG!", said("ONII-CHAN, ONII-CHAN LO LẮNG!").joinToString(" "))
        assertEquals("“ne-xan!” và óp-pa, ariel-xa-ma.", said("“NEE-SAN!” và OPPA, ARIEL-SAMA.").joinToString(" "))
        assertEquals("Kiểm tra ét a en và xen-pai", said("Kiểm tra SAN và SENPAI").joinToString(" "))
    }

    @Test
    fun aTitleBeforeANameIsReadInFull() {
        assertEquals("mister Lyle đến, missus Smith, miss Lee và doctor Stone.", said("Mr. Lyle đến, Mrs. Smith, Ms. Lee và Dr. Stone.").joinToString(" "))
        assertEquals("mục tiêu của mister lyle thôi, “mister Lyle” và (doctor Stone)", said("mục tiêu của mr.lyle thôi, “Mr.Lyle” và (dr.Stone)").joinToString(" "))
        assertEquals("saint Louis và doctor Stone, mister Lyle.", said("St. Louis và Dr Stone, Mr Lyle.").joinToString(" "))
        assertEquals("Main St. dài, Dr. nào, ở số 5St. Mr.", said("Main St. dài, Dr. nào, ở số 5St. Mr.").joinToString(" "))
    }

    @Test
    fun aTextArrowIsThanhOrNothing() {
        fun arrows(text: String) = said(text).filter { it.isNotEmpty() }.joinToString(" ")
        assertEquals("hát pê: 1780 thành 1940", arrows("HP: 1780 --> 1940"))
        assertEquals("A thành B, C thành D, E thành F, G thành H.", arrows("A -> B, C => D, E → F, G ⇒ H."))
        assertEquals("1780 thành 1940 và A thành B", arrows("1780->1940 và A-->B"))
        assertEquals("A B và C D, E F", arrows("A <- B và C ← D, E<-F"))
        assertEquals("Bước tiếp. Xong", arrows("-> Bước tiếp. → Xong"))
        assertEquals("A <-> B, x <= 5, a >= 3, a thành b c", arrows("A <-> B, x <= 5, a >= 3, a -> b <- c"))
    }
}
