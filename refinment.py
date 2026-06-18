import torch

def refine_soft_argmax(scores, kpts_int, win_size=3):
    """
    scores: [B,1,H,W] or [B,H,W] – raw score map
    kpts_int: [B,K,2] integer (x,y) coordinates
    win_size: odd integer (3 or 5)
    """
    B, K, _ = kpts_int.shape
    pad = win_size // 2
    H, W = scores.shape[-2], scores.shape[-1]
    
    xs = kpts_int[..., 0].long()
    ys = kpts_int[..., 1].long()
    
    # Precompute offsets
    offsets = torch.arange(-pad, pad+1, device=scores.device)
    dx, dy = torch.meshgrid(offsets, offsets, indexing='xy')
    offsets_flat = torch.stack([dx.flatten(), dy.flatten()], dim=-1)  # [win^2, 2]
    
    # Compute base indices (row-major)
    idx_base = ys * W + xs   # [B, K]
    
    # Expand to window indices
    # idx_win = idx_base + dx + dy * W   (dx, dy are scalar offsets)
    # We'll compute using broadcasting
    idx_win = idx_base.unsqueeze(-1) + offsets_flat[:, 0] + offsets_flat[:, 1] * W  # [B, K, win^2]
    
    max_idx = H * W - 1
    idx_win = idx_win.clamp(0, max_idx)
    
    # Flatten scores and gather
    scores_flat = scores.view(B, -1)  # [B, H*W]
    win_vals = scores_flat.gather(1, idx_win.view(B, -1)).view(B, K, win_size*win_size)
    
    weights = torch.softmax(win_vals, dim=-1)  # [B, K, win^2]
    subpix_offsets = (weights.unsqueeze(-1) * offsets_flat.to(weights.dtype)).sum(dim=-2)
    refined = kpts_int.float() + subpix_offsets

    return refined

def refine_quadratic(scores, kpts_int):
    """
    scores: [B,1,H,W] raw score map
    kpts_int: [B,K,2] integer (x,y) coordinates
    returns: [B,K,2] subpixel (x,y) coordinates
    """
    B, K, _ = kpts_int.shape
    H, W = scores.shape[-2], scores.shape[-1]
    xs = kpts_int[..., 0].long()
    ys = kpts_int[..., 1].long()
    
    # Pre‑compute offsets for 3x3 neighbourhood (row‑major order)
    offsets = torch.tensor([[-1,-1],[-1,0],[-1,1],
                            [0,-1], [0,0], [0,1],
                            [1,-1], [1,0], [1,1]],
                           device=scores.device, dtype=torch.int8)
    
    # Compute base linear indices
    idx_base = ys * W + xs   # [B,K]
    
    # Expand to 9 indices (dx + dy*W)
    idx_win = idx_base.unsqueeze(-1) + offsets[:, 0] + offsets[:, 1] * W   # [B,K,9]
    
    # Clamp to valid range – prevents any out‑of‑bounds gather
    max_idx = H * W - 1
    idx_win = idx_win.clamp(0, max_idx)

    batch_idx = torch.arange(B)[:, None]
    idx_win = idx_win.view(B, -1)
    idx_win_x = idx_win % W
    idx_win_y = idx_win // W

    vals = scores[batch_idx, 0, idx_win_y, idx_win_x]
#     print(f"\n\nNEW\nbatch_idx: {batch_idx.shape}\nvals: {vals.shape}\n\
# vals.view: {vals.view(B, K, 9).shape}\nx: {idx_win_x.shape}\ny: {idx_win_y.shape}\n\n")
    vals = vals.view(B, K, 9)
    
    # Gather the 9 neighbourhood values
    scores_flat = scores.view(B, -1)   # [B, H*W]
    #print(f"\n\nOLD\nscores_flat: {scores_flat.shape}\nscores: {scores.shape}\nidx_win: {idx_win.shape}\nidx_win_flat: {idx_win.view(B, -1).shape}")
    #vals = scores_flat.gather(1, idx_win.view(B, -1)).view(B, K, 9)  # [B,K,9]
    
    # Extract the 9 values for readability
    f00 = vals[..., 4]   # centre
    f10 = vals[..., 7]   # (1,0)
    f01 = vals[..., 5]   # (0,1)
    f_10 = vals[..., 1]  # (-1,0)
    f0_1 = vals[..., 3]  # (0,-1)
    f11 = vals[..., 8]   # (1,1)
    f_1_1 = vals[..., 0] # (-1,-1)
    f1_1 = vals[..., 6]  # (1,-1)
    f_11 = vals[..., 2]  # (-1,1)
    
    # Compute derivatives
    dx = (f10 - f_10) / 2.0
    dy = (f01 - f0_1) / 2.0
    dxx = (f10 + f_10 - 2 * f00)
    dyy = (f01 + f0_1 - 2 * f00)
    dxy = (f11 + f_1_1 - f1_1 - f_11) / 4.0
    
    # Solve for subpixel offset
    det = dxx * dyy - dxy * dxy
    eps = 1e-8
    valid = det.abs() > eps
    
    delta_x = torch.where(valid, (dyy * (-dx) - dxy * (-dy)) / (det), torch.zeros_like(dx))
    delta_y = torch.where(valid, (dxx * (-dy) - dxy * (-dx)) / (det), torch.zeros_like(dy))
    
    # Clean any potential NaN/inf (safety net)
    # delta_x = torch.nan_to_num(delta_x, nan=0.0, posinf=0.0, neginf=0.0)
    # delta_y = torch.nan_to_num(delta_y, nan=0.0, posinf=0.0, neginf=0.0)
    
    # Clamp offsets to ±0.95
    delta_x = delta_x.clamp(-0.95, 0.95)
    delta_y = delta_y.clamp(-0.95, 0.95)
    
    refined = kpts_int.float() + torch.stack([delta_x, delta_y], dim=-1)
    return refined

def refine_quadratic_with_gather(scores, kpts_int):
    """
    scores: [B,1,H,W] raw score map
    kpts_int: [B,K,2] integer (x,y) coordinates
    returns: [B,K,2] subpixel (x,y) coordinates
    """
    B, K, _ = kpts_int.shape
    H, W = scores.shape[-2], scores.shape[-1]
    xs = kpts_int[..., 0].long()
    ys = kpts_int[..., 1].long()
    
    # Pre‑compute offsets for 3x3 neighbourhood (row‑major order)
    offsets = torch.tensor([[-1,-1],[-1,0],[-1,1],
                            [0,-1], [0,0], [0,1],
                            [1,-1], [1,0], [1,1]],
                           device=scores.device, dtype=torch.int8)
    
    # Compute base linear indices
    idx_base = ys * W + xs   # [B,K]
    
    # Expand to 9 indices (dx + dy*W)
    idx_win = idx_base.unsqueeze(-1) + offsets[:, 0] + offsets[:, 1] * W   # [B,K,9]
    
    # Clamp to valid range – prevents any out‑of‑bounds gather
    max_idx = H * W - 1
    idx_win = idx_win.clamp(0, max_idx)
    
    # Gather the 9 neighbourhood values
    scores_flat = scores.view(B, -1)   # [B, H*W]
    vals = scores_flat.gather(1, idx_win.view(B, -1)).view(B, K, 9)  # [B,K,9]
    
    # Extract the 9 values for readability
    f00 = vals[..., 4]   # centre
    f10 = vals[..., 7]   # (1,0)
    f01 = vals[..., 5]   # (0,1)
    f_10 = vals[..., 1]  # (-1,0)
    f0_1 = vals[..., 3]  # (0,-1)
    f11 = vals[..., 8]   # (1,1)
    f_1_1 = vals[..., 0] # (-1,-1)
    f1_1 = vals[..., 6]  # (1,-1)
    f_11 = vals[..., 2]  # (-1,1)
    
    # Compute derivatives
    dx = (f10 - f_10) / 2.0
    dy = (f01 - f0_1) / 2.0
    dxx = (f10 + f_10 - 2 * f00)
    dyy = (f01 + f0_1 - 2 * f00)
    dxy = (f11 + f_1_1 - f1_1 - f_11) / 4.0
    
    # Solve for subpixel offset
    det = dxx * dyy - dxy * dxy
    eps = 1e-8
    valid = det.abs() > eps
    
    delta_x = torch.where(valid, (dyy * (-dx) - dxy * (-dy)) / (det), torch.zeros_like(dx))
    delta_y = torch.where(valid, (dxx * (-dy) - dxy * (-dx)) / (det), torch.zeros_like(dy))
    
    # Clean any potential NaN/inf (safety net)
    # delta_x = torch.nan_to_num(delta_x, nan=0.0, posinf=0.0, neginf=0.0)
    # delta_y = torch.nan_to_num(delta_y, nan=0.0, posinf=0.0, neginf=0.0)
    
    # Clamp offsets to ±0.95
    delta_x = delta_x.clamp(-0.95, 0.95)
    delta_y = delta_y.clamp(-0.95, 0.95)
    
    refined = kpts_int.float() + torch.stack([delta_x, delta_y], dim=-1)
    return refined
