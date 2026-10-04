package vn.abook.player

import java.io.File
import java.security.KeyFactory
import java.security.KeyPairGenerator
import java.security.MessageDigest
import java.security.PrivateKey
import java.security.Signature
import java.security.spec.PKCS8EncodedKeySpec
import java.util.Base64
import org.json.JSONObject

/**
 * Ký danh mục / cấu hình thử cho test JVM bằng khoá TEST của tests/fixtures/catalog_signing (xem README ở đó: khoá chỉ dùng cho test,
 * không liên quan khoá thật của ABook). JDK 21 có Ed25519 trong `java.security` (app thật chạy từ API 24 nên dùng Tink để KIỂM - Signatures.kt).
 */
object CatalogSigning {
    /** Thư mục fixture dùng chung với pytest (`tests/test_music_catalog_signing.py`). */
    val fixture = File("../../../tests/fixtures/catalog_signing")
    const val ISSUED = "2026-10-04T00:00:00Z"

    private fun hex(text: String): ByteArray = text.trim().chunked(2).map { it.toInt(16).toByte() }.toByteArray()

    val publicKey: ByteArray by lazy { hex(File(fixture, "public_key.hex").readText()) }
    val testKey: PrivateKey by lazy {
        // PKCS#8 của khoá Ed25519 = tiền tố cố định + hạt 32 byte
        KeyFactory.getInstance("Ed25519").generatePrivate(PKCS8EncodedKeySpec(hex("302e020100300506032b657004220420") + hex(File(fixture, "test_private_seed.hex").readText())))
    }

    /** Một khoá lạ (người khác ký) - app phải từ chối. */
    fun strangerKey(): PrivateKey = KeyPairGenerator.getInstance("Ed25519").generateKeyPair().private

    fun sha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    /** Nội dung file `.sig`: chữ ký Ed25519 trên đúng các byte `raw`, base64, một dòng. */
    fun sign(raw: ByteArray, key: PrivateKey = testKey): ByteArray {
        val signature = Signature.getInstance("Ed25519")
        signature.initSign(key)
        signature.update(raw)
        return Base64.getEncoder().encode(signature.sign()) + "\n".toByteArray()
    }

    /** Điền `files` (sha256 mọi file .json trong tracks/ và cells/ của `cloud`) và `issued` (nếu chưa có), ghi manifest.json + manifest.json.sig. */
    fun writeManifest(cloud: File, manifest: JSONObject) {
        val files = JSONObject()
        for (folder in listOf("tracks", "cells")) {
            File(cloud, folder).listFiles { file -> file.name.endsWith(".json") }?.sortedBy { it.name }?.forEach { files.put("$folder/${it.name}", sha256(it.readBytes())) }
        }
        manifest.put("files", files)
        if (!manifest.has("issued")) manifest.put("issued", ISSUED)
        val raw = manifest.toString().toByteArray(Charsets.UTF_8)
        File(cloud, "manifest.json").writeBytes(raw)
        File(cloud, "manifest.json.sig").writeBytes(sign(raw))
    }

    /** Nguồn danh mục thử: chép `good/` của fixture vào `root/cloud` rồi phủ lần lượt các thư mục ca (`newer`, `bad_signature`...). */
    fun cloud(root: File, vararg cases: String): File {
        val cloud = File(root, "cloud")
        if (!cloud.exists()) File(fixture, "good").copyRecursively(cloud)
        for (case in cases) File(fixture, case).copyRecursively(cloud, overwrite = true)
        return cloud
    }
}
