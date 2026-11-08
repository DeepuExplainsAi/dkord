package app.dkord

import android.app.Activity
import android.graphics.Color
import android.os.Bundle
import android.widget.FrameLayout

/** Idle CI launcher without Google widgets/network. Real app/test windows and IME are unchanged. */
class EmulatorHomeActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(FrameLayout(this).apply { setBackgroundColor(Color.rgb(24, 24, 28)) })
    }
}
