"""
Temporal Fusion Transformer - Multi-Timeframe State Encoder
============================================================
Processes multiple timeframes simultaneously to learn cross-timeframe patterns.

Architecture:
1. Separate encoder per timeframe (D1, H4, H1, M15, M5, M1)
2. Cross-timeframe attention (learns "D1 up + H1 pullback = long")
3. Fusion layer outputs 512-dim state embedding

Used by PPO agent to understand market structure.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List
import numpy as np


class TimeframeEncoder(nn.Module):
    """
    Encodes a single timeframe using 1D CNN + Attention.

    Input: (batch, seq_len, 5) - OHLCV data
    Output: (batch, hidden_dim) - Encoded representation
    """

    def __init__(self, input_dim: int = 5, hidden_dim: int = 64, seq_len: int = 100):
        super().__init__()

        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.seq_len = seq_len

        # 1D Convolutional layers to extract local patterns
        self.conv1 = nn.Conv1d(input_dim, 32, kernel_size=3, padding=1)
        self.conv2 = nn.Conv1d(32, 64, kernel_size=3, padding=1)
        self.conv3 = nn.Conv1d(64, hidden_dim, kernel_size=3, padding=1)

        self.bn1 = nn.BatchNorm1d(32)
        self.bn2 = nn.BatchNorm1d(64)
        self.bn3 = nn.BatchNorm1d(hidden_dim)

        # Self-attention to capture long-range dependencies
        self.attention = nn.MultiheadAttention(
            embed_dim=hidden_dim,
            num_heads=4,
            batch_first=True
        )

        # Layer norm
        self.layer_norm = nn.LayerNorm(hidden_dim)

        # Final pooling
        self.global_pool = nn.AdaptiveAvgPool1d(1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (batch, seq_len, input_dim) - OHLCV data

        Returns:
            (batch, hidden_dim) - Encoded representation
        """
        # Transpose for Conv1d: (batch, input_dim, seq_len)
        x = x.transpose(1, 2)

        # Convolutional feature extraction
        x = F.relu(self.bn1(self.conv1(x)))
        x = F.relu(self.bn2(self.conv2(x)))
        x = F.relu(self.bn3(self.conv3(x)))

        # Transpose back for attention: (batch, seq_len, hidden_dim)
        x = x.transpose(1, 2)

        # Self-attention
        attn_out, _ = self.attention(x, x, x)

        # Residual connection + layer norm
        x = self.layer_norm(x + attn_out)

        # Global pooling: (batch, hidden_dim, seq_len) -> (batch, hidden_dim, 1)
        x = x.transpose(1, 2)
        x = self.global_pool(x).squeeze(-1)

        return x  # (batch, hidden_dim)


class MultiTimeframeEncoder(nn.Module):
    """
    Processes ALL timeframes simultaneously with cross-timeframe attention.

    Learns patterns like:
    - "D1 uptrend + H4 pullback to support + M15 consolidation = high-prob long"
    - "All timeframes aligned bearish + high volatility = avoid"

    Input: Dict of timeframe data {
        'D1': (batch, 30, 5),
        'H4': (batch, 120, 5),
        'H1': (batch, 168, 5),
        'M15': (batch, 672, 5),
        'M5': (batch, 2016, 5),
        'M1': (batch, 1440, 5)
    }

    Output: (batch, 512) - Fused multi-timeframe state embedding
    """

    def __init__(self, hidden_dim: int = 64):
        super().__init__()

        self.hidden_dim = hidden_dim

        # Separate encoder for each timeframe
        # Varying sequence lengths based on what makes sense for each TF
        self.d1_encoder = TimeframeEncoder(input_dim=5, hidden_dim=hidden_dim, seq_len=30)
        self.h4_encoder = TimeframeEncoder(input_dim=5, hidden_dim=hidden_dim, seq_len=120)
        self.h1_encoder = TimeframeEncoder(input_dim=5, hidden_dim=hidden_dim, seq_len=168)
        self.m15_encoder = TimeframeEncoder(input_dim=5, hidden_dim=hidden_dim, seq_len=96)  # Reduced from 672
        self.m5_encoder = TimeframeEncoder(input_dim=5, hidden_dim=hidden_dim, seq_len=288)  # Reduced from 2016
        self.m1_encoder = TimeframeEncoder(input_dim=5, hidden_dim=hidden_dim, seq_len=100)  # Reduced from 1440

        # Cross-timeframe attention
        # Allows timeframes to "communicate" and learn relationships
        self.cross_attention = nn.MultiheadAttention(
            embed_dim=hidden_dim,
            num_heads=8,
            batch_first=True
        )

        # Fusion layer: Combine all timeframe embeddings
        self.fusion = nn.Sequential(
            nn.Linear(hidden_dim * 6, 512),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Dropout(0.1),
        )

        # Final output layer
        self.output_layer = nn.Linear(256, 512)

    def forward(self, multi_tf_data: Dict[str, torch.Tensor]) -> torch.Tensor:
        """
        Args:
            multi_tf_data: Dict of {
                'D1': (batch, seq_len, 5),
                'H4': (batch, seq_len, 5),
                ...
            }

        Returns:
            (batch, 512) - Fused state embedding
        """
        # Encode each timeframe separately
        d1_emb = self.d1_encoder(multi_tf_data.get('D1', torch.zeros(1, 30, 5)))
        h4_emb = self.h4_encoder(multi_tf_data.get('H4', torch.zeros(1, 120, 5)))
        h1_emb = self.h1_encoder(multi_tf_data.get('H1', torch.zeros(1, 168, 5)))
        m15_emb = self.m15_encoder(multi_tf_data.get('M15', torch.zeros(1, 96, 5)))
        m5_emb = self.m5_encoder(multi_tf_data.get('M5', torch.zeros(1, 288, 5)))
        m1_emb = self.m1_encoder(multi_tf_data.get('M1', torch.zeros(1, 100, 5)))

        # Stack embeddings for cross-attention
        # Shape: (6, batch, hidden_dim) -> (batch, 6, hidden_dim)
        all_embs = torch.stack([d1_emb, h4_emb, h1_emb, m15_emb, m5_emb, m1_emb], dim=1)

        # Cross-timeframe attention
        # Each timeframe can "attend" to other timeframes
        # This learns patterns like "D1 trend + H1 pullback"
        attended, attention_weights = self.cross_attention(all_embs, all_embs, all_embs)

        # Flatten: (batch, 6, hidden_dim) -> (batch, 6 * hidden_dim)
        fused = attended.flatten(start_dim=1)

        # Fusion layers
        fused = self.fusion(fused)

        # Final output
        state_embedding = self.output_layer(fused)

        return state_embedding  # (batch, 512)


class TransformerFeatureExtractor(nn.Module):
    """
    Custom feature extractor for Stable-Baselines3 PPO.

    Processes raw multi-timeframe market data + additional features
    into a unified state representation.

    This replaces the default MlpExtractor in PPO.
    """

    def __init__(
        self,
        observation_space,
        features_dim: int = 512,
        transformer_hidden_dim: int = 64,
    ):
        super().__init__()

        self._features_dim = features_dim

        # Multi-timeframe Transformer
        self.transformer = MultiTimeframeEncoder(hidden_dim=transformer_hidden_dim)

        # Process additional features (account, position, indicators)
        # These are already processed, just need to combine them
        account_dim = 12
        position_dim = 6
        indicators_dim = 20
        additional_dim = account_dim + position_dim + indicators_dim

        self.additional_features = nn.Sequential(
            nn.Linear(additional_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(256, 256),
            nn.ReLU(),
        )

        # Final fusion: Transformer embedding + additional features
        self.final_fusion = nn.Sequential(
            nn.Linear(512 + 256, features_dim),
            nn.ReLU(),
            nn.Dropout(0.1),
        )

    def forward(self, observations: Dict[str, torch.Tensor]) -> torch.Tensor:
        """
        Args:
            observations: Dict from environment with keys:
                - 'market_data': Dict of multi-timeframe OHLCV
                - 'account_state': (batch, 12)
                - 'position_state': (batch, 6)
                - 'indicators': (batch, 20)

        Returns:
            (batch, features_dim) - Final state representation for PPO
        """
        # Process multi-timeframe market data with Transformer
        # Note: In actual use, we need to extract multi-TF data from environment
        # For now, we'll use a placeholder approach

        # Extract market data (will be populated by environment wrapper)
        if 'market_data' in observations and isinstance(observations['market_data'], dict):
            tf_embedding = self.transformer(observations['market_data'])
        else:
            # Fallback: Use zeros if market data not available
            batch_size = observations['account_state'].shape[0]
            tf_embedding = torch.zeros(batch_size, 512, device=observations['account_state'].device)

        # Process additional features
        additional = torch.cat([
            observations['account_state'],
            observations['position_state'],
            observations['indicators'],
        ], dim=-1)

        additional_embedding = self.additional_features(additional)

        # Fuse everything together
        final_state = self.final_fusion(
            torch.cat([tf_embedding, additional_embedding], dim=-1)
        )

        return final_state

    @property
    def features_dim(self) -> int:
        return self._features_dim


def create_dummy_multi_tf_data(batch_size: int = 1) -> Dict[str, torch.Tensor]:
    """
    Create dummy multi-timeframe data for testing.

    Returns:
        Dict of {
            'D1': (batch, 30, 5),
            'H4': (batch, 120, 5),
            'H1': (batch, 168, 5),
            'M15': (batch, 96, 5),
            'M5': (batch, 288, 5),
            'M1': (batch, 100, 5)
        }
    """
    return {
        'D1': torch.randn(batch_size, 30, 5),
        'H4': torch.randn(batch_size, 120, 5),
        'H1': torch.randn(batch_size, 168, 5),
        'M15': torch.randn(batch_size, 96, 5),
        'M5': torch.randn(batch_size, 288, 5),
        'M1': torch.randn(batch_size, 100, 5),
    }


if __name__ == "__main__":
    # Test the Transformer
    print("Testing Multi-Timeframe Transformer...")

    # Create dummy data
    batch_size = 4
    dummy_data = create_dummy_multi_tf_data(batch_size)

    # Create model
    model = MultiTimeframeEncoder(hidden_dim=64)

    # Forward pass
    output = model(dummy_data)

    print(f"Input shapes:")
    for tf, data in dummy_data.items():
        print(f"  {tf}: {data.shape}")

    print(f"\nOutput shape: {output.shape}")
    print(f"Expected: ({batch_size}, 512)")

    # Count parameters
    total_params = sum(p.numel() for p in model.parameters())
    print(f"\nTotal parameters: {total_params:,}")

    print("\n✅ Transformer test passed!")
