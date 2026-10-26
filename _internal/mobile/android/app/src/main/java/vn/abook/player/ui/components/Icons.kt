package vn.abook.player.ui.components

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawWithCache
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.scale
import androidx.compose.ui.graphics.vector.PathParser
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/*
 * Biểu tượng = đúng hình lucide của bản web (DESIGN.md luật 8: cùng việc, cùng biểu tượng), nét lấy từ LucidePaths (sinh bởi
 * scripts/gen_lucide_icons.py). Vẽ như lucide-react: lưới 24 co theo cỡ ô, nét 2 đơn vị lưới, đầu và góc tròn. Không vẽ tay phỏng theo.
 */

private val parsed = HashMap<String, Path>()

/** Đường của một chuỗi SVG, dịch một lần cho cả app (các icon chỉ đọc). */
internal fun lucidePath(data: String): Path = parsed.getOrPut(data) { PathParser().parsePathString(data).toPath() }

private val GridStroke = Stroke(width = 2f, cap = StrokeCap.Round, join = StrokeJoin.Round)

/** Vẽ một icon lucide trong Canvas tự vẽ: `unit` = px của một đơn vị lưới 24 (mặc định phủ bề ngang ô). */
internal fun DrawScope.drawLucide(data: String, color: Color, unit: Float = size.width / 24f, fill: String? = null) {
    scale(unit, unit, Offset.Zero) {
        drawPath(lucidePath(data), color, style = GridStroke)
        if (fill != null) drawPath(lucidePath(fill), color)
    }
}

@Composable
fun LucideIcon(data: String, color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp, fill: String? = null) {
    Box(
        modifier.size(size).drawWithCache {
            val path = lucidePath(data)
            val dots = fill?.let(::lucidePath)
            val unit = this.size.width / 24f
            onDrawBehind {
                scale(unit, unit, Offset.Zero) {
                    drawPath(path, color, style = GridStroke)
                    if (dots != null) drawPath(dots, color)
                }
            }
        },
    )
}

@Composable fun PlusIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.PLUS, color, modifier, size)
@Composable fun SearchIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.SEARCH, color, modifier, size)
@Composable fun CloseIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.X, color, modifier, size)

/** Xếp theo (web: ArrowDownWideNarrow). */
@Composable fun SortIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.ARROW_DOWN_WIDE_NARROW, color, modifier, size)

/** Dấu chọn ở đầu / cuối dòng. */
@Composable fun CheckIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.CHECK, color, modifier, size)

/** Dấu nguồn của sách ở máy khác (web: Laptop). */
@Composable fun RemoteIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 14.dp) = LucideIcon(LucidePaths.LAPTOP, color, modifier, size)

/** "Thêm" (menu "…"). */
@Composable fun MoreIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.ELLIPSIS, color, modifier, size)

/** "Từ đầu" (web: RotateCcw). */
@Composable fun RestartIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.ROTATE_CCW, color, modifier, size)

@Composable fun SpeakerIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.SPEAKER, color, modifier, size)
@Composable fun TvIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.TV, color, modifier, size)
@Composable fun MonitorSpeakerIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.MONITOR_SPEAKER, color, modifier, size)
@Composable fun CastIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.CAST, color, modifier, size)

/** "Làm mới" (web: RefreshCw) - khác "Từ đầu". */
@Composable fun RefreshIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.REFRESH_CW, color, modifier, size)

/** Chương chưa có audio (web: CircleDashed). */
@Composable fun DashedCircleIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.CIRCLE_DASHED, color, modifier, size)

@Composable fun PencilIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.PENCIL, color, modifier, size)
@Composable fun ShareIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.SHARE_2, color, modifier, size)
@Composable fun TrashIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.TRASH_2, color, modifier, size)

/** "Đọc theo" (web: BookOpenText). */
@Composable fun BookOpenIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.BOOK_OPEN_TEXT, color, modifier, size)

/** "Xuất" (web: FileDown ở menu sách). */
@Composable fun ExportIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.FILE_DOWN, color, modifier, size)

/** "Nhạc nền" (web: EighthNote ở trình phát và menu sách). */
@Composable fun MusicIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.EIGHTH_NOTE, color, modifier, size)

/** "Đổi bài" và "Chọn" của một đoạn nhạc gắn sẵn (web: Shuffle / Pin ở Sửa sách > Nhạc nền). */
@Composable fun ShuffleIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.SHUFFLE, color, modifier, size)
@Composable fun PinIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.PIN, color, modifier, size)

/* Sáu nhóm Cài đặt - đúng bộ của SettingsNav.tsx: AudioLines, Headphones, MoonStar, Palette, MonitorSmartphone, Wrench. */

@Composable fun VoiceIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.AUDIO_LINES, color, modifier, size)
@Composable fun HeadphonesIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.HEADPHONES, color, modifier, size)
@Composable fun MoonIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.MOON_STAR, color, modifier, size)
@Composable fun ThemeIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) =
    LucideIcon(LucidePaths.PALETTE, color, modifier, size, fill = LucidePaths.PALETTE_FILL)
@Composable fun DevicesIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.MONITOR_SMARTPHONE, color, modifier, size)
@Composable fun WrenchIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.WRENCH, color, modifier, size)

/* Thêm sách / sửa sách / thiết bị. */

@Composable fun FileIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.FILE, color, modifier, size)
@Composable fun FolderIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.FOLDER_OPEN, color, modifier, size)
@Composable fun ImageIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.IMAGE_PLUS, color, modifier, size)
@Composable fun LaptopIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.LAPTOP, color, modifier, size)
@Composable fun PhoneIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.SMARTPHONE, color, modifier, size)
@Composable fun BluetoothIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.BLUETOOTH, color, modifier, size)

/* Giọng đọc - đúng bộ của VoiceSettings.tsx: Download (tải giọng), Upload (thêm nhạc), KeyRound (khoá trực tuyến), Play / Square (nghe thử / dừng). */

@Composable fun DownloadIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.DOWNLOAD, color, modifier, size)
@Composable fun UploadIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.UPLOAD, color, modifier, size)
@Composable fun KeyIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.KEY_ROUND, color, modifier, size)
@Composable fun PlayIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.PLAY, color, modifier, size)
@Composable fun StopIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) = LucideIcon(LucidePaths.SQUARE, color, modifier, size)
