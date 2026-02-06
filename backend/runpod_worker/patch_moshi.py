"""
Monkey-patch for Moshi IndexError bugs in transformer.py

Root cause: In streaming mode, offset + t can exceed array/module list bounds
when the accumulated step count exceeds weights_per_step.

This patch fixes ALL known overflow locations:

OLD Moshi versions (PersonaPlex/nvidia):
  1. multi_linear() - weight[t + offset] overflow
  2. _ff_block() - self.gating[offset + t] overflow

NEW Moshi versions (kyutai-labs/main):
  3. apply_weights_per_step() - modules[module_index] overflow

Usage:
    from patch_moshi import apply_moshi_patch
    apply_moshi_patch()
"""
import logging
import typing as tp

import torch
import torch.nn as nn
from torch.nn import functional as F

logger = logging.getLogger(__name__)

_patch_applied = False


# =============================================================================
# Patch 1: Fix multi_linear (OLD Moshi versions)
# Original: weight[t + offset] overflows when t + offset >= num_linear
# =============================================================================
def safe_multi_linear(
    num_linear: int,
    weight: torch.Tensor,
    x: torch.Tensor,
    offset: int,
):
    """Safe multi_linear that wraps index to prevent overflow."""
    B, T, C = x.shape
    ys = []
    chout, chin = weight.shape
    weight = weight.view(num_linear, -1, chin)
    for t in range(T):
        idx = (t + offset) % num_linear
        y = F.linear(x[:, t], weight[idx])
        ys.append(y)
    out = torch.stack(ys, 1)
    return out


# =============================================================================
# Patch 2: Fix apply_weights_per_step (NEW Moshi versions)
# Original: modules[module_index] overflows
# =============================================================================
def safe_apply_weights_per_step(
    modules: nn.ModuleList,
    schedule: "list[int] | None",
    x: torch.Tensor,
    offset: "int | None",
) -> torch.Tensor:
    """Safe apply_weights_per_step that wraps index to prevent overflow."""
    if len(modules) == 1:
        return modules[0](x)

    assert offset is not None, "Out of sync execution with weights per step."

    num_modules = len(modules)
    ys: "list[torch.Tensor]" = []
    B, T, C = x.shape
    for t in range(T):
        module_index = t + offset
        if schedule is not None:
            # Clamp to schedule length first
            schedule_idx = module_index % len(schedule)
            module_index = schedule[schedule_idx]
        else:
            module_index = module_index % num_modules
        y = modules[module_index](x[:, t : t + 1])
        ys.append(y)
    out = torch.cat(ys, 1)
    return out


# =============================================================================
# Patch 3: Fix _ff_block (OLD Moshi versions where gating is accessed directly)
# Original: self.gating[offset + t] overflows
# =============================================================================
def safe_ff_block(self, x: torch.Tensor) -> torch.Tensor:
    """Safe _ff_block that wraps gating index to prevent overflow."""
    state = self._streaming_state
    offset = 0
    if state is not None:
        offset = state.offset_cpu
    x_orig = x
    x = self.norm2(x)
    if self.gating is None:
        assert self.linear1 is not None
        assert self.linear2 is not None
        update = self.linear2(self.activation(self.linear1(x)))
    else:
        if self.weights_per_step:
            assert isinstance(self.gating, nn.ModuleList)
            num_gates = len(self.gating)
            B, T, D = x.shape
            ys = []
            for t in range(T):
                idx = (offset + t) % num_gates
                y = self.gating[idx](x[:, t : t + 1])
                ys.append(y)
            update = torch.cat(ys, dim=1)
        else:
            update = self.gating(x)
    # Use .to(update) for dtype compatibility (safe for both old/new versions)
    return x_orig.to(update) + self.layer_scale_2(update)


# =============================================================================
# Apply all patches
# =============================================================================
def apply_moshi_patch():
    """
    Apply monkey-patches to fix all Moshi IndexError bugs.
    
    Detects which version of Moshi is installed and patches accordingly.
    Safe to call multiple times (only patches once).
    """
    global _patch_applied

    if _patch_applied:
        logger.info("Moshi patch already applied")
        return

    try:
        import moshi.modules.transformer as mt

        patches_applied = 0

        # --- Patch for OLD versions: multi_linear ---
        if hasattr(mt, 'multi_linear'):
            mt._original_multi_linear = mt.multi_linear
            mt.multi_linear = safe_multi_linear
            patches_applied += 1
            logger.info("  [+] Patched multi_linear (attention index overflow fix)")

        # --- Patch for NEW versions: apply_weights_per_step ---
        if hasattr(mt, 'apply_weights_per_step'):
            mt._original_apply_weights_per_step = mt.apply_weights_per_step
            mt.apply_weights_per_step = safe_apply_weights_per_step
            patches_applied += 1
            logger.info("  [+] Patched apply_weights_per_step (module index overflow fix)")

        # --- Patch for OLD versions: _ff_block on StreamingTransformerLayer ---
        # Only needed if apply_weights_per_step doesn't exist (old code has direct loop)
        if not hasattr(mt, 'apply_weights_per_step'):
            layer_class = mt.StreamingTransformerLayer
            if hasattr(layer_class, '_ff_block'):
                layer_class._original_ff_block = layer_class._ff_block
                layer_class._ff_block = safe_ff_block
                patches_applied += 1
                logger.info("  [+] Patched _ff_block (gating index overflow fix)")

        _patch_applied = True
        logger.info(f"Moshi patches applied successfully ({patches_applied} patches)")

    except ImportError:
        logger.warning("Could not import moshi.modules.transformer - patches not applied")
    except Exception as e:
        logger.error(f"Failed to apply Moshi patches: {e}", exc_info=True)


def is_patch_applied():
    """Check if the patches have been applied."""
    return _patch_applied


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    apply_moshi_patch()
    if is_patch_applied():
        print("All patches applied successfully")
    else:
        print("Patches not applied - check logs")
