package vn.abook.player.ui.devices

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PairingEventsTest {
    @Test fun `pairing event arriving before the create code response cannot resurrect the code`() {
        val source = FakeDevicesSource()
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        try {
            val devices = DevicesState(source, scope, now = { 1_700_000_000_000L })
            val gate = kotlinx.coroutines.CompletableDeferred<Unit>()
            source.codeGate = gate
            devices.newCode()
            source.share = source.share.copy(code = null)
            source.shareEvents.tryEmit(Unit)
            gate.complete(Unit)
            assertNull(devices.share.value.share.code)
            assertEquals(1, source.shareReads)
        } finally { scope.cancel() }
    }

    @Test fun `server event removes consumed code and loads the newly paired device`() {
        val source = FakeDevicesSource()
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        try {
            val devices = DevicesState(source, scope, now = { 1_700_000_000_000L })
            devices.newCode()
            assertEquals("482915", devices.share.value.share.code?.digits)
            val sharer = Sharer("new", "Other phone", 1_700_000_000.0)
            source.share = source.share.copy(code = null, devices = listOf(sharer))
            source.shareEvents.tryEmit(Unit)
            assertNull(devices.share.value.share.code)
            assertEquals(listOf(sharer), devices.share.value.share.devices)
            assertEquals(1, source.shareReads)
        } finally { scope.cancel() }
    }

    @Test fun `expiry fires once without reading the source again`() = runBlocking {
        val source = FakeDevicesSource()
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        try {
            source.share = Share(running = true, code = Code("123456", 1000.03))
            val devices = DevicesState(source, scope, now = { 1_000_000L })
            devices.openShare()
            assertEquals("123456", devices.share.value.share.code?.digits)
            withTimeout(3000) { devices.share.first { it.loaded && it.share.code == null } }
            assertEquals("A deadline must not poll the server", 1, source.shareReads)
        } finally { scope.cancel() }
    }

    @Test fun `a new code cancels the previous expiry`() {
        val source = FakeDevicesSource()
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        try {
            val devices = DevicesState(source, scope, now = { 1_700_000_000_000L })
            devices.newCode()
            devices.cancelCode()
            assertNull(devices.share.value.share.code)
            devices.newCode()
            assertEquals("482915", devices.share.value.share.code?.digits)
            assertEquals(0, source.shareReads)
        } finally { scope.cancel() }
    }
}
