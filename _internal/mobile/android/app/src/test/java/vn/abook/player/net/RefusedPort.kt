package vn.abook.player.net

import java.net.InetSocketAddress
import java.net.Socket

/** Reserve a TCP port without listening so another test cannot claim the refusal endpoint. */
internal fun <T> withRefusedPort(block: (Int) -> T): T = Socket().use { reserved ->
    reserved.bind(InetSocketAddress("127.0.0.1", 0))
    block(reserved.localPort)
}
