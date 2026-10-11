# We are creating the 1-D Convolutional Autoencoder.
# Input Window Shape: [Batch, 2, 48] (2 channels: Consumption GC and Generation GG, with 48 half-hour intervals).
# The Goal: Compress 48 intervals down into a smaller latent representation, and reconstruct it back to 48.

import torch
import torch.nn as nn

class Conv1DAutoencoder(nn.Module):
    """
    1-D Convolutional Autoencoder for Smart-Meter Anomaly Detection.
    Input shape:  [Batch, 2, 48]  (2 channels: GC, GG; 48 half-hour intervals)
    Output shape: [Batch, 2, 48]  (Reconstructed telemetry)
    """
    def __init__(self, in_channels: int = 2):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Conv1d(in_channels=in_channels, out_channels=16, kernel_size=4, stride=2, padding=1), #this ompresses 48 time steps down to 24
            nn.ReLU(),
            nn.Conv1d(in_channels=16, out_channels=32, kernel_size=4, stride=2, padding=1), #24 to 12 time intervals
            nn.ReLU()
        )



        # -------------------------------------------------------------
        self.decoder = nn.Sequential(
            nn.ConvTranspose1d(in_channels=32, out_channels=16, kernel_size=4, stride=2, padding=1),
            nn.ReLU(),
            nn.ConvTranspose1d(in_channels=16, out_channels=in_channels, kernel_size=4, stride=2, padding=1),
            # >>> FILL IN YOUR ENCODER CODE HERE <<<
        )


    def forward(self, x):
        encoded = self.encoder(x)
        decoded = self.decoder(encoded)
        return decoded


# =====================================================================
# VERIFICATION CHECKPOINT (Tests your model automatically!)
# =====================================================================
if __name__ == "__main__":
    print("--- TESTING YOUR 1-D CONVOLUTIONAL AUTOENCODER ---")
    
    # 1. Create a dummy batch of 16 windows (matching dataset.py shape: [16, 2, 48])
    dummy_input = torch.randn(16, 2, 48)
    print(f"Dummy Input Shape:  {dummy_input.shape}")

    # 2. Instantiate your model
    model = Conv1DAutoencoder(in_channels=2)

    # 3. Run the forward pass
    reconstruction = model(dummy_input)
    print(f"Model Output Shape: {reconstruction.shape}")

    # 4. Check if dimensions match perfectly
    assert reconstruction.shape == dummy_input.shape, (
        f"❌ Mismatch! Input was {dummy_input.shape}, but model returned {reconstruction.shape}"
    )
    
    print("\n✅ CHECKPOINT PASSED! Your 1D Autoencoder compiles and reconstructs the exact [16, 2, 48] shape!")