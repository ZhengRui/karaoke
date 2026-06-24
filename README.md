# 卡拉OK MV 合成管线

把一组**照片** + **歌词** + **音频** 合成为一段带滚动卡拉OK字幕、Ken Burns 运镜的 1080p MV 视频。

入口是 `build_video.py`，整个流程切成 5 个可独立运行的阶段，全部由 ffmpeg 驱动。

## 依赖

- **Python 3**（仅标准库，无 pip 依赖）
- **ffmpeg / ffprobe**（硬依赖，承担全部合成工作）
  ```bash
  brew install ffmpeg   # macOS
  ```
- 可选 **Demucs**：仅在你想从成品歌曲里分离伴奏时才需要，主流程不调用它
  ```bash
  pip install demucs
  ```
- 字幕默认字体 `Heiti SC`，`karaoke/finalize.py` 默认从 `/System/Library/Fonts` 找字体——**macOS 专属**，换平台需调整字体与路径。

## 快速开始

在**项目根目录**下运行（需让 `karaoke/` 包可被导入）：

```bash
python build_video.py            # 用默认素材跑完整流程
```

成品默认输出到 `red_sun_karaoke.mp4`。

## 阶段

`python build_video.py --stage <名称>`，默认 `all` 按顺序全跑：

| 阶段 | 作用 |
|------|------|
| `subs`     | 解析 LRC 歌词 → 生成 `build/subtitles.ass` 卡拉OK字幕 |
| `stills`   | 把照片裁成统一画幅静帧（竖图模糊补边）→ `build/stills/` |
| `clips`    | 给每张静帧加 Ken Burns 运镜，切成等长无声片段 → `build/clips/` |
| `assemble` | 把片段交叉淡化拼接成背景视频 → `build/bg.mp4` |
| `finalize` | 背景 + 字幕 + 音频 → 最终 mp4 |

## 换一首新歌

准备 3 类输入，再用命令行参数指过去即可，无需改源码：

1. **照片**：一个目录，里面放 `.jpg`（只读 `*.jpg`）。文件名用数字（`1.jpg`、`2.jpg`…）会按数字排序决定首轮出场顺序；张数不够会自动洗牌循环铺满整首歌。
2. **歌词**：标准 LRC，每行 `[mm:ss.cc]歌词`（时间为该句出现时刻）。含"词："/"曲："/歌手名 的行会被当元数据跳过（关键词见 `karaoke/lrc.py`）。
3. **音频**：成品歌曲直接用即可；要纯伴奏可先用 Demucs 分离：
   ```bash
   demucs --two-stems=vocals 你的歌.mp3   # 输出 separated/htdemucs/歌名/{no_vocals,vocals}.wav
   ```

示例：

```bash
python build_video.py --clean \
  --photos my_imgs \
  --lrc my_song.lrc \
  --audio my_song.wav \
  --out my_song_mv.mp4 \
  --font "PingFang SC"
```

> `--clean` 会先清空 `--build` 目录，避免和上一首的中间产物混淆，换歌时建议带上。

## 参数

所有 `build_video.py` 顶部的配置项都已暴露为命令行参数（默认值即代码里的常量）。完整列表与默认值见：

```bash
python build_video.py --help
```

分组速览：

- **流程**：`--stage`、`--clean`
- **路径**：`--photos` `--lrc` `--audio` `--build` `--out`
- **时长**：`--photo-dur`（每张停留秒数）`--fade`（交叉淡化秒数）
- **字幕**：`--font` `--base-size` `--next-scale` `--y-cur` `--y-next` `--rise-ms` `--out-ms` `--intro-lead`
- **其他**：`--seed`（照片洗牌随机种子，固定即可复现）

## 字幕与音频不同步怎么办

字幕的时间完全由 `lyrics.lrc` 里的 `[mm:ss.cc]` 时间戳决定。不同步分两种情况：

### 整体偏移(最常见)

所有字幕统一早了或晚了几秒——通常是 LRC 来源和你的音频版本片头长度不同。用 `--offset` 整体平移即可：

- **正数 = 字幕延后**（字幕比音频早出现时,往后推）
- **负数 = 字幕提前**（字幕比音频晚出现时）

```bash
# 字幕整体早了 0.8 秒,往后推
python build_video.py --stage subs --offset 0.8   # 只重生成字幕,快速试
python build_video.py --offset 0.8                # 试好后跑完整流程
```

> 校验技巧:先 `--stage subs --offset X` 只重生成字幕,再 `--stage finalize` 合成预览,反复试出合适的 X,省得每次全流程重跑。也可以先在播放器(如 VLC 的 `G`/`H` 键)里调字幕延迟试出偏移量,再写回 `--offset`。
>
> 注意 `--intro-lead` 只影响第一句的淡入观感,不是全局对齐开关,别拿它对时间。

### 逐句漂移(开头对得上,越往后越偏)

说明这份 LRC 是给另一个时长/变速版本打的轴,固定偏移救不了。解决办法:

1. 换一份与你音频版本匹配的 LRC,再用 `--offset` 微调;
2. 用语音识别自动重新打轴——把 Demucs 分离出的干净人声 `separated/<歌>/vocals.wav` 喂给 **Whisper**(`whisper-timestamped` / `WhisperX`)生成词级时间戳,转成 LRC;
3. 用 [Aegisub](https://aegisub.org/) 等工具边听边手动打轴(最准但费时)。

## 测试

```bash
python -m unittest discover tests
```

## 目录结构

```
build_video.py        # 入口:参数解析 + 阶段编排
karaoke/              # 核心包
  lrc.py              #   LRC 歌词解析
  ass_gen.py          #   ASS 卡拉OK字幕生成(当前句大字/下句小字/切句上升淡出)
  photos.py           #   列照片、按种子排序铺满
  clips.py            #   静帧合成 + Ken Burns 运镜
  assemble.py         #   计算片段数、交叉淡化拼接
  finalize.py         #   烧字幕 + 合并音轨输出
photos/               # 输入照片
lyrics.lrc            # 输入歌词
separated/            # Demucs 分离出的音频
build/                # 中间产物(可用 --clean 清空)
tests/                # 单元测试
```
