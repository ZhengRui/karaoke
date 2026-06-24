import argparse
import shutil
import subprocess
from pathlib import Path

from karaoke.lrc import parse_lrc
from karaoke.ass_gen import build_ass
from karaoke.photos import list_photos, build_sequence
from karaoke.clips import compose_still, ken_burns
from karaoke.assemble import clips_needed, assemble
from karaoke.finalize import finalize

# ---------------- 默认值(可用命令行参数覆盖) ----------------
ROOT = Path(__file__).parent
PHOTOS_DIR = ROOT / "photos"
LRC_FILE = ROOT / "lyrics.lrc"
AUDIO = ROOT / "separated/htdemucs/red_sun/remix.wav"
BUILD = ROOT / "build"
OUT = ROOT / "red_sun_karaoke.mp4"

PHOTO_DUR = 6.5          # 每张照片停留秒数
FADE = 1.0              # 交叉淡化秒数

# ---- 滚动歌词字幕 ----
FONT = "Heiti SC"
BASE_SIZE = 84          # 当前句字号(特大);下句按 NEXT_SCALE 缩小
NEXT_SCALE = 0.62       # 下句相对当前句的缩放
Y_CUR = 920             # 当前句垂直中心(0~1080,越大越靠下)
Y_NEXT = 1018           # 下句垂直中心(与 Y_CUR 的差=行间距)
RISE_MS = 300           # 切句:下句升为当前的时长
OUT_MS = 220            # 切句:当前句原地淡出消失的时长
INTRO_LEAD = 1.6        # 第一句提前多少秒作为"下句"淡入
SEED = 7
# ----------------------------------------------------------


def audio_duration(audio):
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(audio)])
    return float(out.strip())


def stage_subs(cfg):
    dur = audio_duration(cfg.audio)
    lines = parse_lrc(cfg.lrc.read_text())
    ass = build_ass(lines, audio_end=dur, font=cfg.font,
                    base_size=cfg.base_size, next_scale=cfg.next_scale,
                    y_cur=cfg.y_cur, y_next=cfg.y_next,
                    rise_ms=cfg.rise_ms, out_ms=cfg.out_ms, intro_lead=cfg.intro_lead)
    cfg.build.mkdir(exist_ok=True)
    (cfg.build / "subtitles.ass").write_text(ass)
    print(f"subs: {len(lines)} lines → {cfg.build / 'subtitles.ass'} (audio_end={dur:.2f})")


def stage_stills(cfg):
    photos = list_photos(cfg.photos)
    (cfg.build / "stills").mkdir(parents=True, exist_ok=True)
    for p in photos:
        compose_still(p, cfg.build / "stills" / f"{p.stem}.png")
    print(f"stills: {len(photos)} composed")


def stage_clips(cfg):
    photos = list_photos(cfg.photos)
    n = clips_needed(audio_duration(cfg.audio), dur=cfg.photo_dur, fade=cfg.fade)
    seq = build_sequence(photos, target_count=n, seed=cfg.seed)
    (cfg.build / "clips").mkdir(parents=True, exist_ok=True)
    for i, p in enumerate(seq):
        still = cfg.build / "stills" / f"{p.stem}.png"
        ken_burns(still, cfg.build / "clips" / f"clip_{i:03d}.mp4",
                  dur=cfg.photo_dur, fps=30, zoom_in=(i % 2 == 0))
    print(f"clips: {n} generated")


def stage_assemble(cfg):
    n = clips_needed(audio_duration(cfg.audio), dur=cfg.photo_dur, fade=cfg.fade)
    clips = [cfg.build / "clips" / f"clip_{i:03d}.mp4" for i in range(n)]
    total = assemble(clips, cfg.build / "bg.mp4", dur=cfg.photo_dur, fade=cfg.fade)
    print(f"assemble: {n} clips → {cfg.build / 'bg.mp4'} (~{total:.1f}s)")


def stage_finalize(cfg):
    finalize(cfg.build / "bg.mp4", cfg.build / "subtitles.ass", cfg.audio, cfg.out)
    print(f"finalize: → {cfg.out}")


STAGES = {
    "subs": stage_subs, "stills": stage_stills, "clips": stage_clips,
    "assemble": stage_assemble, "finalize": stage_finalize,
}


def build_parser():
    ap = argparse.ArgumentParser(
        description="卡拉OK MV 合成管线:照片 + 歌词 + 音频 → 1080p 视频。",
        epilog=(
            "示例:\n"
            "  python build_video.py                       # 用默认素材跑完整流程\n"
            "  python build_video.py --stage clips         # 只重跑 clips 阶段\n"
            "  python build_video.py --photos imgs --lrc song.lrc \\\n"
            "                        --audio song.wav --out song_mv.mp4\n"
            "阶段顺序: subs → stills → clips → assemble → finalize"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    g_flow = ap.add_argument_group("流程")
    g_flow.add_argument("--stage", choices=list(STAGES) + ["all"], default="all",
                        help="要执行的阶段,all 表示按顺序全跑 (默认: all)")
    g_flow.add_argument("--clean", action="store_true",
                        help="运行前清空 build 目录(避免和上一首的中间产物混淆)")

    g_path = ap.add_argument_group("路径")
    g_path.add_argument("--photos", type=Path, default=PHOTOS_DIR,
                        help="照片目录(只读取 *.jpg) (默认: %(default)s)")
    g_path.add_argument("--lrc", type=Path, default=LRC_FILE,
                        help="LRC 歌词文件 (默认: %(default)s)")
    g_path.add_argument("--audio", type=Path, default=AUDIO,
                        help="音频文件(伴奏/成品) (默认: %(default)s)")
    g_path.add_argument("--build", type=Path, default=BUILD,
                        help="中间产物目录 (默认: %(default)s)")
    g_path.add_argument("--out", type=Path, default=OUT,
                        help="最终输出 mp4 (默认: %(default)s)")

    g_time = ap.add_argument_group("时长")
    g_time.add_argument("--photo-dur", type=float, default=PHOTO_DUR,
                        help="每张照片停留秒数 (默认: %(default)s)")
    g_time.add_argument("--fade", type=float, default=FADE,
                        help="相邻片段交叉淡化秒数 (默认: %(default)s)")

    g_sub = ap.add_argument_group("字幕")
    g_sub.add_argument("--font", default=FONT,
                       help="字幕字体名 (默认: %(default)s)")
    g_sub.add_argument("--base-size", type=int, default=BASE_SIZE,
                       help="当前句字号 (默认: %(default)s)")
    g_sub.add_argument("--next-scale", type=float, default=NEXT_SCALE,
                       help="下句相对当前句的缩放 (默认: %(default)s)")
    g_sub.add_argument("--y-cur", type=int, default=Y_CUR,
                       help="当前句垂直中心,0~1080 越大越靠下 (默认: %(default)s)")
    g_sub.add_argument("--y-next", type=int, default=Y_NEXT,
                       help="下句垂直中心,与 y-cur 之差=行间距 (默认: %(default)s)")
    g_sub.add_argument("--rise-ms", type=int, default=RISE_MS,
                       help="切句时下句升为当前句的时长(毫秒) (默认: %(default)s)")
    g_sub.add_argument("--out-ms", type=int, default=OUT_MS,
                       help="切句时当前句原地淡出的时长(毫秒) (默认: %(default)s)")
    g_sub.add_argument("--intro-lead", type=float, default=INTRO_LEAD,
                       help="第一句提前多少秒作为下句淡入 (默认: %(default)s)")

    g_misc = ap.add_argument_group("其他")
    g_misc.add_argument("--seed", type=int, default=SEED,
                        help="照片序列洗牌随机种子 (默认: %(default)s)")

    return ap


def main():
    cfg = build_parser().parse_args()
    if cfg.clean and cfg.build.exists():
        shutil.rmtree(cfg.build)
        print(f"clean: removed {cfg.build}")
    order = ["subs", "stills", "clips", "assemble", "finalize"]
    todo = order if cfg.stage == "all" else [cfg.stage]
    for s in todo:
        print(f"=== {s} ===")
        STAGES[s](cfg)


if __name__ == "__main__":
    main()
