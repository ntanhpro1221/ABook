// Giọng khựng quá lâu: đang phát mà vị trí đứng yên (đệm, đọc to chờ đoạn kế) từ `voiceStallFadeAfterSeconds` (music_mix.json, chung ba nền)
// trở lên. Khi ấy nhạc nền mờ xuống như lúc giọng tự hết, chứ không kêu một mình tới chốt chờ của trình phát; vị trí chạy lại (có tiếng,
// hay người nghe tua) thì nhạc lên lại. Android: VoiceStall.kt, Qt: MusicLogic::VoiceStall - cùng luật.
import mix from "../../../abook/webui/assets/music_mix.json";

/** Chọn theo khe nối đo thật (docs/MUSIC_RESEARCH.md, 01-11): đọc to Edge chưa có sẵn, 1 giờ, 153 chỗ nối - dài nhất 8,8 s. */
export const VOICE_STALL_MS = mix.voiceStallFadeAfterSeconds * 1000;

/** Trong lúc khựng không có sự kiện thời gian nào: trình phát hỏi lại theo nhịp này (mờ muộn nhất chừng ấy sau hạn). */
export const VOICE_STALL_TICK_MS = 1000;

export class VoiceStall {
  private since: number | null = null;
  private at = Number.NaN;

  constructor(private readonly afterMs = VOICE_STALL_MS) {}

  /** `playing`: giọng đang phát (chưa bị người nghe dừng); true = đã khựng quá hạn. */
  update(nowMs: number, position: number, playing: boolean): boolean {
    if (!playing) {
      this.since = null;
      return false;
    }
    if (this.since === null || position !== this.at) {
      this.since = nowMs;
      this.at = position;
      return false;
    }
    return nowMs - this.since >= this.afterMs;
  }
}
