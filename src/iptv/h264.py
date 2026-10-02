"""从 H.264 码流里解出真实分辨率。

为什么必须自己解：HLS 主清单里带 RESOLUTION 的源只有不到一成
（实测 197 条可用流里只有 19 条声明了分辨率），剩下九成全靠
播放器的 OSD 才知道是 1080p 还是 720x576 标清。
不自己解出来，「按分辨率排序」就是空转。

做法：在视频 ES 里找 SPS（NAL 类型 7），按 H.264 语法解到
pic_width_in_mbs_minus1 / pic_height_in_map_units_minus1，再减掉裁剪。
"""

from __future__ import annotations

# 用这些 profile 时 SPS 里多一段 chroma_format_idc 等字段
_HIGH_PROFILES = {100, 110, 122, 244, 44, 83, 86, 118, 128, 138, 139, 134, 135}

# 解析出来的分辨率要落在这个范围内才认，防止把随机数据当 SPS
_MIN_W, _MAX_W = 128, 8192
_MIN_H, _MAX_H = 96, 8192


class _Bits:
    """按位读取，含 Exp-Golomb。越界一律当 0，让解析自然失败而不是抛异常。"""

    def __init__(self, data: bytes) -> None:
        self.d = data
        self.pos = 0

    def u(self, n: int) -> int:
        v = 0
        for _ in range(n):
            idx = self.pos >> 3
            byte = self.d[idx] if idx < len(self.d) else 0
            v = (v << 1) | ((byte >> (7 - (self.pos & 7))) & 1)
            self.pos += 1
        return v

    def ue(self) -> int:
        zeros = 0
        while self.u(1) == 0:
            zeros += 1
            if zeros > 31:
                raise ValueError("Exp-Golomb 前缀过长")
        return (1 << zeros) - 1 + (self.u(zeros) if zeros else 0)

    def se(self) -> int:
        v = self.ue()
        return (v + 1) // 2 if v & 1 else -(v // 2)


def unescape(data: bytes) -> bytes:
    """去掉防竞争字节（0x00 0x00 0x03 -> 0x00 0x00）。"""
    out = bytearray()
    zeros = 0
    for x in data:
        if zeros >= 2 and x == 0x03:
            zeros = 0
            continue
        zeros = zeros + 1 if x == 0 else 0
        out.append(x)
    return bytes(out)


def _skip_scaling_list(b: _Bits, size: int) -> None:
    last, nxt = 8, 8
    for _ in range(size):
        if nxt != 0:
            nxt = (last + b.se() + 256) % 256
        last = nxt or last


def parse_sps(nal: bytes) -> tuple[int, int] | None:
    """输入一个 NAL 单元（含 1 字节 nal_header），返回 (宽, 高)。"""
    if len(nal) < 4 or (nal[0] & 0x1F) != 7:
        return None
    b = _Bits(unescape(nal)[1:])
    try:
        profile = b.u(8)
        b.u(8)                      # constraint flags + reserved
        b.u(8)                      # level_idc
        b.ue()                      # seq_parameter_set_id

        chroma = 1                  # 默认 4:2:0
        if profile in _HIGH_PROFILES:
            chroma = b.ue()
            if chroma == 3:
                b.u(1)              # separate_colour_plane_flag
            b.ue()                  # bit_depth_luma_minus8
            b.ue()                  # bit_depth_chroma_minus8
            b.u(1)                  # qpprime_y_zero_transform_bypass_flag
            if b.u(1):              # seq_scaling_matrix_present_flag
                for i in range(12 if chroma == 3 else 8):
                    if b.u(1):
                        _skip_scaling_list(b, 16 if i < 6 else 64)

        b.ue()                      # log2_max_frame_num_minus4
        poc_type = b.ue()
        if poc_type == 0:
            b.ue()                  # log2_max_pic_order_cnt_lsb_minus4
        elif poc_type == 1:
            b.u(1)                  # delta_pic_order_always_zero_flag
            b.se()                  # offset_for_non_ref_pic
            b.se()                  # offset_for_top_to_bottom_field
            for _ in range(b.ue()):
                b.se()
        b.ue()                      # max_num_ref_frames
        b.u(1)                      # gaps_in_frame_num_value_allowed_flag

        width_mbs = b.ue() + 1
        height_units = b.ue() + 1
        frame_mbs_only = b.u(1)
        if not frame_mbs_only:
            b.u(1)                  # mb_adaptive_frame_field_flag
        b.u(1)                      # direct_8x8_inference_flag

        crop_l = crop_r = crop_t = crop_b = 0
        if b.u(1):                  # frame_cropping_flag
            crop_l, crop_r, crop_t, crop_b = b.ue(), b.ue(), b.ue(), b.ue()
    except (ValueError, IndexError):
        return None

    width = width_mbs * 16
    height = height_units * 16 * (2 - frame_mbs_only)

    if chroma == 0:
        unit_x, unit_y = 1, 2 - frame_mbs_only
    else:
        sub_w, sub_h = {1: (2, 2), 2: (2, 1), 3: (1, 1)}.get(chroma, (2, 2))
        unit_x, unit_y = sub_w, sub_h * (2 - frame_mbs_only)

    width -= (crop_l + crop_r) * unit_x
    height -= (crop_t + crop_b) * unit_y

    if not (_MIN_W <= width <= _MAX_W and _MIN_H <= height <= _MAX_H):
        return None
    return width, height


def find_sps(es: bytes, max_scan: int = 0) -> bytes | None:
    """在一段 Annex-B 码流里找第一个能正常解出的 SPS NAL（含 nal_header）。

    参数是视频 ES（可以夹杂 PES 头，不影响：SPS 就在里面）。
    会依次尝试每个 SPS 候选，跳过解不出来的（防竞争字节错位、
    或者碰巧撞上 00 00 01 的普通数据）。
    """
    limit = max_scan or len(es)
    i = 0
    tries = 0
    while i < limit - 4 and tries < 8:
        if es[i] == 0 and es[i + 1] == 0 and es[i + 2] == 1 and (es[i + 3] & 0x1F) == 7:
            tries += 1
            start = i + 3
            nxt = es.find(b"\x00\x00\x01", start + 1)
            end = nxt + 1 if nxt > 0 else min(len(es), start + 512)
            nal = es[start:end].rstrip(b"\x00")
            if parse_sps(nal):
                return nal
            i = start + 1
            continue
        i += 1
    return None


def find_resolution(es: bytes, max_scan: int = 0) -> tuple[int, int] | None:
    """在 Annex-B 码流里找 SPS 并解出分辨率。"""
    nal = find_sps(es, max_scan)
    return parse_sps(nal) if nal else None
