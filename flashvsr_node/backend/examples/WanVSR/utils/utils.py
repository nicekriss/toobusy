from einops import rearrange, repeat

import torch
import torch.nn as nn
import torch.nn.functional as F
from tqdm import tqdm
import time
import math

CACHE_T = 2

def block_sparse_attn_func(q, k, v, cu_seqlens_q, cu_seqlens_k, head_mask_type,
                          streaming_info, base_blockmask, max_seqlen_q_, max_seqlen_k_,
                          p_dropout, deterministic=False, softmax_scale=None,
                          is_causal=False, exact_streaming=False, return_attn_probs=False):
    """
    使用标准注意力机制替代块稀疏注意力实现
    """
    batch_size = 1
    seq_len_q = q.shape[0] // batch_size
    seq_len_k = k.shape[0] // batch_size
    num_heads = q.shape[1]
    head_dim = q.shape[2]

    # 重塑张量为标准注意力格式
    q = q.view(batch_size, seq_len_q, num_heads, head_dim).transpose(1, 2)  # (B, H, S_q, D)
    k = k.view(batch_size, seq_len_k, num_heads, head_dim).transpose(1, 2)  # (B, H, S_k, D)
    v = v.view(batch_size, seq_len_k, num_heads, head_dim).transpose(1, 2)  # (B, H, S_k, D)

    # 使用 F.scaled_dot_product_attention，它能更好地处理各种情况
    if base_blockmask is not None:
        if base_blockmask.dim() == 2:
            attn_mask = base_blockmask.unsqueeze(0).unsqueeze(0)
            attn_mask = attn_mask.expand(batch_size, num_heads, -1, -1)
        elif base_blockmask.dim() == 4:
            attn_mask = base_blockmask
        else:
            attn_mask = None
        if attn_mask is not None:
            _, _, mask_seq_q, mask_seq_k = attn_mask.shape

            target_seq_q = seq_len_q
            target_seq_k = seq_len_k
            #print(f"Attention mask shape: {attn_mask.shape},{target_seq_q},{target_seq_k}")
            #Attention mask shape:  torch.Size([1, 12, 24, 96]),3072,12288
            # 使用插值方法进行扩展，模式为 nearest 以保持稀疏结构
            if mask_seq_q != target_seq_q or mask_seq_k != target_seq_k:
                try:
                    attn_mask = F.interpolate(
                        attn_mask.float(),
                        size=(target_seq_q, target_seq_k),
                        mode='nearest'
                    ).to(attn_mask.dtype)
                except torch.OutOfMemoryError:
                    # 如果直接插值OOM，则分块处理
                    print("Direct interpolation OOM, using chunked processing")
                    attn_mask = chunked_interpolate(attn_mask, (target_seq_q, target_seq_k))
    else:
        attn_mask = None
    training=False
    try:
        output = F.scaled_dot_product_attention(
            q, k, v,
            attn_mask=attn_mask if attn_mask is not None else None,
            dropout_p=p_dropout if training else 0.0,
            is_causal=is_causal
        )
    except Exception:
        attention_scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(head_dim)
        if attn_mask is not None:
            if attn_mask.shape != attention_scores.shape:
                min_shape = [min(a, b) for a, b in zip(attn_mask.shape, attention_scores.shape)]
                attn_mask = attn_mask[:min_shape[0], :min_shape[1], :min_shape[2], :min_shape[3]]
                attention_scores = attention_scores[:min_shape[0], :min_shape[1], :min_shape[2], :min_shape[3]]
            if attn_mask.dtype == torch.bool:
                attention_scores = attention_scores.masked_fill(~attn_mask, float('-inf'))
            else:
                attention_scores = attention_scores + attn_mask
        attention_weights = F.softmax(attention_scores, dim=-1)
        output = torch.matmul(attention_weights, v)
    output = output.transpose(1, 2).contiguous().view(batch_size * seq_len_q, num_heads, head_dim)
    return output.squeeze(0)

def chunked_interpolate(tensor, target_size, chunk_size=1024):
    """
    分块插值以减少内存消耗
    """
    batch, heads, h, w = tensor.shape
    target_h, target_w = target_size

    output = torch.zeros(batch, heads, target_h, target_w, dtype=tensor.dtype, device=tensor.device)

    chunk_h = min(chunk_size, h)
    chunk_w = min(chunk_size, w)

    for i in range(0, h, chunk_h):
        for j in range(0, w, chunk_w):
            end_i = min(i + chunk_h, h)
            end_j = min(j + chunk_w, w)

            chunk = tensor[:, :, i:end_i, j:end_j]


            target_end_i = int(target_h * end_i / h)
            target_start_i = int(target_h * i / h)
            target_end_j = int(target_w * end_j / w)
            target_start_j = int(target_w * j / w)


            if chunk.numel() > 0:
                interpolated = F.interpolate(
                    chunk.float(),
                    size=(target_end_i - target_start_i, target_end_j - target_start_j),
                    mode='nearest'
                ).to(tensor.dtype)


                output[:, :, target_start_i:target_end_i, target_start_j:target_end_j] = interpolated

    return output


class RMS_norm(nn.Module):

    def __init__(self, dim, channel_first=True, images=True, bias=False):
        super().__init__()
        broadcastable_dims = (1, 1, 1) if not images else (1, 1)
        shape = (dim, *broadcastable_dims) if channel_first else (dim,)

        self.channel_first = channel_first
        self.scale = dim**0.5
        self.gamma = nn.Parameter(torch.ones(shape))
        self.bias = nn.Parameter(torch.zeros(shape)) if bias else 0.

    def forward(self, x):
        return F.normalize(
            x, dim=(1 if self.channel_first else
                    -1)) * self.scale * self.gamma + self.bias

class CausalConv3d(nn.Conv3d):
    """
    Causal 3d convolusion.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._padding = (self.padding[2], self.padding[2], self.padding[1],
                         self.padding[1], 2 * self.padding[0], 0)
        self.padding = (0, 0, 0)

    def forward(self, x, cache_x=None):
        padding = list(self._padding)
        if cache_x is not None and self._padding[4] > 0:
            cache_x = cache_x.to(x.device)
            # print(cache_x.shape, x.shape)
            x = torch.cat([cache_x, x], dim=2)
            padding[4] -= cache_x.shape[2]
            # print('cache!')
        x = F.pad(x, padding, mode='replicate') # mode='replicate'
        # print(x[0,0,:,0,0])

        return super().forward(x)

class PixelShuffle3d(nn.Module):
    def __init__(self, ff, hh, ww):
        super().__init__()
        self.ff = ff
        self.hh = hh
        self.ww = ww

    def forward(self, x):
        # x: (B, C, F, H, W)
        return rearrange(x,
                         'b c (f ff) (h hh) (w ww) -> b (c ff hh ww) f h w',
                         ff=self.ff, hh=self.hh, ww=self.ww)

class Buffer_LQ4x_Proj(nn.Module):

    def __init__(self, in_dim, out_dim, layer_num=30):
        super().__init__()
        self.ff = 1
        self.hh = 16
        self.ww = 16
        self.hidden_dim1 = 2048
        self.hidden_dim2 = 3072
        self.layer_num = layer_num

        self.pixel_shuffle = PixelShuffle3d(self.ff, self.hh, self.ww)

        self.conv1 = CausalConv3d(in_dim*self.ff*self.hh*self.ww, self.hidden_dim1, (4, 3, 3), stride=(2, 1, 1), padding=(1, 1, 1)) # f -> f/2 h -> h w -> w
        self.norm1 = RMS_norm(self.hidden_dim1, images=False)
        self.act1 = nn.SiLU()

        self.conv2 = CausalConv3d(self.hidden_dim1, self.hidden_dim2, (4, 3, 3), stride=(2, 1, 1), padding=(1, 1, 1)) # f -> f/2 h -> h w -> w
        self.norm2 = RMS_norm(self.hidden_dim2, images=False)
        self.act2 = nn.SiLU()

        self.linear_layers = nn.ModuleList([nn.Linear(self.hidden_dim2, out_dim) for _ in range(layer_num)])

        self.clip_idx = 0

    def forward(self, video):
        self.clear_cache()
        # x: (B, C, F, H, W)

        t = video.shape[2]
        iter_ = 1 + (t - 1) // 4
        first_frame = video[:, :, :1, :, :].repeat(1, 1, 3, 1, 1)
        video = torch.cat([first_frame, video], dim=2)
        # print(video.shape)

        out_x = []
        for i in range(iter_):
            x = self.pixel_shuffle(video[:,:,i*4:(i+1)*4,:,:])
            cache1_x = x[:, :, -CACHE_T:, :, :].clone()
            self.cache['conv1'] = cache1_x
            x = self.conv1(x, self.cache['conv1'])
            x = self.norm1(x)
            x = self.act1(x)
            cache2_x = x[:, :, -CACHE_T:, :, :].clone()
            self.cache['conv2'] = cache2_x
            if i == 0:
                continue
            x = self.conv2(x, self.cache['conv2'])
            x = self.norm2(x)
            x = self.act2(x)
            out_x.append(x)
        out_x = torch.cat(out_x, dim = 2)
        # print(out_x.shape)
        out_x = rearrange(out_x, 'b c f h w -> b (f h w) c')
        outputs = []
        for i in range(self.layer_num):
            outputs.append(self.linear_layers[i](out_x))
        return outputs

    def clear_cache(self):
        self.cache = {}
        self.cache['conv1'] = None
        self.cache['conv2'] = None
        self.clip_idx = 0

    def stream_forward(self, video_clip):
        if self.clip_idx == 0:
            # self.clear_cache()
            first_frame = video_clip[:, :, :1, :, :].repeat(1, 1, 3, 1, 1)
            video_clip = torch.cat([first_frame, video_clip], dim=2)
            x = self.pixel_shuffle(video_clip)
            cache1_x = x[:, :, -CACHE_T:, :, :].clone()
            self.cache['conv1'] = cache1_x
            x = self.conv1(x, self.cache['conv1'])
            x = self.norm1(x)
            x = self.act1(x)
            cache2_x = x[:, :, -CACHE_T:, :, :].clone()
            self.cache['conv2'] = cache2_x
            self.clip_idx += 1
            return None
        else:
            x = self.pixel_shuffle(video_clip)
            cache1_x = x[:, :, -CACHE_T:, :, :].clone()
            self.cache['conv1'] = cache1_x
            x = self.conv1(x, self.cache['conv1'])
            x = self.norm1(x)
            x = self.act1(x)
            cache2_x = x[:, :, -CACHE_T:, :, :].clone()
            self.cache['conv2'] = cache2_x
            x = self.conv2(x, self.cache['conv2'])
            x = self.norm2(x)
            x = self.act2(x)
            out_x = rearrange(x, 'b c f h w -> b (f h w) c')
            outputs = []
            for i in range(self.layer_num):
                outputs.append(self.linear_layers[i](out_x))
            self.clip_idx += 1
            return outputs


class Causal_LQ4x_Proj(nn.Module):

    def __init__(self, in_dim, out_dim, layer_num=30):
        super().__init__()
        self.ff = 1
        self.hh = 16
        self.ww = 16
        self.hidden_dim1 = 2048
        self.hidden_dim2 = 3072
        self.layer_num = layer_num

        self.pixel_shuffle = PixelShuffle3d(self.ff, self.hh, self.ww)

        self.conv1 = CausalConv3d(in_dim*self.ff*self.hh*self.ww, self.hidden_dim1, (4, 3, 3), stride=(2, 1, 1), padding=(1, 1, 1)) # f -> f/2 h -> h w -> w
        self.norm1 = RMS_norm(self.hidden_dim1, images=False)
        self.act1 = nn.SiLU()

        self.conv2 = CausalConv3d(self.hidden_dim1, self.hidden_dim2, (4, 3, 3), stride=(2, 1, 1), padding=(1, 1, 1)) # f -> f/2 h -> h w -> w
        self.norm2 = RMS_norm(self.hidden_dim2, images=False)
        self.act2 = nn.SiLU()

        self.linear_layers = nn.ModuleList([nn.Linear(self.hidden_dim2, out_dim) for _ in range(layer_num)])

        self.clip_idx = 0

    def forward(self, video):
        self.clear_cache()
        # x: (B, C, F, H, W)

        t = video.shape[2]
        iter_ = 1 + (t - 1) // 4
        first_frame = video[:, :, :1, :, :].repeat(1, 1, 3, 1, 1)
        video = torch.cat([first_frame, video], dim=2)
        # print(video.shape)

        out_x = []
        for i in range(iter_):
            x = self.pixel_shuffle(video[:,:,i*4:(i+1)*4,:,:])
            cache1_x = x[:, :, -CACHE_T:, :, :].clone()
            x = self.conv1(x, self.cache['conv1'])
            self.cache['conv1'] = cache1_x
            x = self.norm1(x)
            x = self.act1(x)
            cache2_x = x[:, :, -CACHE_T:, :, :].clone()
            if i == 0:
                self.cache['conv2'] = cache2_x
                continue
            x = self.conv2(x, self.cache['conv2'])
            self.cache['conv2'] = cache2_x
            x = self.norm2(x)
            x = self.act2(x)
            out_x.append(x)
        out_x = torch.cat(out_x, dim = 2)
        out_x = rearrange(out_x, 'b c f h w -> b (f h w) c')
        outputs = []
        for i in range(self.layer_num):
            outputs.append(self.linear_layers[i](out_x))
        return outputs

    def clear_cache(self):
        self.cache = {}
        self.cache['conv1'] = None
        self.cache['conv2'] = None
        self.clip_idx = 0

    def stream_forward(self, video_clip):
        if self.clip_idx == 0:
            # self.clear_cache()
            first_frame = video_clip[:, :, :1, :, :].repeat(1, 1, 3, 1, 1)
            video_clip = torch.cat([first_frame, video_clip], dim=2)
            x = self.pixel_shuffle(video_clip)
            cache1_x = x[:, :, -CACHE_T:, :, :].clone()
            x = self.conv1(x, self.cache['conv1'])
            self.cache['conv1'] = cache1_x
            x = self.norm1(x)
            x = self.act1(x)
            cache2_x = x[:, :, -CACHE_T:, :, :].clone()
            self.cache['conv2'] = cache2_x
            self.clip_idx += 1
            return None
        else:
            x = self.pixel_shuffle(video_clip)
            cache1_x = x[:, :, -CACHE_T:, :, :].clone()
            x = self.conv1(x, self.cache['conv1'])
            self.cache['conv1'] = cache1_x
            x = self.norm1(x)
            x = self.act1(x)
            cache2_x = x[:, :, -CACHE_T:, :, :].clone()
            x = self.conv2(x, self.cache['conv2'])
            self.cache['conv2'] = cache2_x
            x = self.norm2(x)
            x = self.act2(x)
            out_x = rearrange(x, 'b c f h w -> b (f h w) c')
            outputs = []
            for i in range(self.layer_num):
                outputs.append(self.linear_layers[i](out_x))
            self.clip_idx += 1
            return outputs

def calculate_frame_adjustment_simple(original_frames):
    input_frames = max(original_frames, 21)

    # 持续增加输入帧数直到满足输出要求
    while True:
        output_frames = calculate_output_frames_with_padding(input_frames)

        if output_frames >= original_frames:
            break
        input_frames += 1

    frames_to_add = input_frames + 4 - original_frames
    frames_to_remove = output_frames - original_frames

    return {
        'required_input_frames': input_frames,
        'frames_to_add': frames_to_add,
        'expected_output_frames': output_frames,
        'frames_to_remove': frames_to_remove,
        'is_sufficient': True
    }

def calculate_output_frames_with_padding(input_frames):
    start_value = 5  # 8*1 - 3
    interval = 8
    if input_frames < start_value:
        return start_value
    group_index = (input_frames - start_value) // interval
    group_min = start_value + group_index * interval
    group_max = group_min + interval - 1
    if group_min <= input_frames <= group_max:
        return group_min
    return group_min + interval

def largest_8n1_leq(n):  # 8n+1
    return 0 if n < 1 else ((n - 1)//8)*8 + 1
