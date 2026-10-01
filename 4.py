#!/usr/bin/env python3
"""小米手环 7 图片转换工具。

实现参考 melianmiko/zmake 的 Mi Band 7 默认编码：
- 颜色超过 256 色时量化到 256 色；
- 使用 8 位索引色调色板；
- 默认在 TGA-RLP（TGA image type 9）和普通 TGA-P 之间选择更小者；
- 使用 ZeppOS/Mi Band 的 46 字节 SOMH 描述段。

输出文件默认沿用旧工具的 .png 后缀，但实际内容是手环使用的 TGA。
"""

from __future__ import annotations

import argparse
import os
import struct
from pathlib import Path

from PIL import Image


DESCRIPTION_LENGTH = 46
PALETTE_SIZE = 256


class WorkingTGAConverter:
    def __init__(
        self,
        max_size: int | None = None,
        colors: int = 256,
        rle: bool | None = None,
    ):
        self.max_size = max_size
        # Mi Band 7 的调色板格式最多支持 256 色；0 保留为旧参数兼容写法。
        self.colors = 256 if colors == 0 else colors
        if not 2 <= self.colors <= 256:
            raise ValueError("颜色数量必须是 2 到 256（0 等同于 256）")
        # None=自动选择最小文件；True=强制 RLP；False=普通 TGA-P。
        self.rle = rle

    def pack(
        self,
        input_file: str | os.PathLike[str],
        output_path: str | None = None,
    ) -> Path:
        input_path = Path(input_file)
        with Image.open(input_path) as source:
            source.load()
            original_size = source.size
            image = self._preprocess(source.convert("RGBA"))
            indexed = self._quantize(image)

        rlp_data = self._build_tga(indexed, image.size, original_size, rle=True)
        raw_data = self._build_tga(indexed, image.size, original_size, rle=False)
        if self.rle is True:
            data, selected_rle = rlp_data, True
        elif self.rle is False:
            data, selected_rle = raw_data, False
        else:
            data, selected_rle = min(
                ((rlp_data, True), (raw_data, False)), key=lambda item: len(item[0])
            )
        destination = Path(output_path) if output_path else input_path.with_name(
            input_path.stem + "_watchface.png"
        )
        destination.write_bytes(data)
        self._validate_tga(data, image.size, selected_rle)
        mode = "TGA-RLP" if selected_rle else "TGA-P"
        print(
            f"转换成功: {destination} ({image.width}x{image.height}, "
            f"256 色索引 {mode}, {len(data)} bytes)"
        )
        return destination

    def batch_pack(self, input_dir: str | os.PathLike[str]) -> int:
        directory = Path(input_dir)
        if not directory.is_dir():
            raise NotADirectoryError(f"{directory} 不是有效目录")
        count = 0
        for path in sorted(directory.iterdir()):
            if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".webp"}:
                self.pack(path)
                count += 1
        print(f"批量转换完成，共成功转换 {count} 张图片")
        return count

    def _preprocess(self, image: Image.Image) -> Image.Image:
        # 默认不缩放；-s 只在用户明确要求时启用。
        if self.max_size is None:
            return image
        if self.max_size < 1:
            raise ValueError("最大尺寸必须大于 0")
        width, height = image.size
        if width <= self.max_size and height <= self.max_size:
            return image
        ratio = min(self.max_size / width, self.max_size / height)
        new_size = (max(1, round(width * ratio)), max(1, round(height * ratio)))
        return image.resize(new_size, Image.Resampling.LANCZOS)

    def _quantize(self, image: Image.Image) -> Image.Image:
        # 与 zmake 的 image_color_compress 一致：量化到最多 256 色。
        # 不使用抖动，避免在本来不超过 256 色的图中制造额外像素变化。
        # Pillow 新版本不允许 MEDIANCUT 直接处理 RGBA；zmake 对不透明图
        # 也会先转 RGB，含透明度的图则使用支持 RGBA 的 FASTOCTREE。
        alpha_min, alpha_max = image.getchannel("A").getextrema()
        if alpha_min == 255 and alpha_max == 255:
            return image.convert("RGB").quantize(
                colors=self.colors,
                method=Image.Quantize.MEDIANCUT,
                dither=Image.Dither.NONE,
            )
        return image.quantize(
            colors=self.colors,
            method=Image.Quantize.FASTOCTREE,
            dither=Image.Dither.NONE,
        )

    @staticmethod
    def _palette_alpha(indexed: Image.Image) -> list[int]:
        transparency = indexed.info.get("transparency")
        if transparency is None:
            return [255] * PALETTE_SIZE
        if isinstance(transparency, int):
            alpha = [255] * PALETTE_SIZE
            if 0 <= transparency < PALETTE_SIZE:
                alpha[transparency] = 0
            return alpha
        values = list(transparency)
        return (values + [255] * PALETTE_SIZE)[:PALETTE_SIZE]

    def _build_palette(self, indexed: Image.Image) -> bytes:
        raw = list(indexed.getpalette() or [])
        raw += [0] * (PALETTE_SIZE * 3 - len(raw))
        alpha = self._palette_alpha(indexed)
        palette = bytearray()
        for i in range(PALETTE_SIZE):
            r, g, b = raw[i * 3 : i * 3 + 3]
            a = alpha[i]
            # Mi Band/ZeppOS 的 dialog 编码使用 BGRA 调色板。
            palette.extend((b, g, r, a))
        return bytes(palette)

    @staticmethod
    def _description(width: int) -> bytes:
        description = bytearray(DESCRIPTION_LENGTH)
        description[0:4] = b"SOMH"
        struct.pack_into("<H", description, 4, width)
        return bytes(description)

    @staticmethod
    def _rle_encode(indices: bytes) -> bytes:
        """编码 TGA type 9 的 RAW/RLE 混合数据包。"""
        out = bytearray()
        i = 0
        n = len(indices)
        while i < n:
            # 连续相同索引适合 RLE 包；TGA 单包最多 128 个像素。
            run_end = i + 1
            while run_end < n and run_end - i < 128 and indices[run_end] == indices[i]:
                run_end += 1
            run_length = run_end - i
            if run_length >= 2:
                out.append(0x80 | (run_length - 1))
                out.append(indices[i])
                i = run_end
                continue

            # 收集 RAW 包，直到下一个可压缩重复段或达到 128 个像素。
            raw_start = i
            i += 1
            while i < n and i - raw_start < 128:
                next_end = i + 1
                while next_end < n and next_end - i < 128 and indices[next_end] == indices[i]:
                    next_end += 1
                if next_end - i >= 2:
                    break
                i += 1
            raw_length = i - raw_start
            out.append(raw_length - 1)
            out.extend(indices[raw_start:i])
        return bytes(out)

    def _build_tga(
        self,
        indexed: Image.Image,
        actual_size: tuple[int, int],
        original_size: tuple[int, int],
        rle: bool,
    ) -> bytes:
        del original_size  # SOMH 只保存真实宽度；与 zmake 保持一致。
        width, height = actual_size
        if width > 0xFFFF or height > 0xFFFF:
            raise ValueError("图片尺寸不能超过 65535")

        header = bytearray(18)
        header[0] = DESCRIPTION_LENGTH
        header[1] = 1       # color map present
        header[2] = 9 if rle else 1  # RLE palette or raw palette
        struct.pack_into("<H", header, 5, PALETTE_SIZE)
        header[7] = 32      # 32-bit BGRA palette entries
        struct.pack_into("<H", header, 12, width)
        struct.pack_into("<H", header, 14, height)
        header[16] = 8      # 8-bit palette indices
        header[17] = 0x20   # top-left origin, same as zmake

        description = self._description(width)
        palette = self._build_palette(indexed)
        pixels = bytes(indexed.getdata())
        pixel_data = self._rle_encode(pixels) if rle else pixels
        # 不添加 26 字节 TRUEVISION footer；参考 ImageToGTR3/MiBand7Tools
        # 的 ImageFix 和 zmake 都将文件截断在像素数据末尾。
        return bytes(header) + description + palette + pixel_data

    @staticmethod
    def _rle_decode(data: bytes, expected_pixels: int) -> bytes:
        out = bytearray()
        pos = 0
        while len(out) < expected_pixels:
            if pos >= len(data):
                raise ValueError("RLE 像素数据提前结束")
            packet = data[pos]
            pos += 1
            count = (packet & 0x7F) + 1
            if packet & 0x80:
                if pos >= len(data):
                    raise ValueError("RLE 包缺少索引")
                out.extend([data[pos]] * count)
                pos += 1
            else:
                if pos + count > len(data):
                    raise ValueError("RAW 包长度不足")
                out.extend(data[pos : pos + count])
                pos += count
        if len(out) != expected_pixels:
            raise ValueError("RLE 像素数量错误")
        return bytes(out)

    @classmethod
    def _validate_tga(cls, data: bytes, size: tuple[int, int], rle: bool) -> None:
        if len(data) < 18 + DESCRIPTION_LENGTH + PALETTE_SIZE * 4:
            raise ValueError("输出文件过短")
        if data[0] != DESCRIPTION_LENGTH or data[1] != 1:
            raise ValueError("输出不是 Mi Band 7 调色板 TGA")
        if data[2] != (9 if rle else 1):
            raise ValueError("TGA 压缩类型不正确")
        if struct.unpack_from("<H", data, 5)[0] != PALETTE_SIZE or data[7] != 32 or data[16] != 8:
            raise ValueError("调色板或像素深度不符合 Mi Band 7 格式")
        if data[18:22] != b"SOMH":
            raise ValueError("缺少 SOMH 描述段")
        width, height = struct.unpack_from("<HH", data, 12)
        if (width, height) != size:
            raise ValueError("头部尺寸与像素尺寸不一致")

        palette_start = 18 + DESCRIPTION_LENGTH
        pixel_start = palette_start + PALETTE_SIZE * 4
        pixel_data = data[pixel_start:]
        indices = cls._rle_decode(pixel_data, width * height) if rle else pixel_data
        if len(indices) != width * height:
            raise ValueError("像素区长度不正确")


def main() -> None:
    parser = argparse.ArgumentParser(description="小米手环 7 表盘图片转换工具")
    parser.add_argument("input", help="输入 PNG/JPG/BMP/WEBP 文件或目录")
    parser.add_argument("-o", "--output", help="输出文件路径（仅适用于单文件转换）")
    parser.add_argument("-b", "--batch", action="store_true", help="批量转换目录中的图片")
    parser.add_argument(
        "-s", "--max-size", type=int, default=None,
        help="可选的最大宽/高；默认不缩放，避免破坏像素",
    )
    parser.add_argument(
        "-c", "--colors", type=int, default=256,
        help="颜色压缩数量（2-256；默认 256；0 等同于 256）",
    )
    rle_group = parser.add_mutually_exclusive_group()
    rle_group.add_argument(
        "--rle", dest="rle", action="store_true",
        help="强制使用 TGA-RLP 游程压缩",
    )
    rle_group.add_argument(
        "--no-rle", dest="rle", action="store_false",
        help="强制使用普通 TGA-P",
    )
    parser.set_defaults(rle=None)
    args = parser.parse_args()
    converter = WorkingTGAConverter(args.max_size, args.colors, rle=args.rle)
    if args.batch:
        converter.batch_pack(args.input)
    else:
        converter.pack(args.input, args.output)


if __name__ == "__main__":
    main()
