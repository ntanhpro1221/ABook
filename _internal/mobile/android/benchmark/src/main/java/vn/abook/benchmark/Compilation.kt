package vn.abook.benchmark

import androidx.benchmark.macro.CompilationMode
import androidx.benchmark.macro.ExperimentalMacrobenchmarkApi
import androidx.test.platform.app.InstrumentationRegistry

/**
 * Chế độ biên dịch của mọi bài đo. Mặc định `Partial` (nạp baseline profile, máy ảo / máy thường). ColorOS chặn `cmd package compile`
 * nên trên OPPO truyền `-e compilationMode ignore` và cài bằng `install-multiple app.apk app.dm` (status=speed-profile) trước khi đo.
 */
@OptIn(ExperimentalMacrobenchmarkApi::class)
internal fun compilation(): CompilationMode =
    if (InstrumentationRegistry.getArguments().getString("compilationMode") == "ignore") CompilationMode.Ignore() else CompilationMode.Partial()
