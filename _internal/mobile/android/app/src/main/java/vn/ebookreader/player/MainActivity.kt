package vn.ebookreader.player

import android.os.Bundle
import com.getcapacitor.BridgeActivity

class MainActivity : BridgeActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        registerPlugin(PlayerPlugin::class.java)
        registerPlugin(LibraryPlugin::class.java)
        super.onCreate(savedInstanceState)
    }

    // Mở app là máy tính thấy điện thoại (để "Phát trên điện thoại" được cả khi chưa nghe gì) - Remote.
    override fun onResume() {
        super.onResume()
        Playback.init(this)
        Remote.foreground = true
    }

    override fun onPause() {
        Remote.foreground = false
        super.onPause()
    }
}
