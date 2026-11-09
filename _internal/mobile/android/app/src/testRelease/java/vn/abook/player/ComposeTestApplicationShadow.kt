package vn.abook.player

import android.content.ComponentName
import androidx.activity.ComponentActivity
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Implementation
import org.robolectric.annotation.Implements
import org.robolectric.annotation.RealObject
import org.robolectric.shadow.api.Shadow
import org.robolectric.shadows.ShadowApplication

/** Release unit tests need the same Compose host as debug's ui-test-manifest, only inside Robolectric. */
@Implements(AbookApplication::class)
class ComposeTestApplicationShadow : ShadowApplication() {
    @RealObject
    private lateinit var application: AbookApplication

    @Implementation
    protected fun onCreate() {
        Shadow.directlyOn<Any?, AbookApplication>(application, AbookApplication::class.java, "onCreate")
        shadowOf(application.packageManager)
            .addActivityIfNotPresent(ComponentName(application, ComponentActivity::class.java))
            .apply {
                exported = true
                theme = android.R.style.Theme_Material_Light_NoActionBar
            }
    }
}
